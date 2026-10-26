import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


updater = load("updater", "update-passwall.py")
collector = load("collector", "collect-ax3000t.py")


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".github").mkdir()
        self.now = datetime(2026, 10, 22, tzinfo=timezone.utc)
        self.commits = {name: str(index) * 40 for index, name in enumerate(updater.SOURCES, 1)}
        self.lock = self.root / ".github/passwall-upstream.json"
        self.lock.write_text(json.dumps({"checked_at": self.now.isoformat(), "commits": self.commits}))
        (self.root / "feeds.conf.default").write_text("".join(
            f"src-git {name} {updater.SOURCES[name][0]}^{self.commits[name]}\n"
            for name in updater.FEED_SOURCES
        ))
        (self.root / "config").write_text("stock profile\n")
        self.git("init", "-q")
        self.git("config", "user.name", "Release tests")
        self.git("config", "user.email", "tests@example.invalid")
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test state")

    def success(self):
        updater.record_success(self.git("rev-parse", "HEAD"), updater.fingerprint(self.root),
                               "test-release", "https://example.invalid/run", self.root)

    def test_unpublished_build_remains_pending_within_gate(self):
        def forbidden(*args):
            self.fail("Must not query upstream within 72 hours")
        self.assertFalse(updater.refresh(self.root, now=self.now + timedelta(hours=1), resolve=forbidden))
        self.assertTrue(updater.needs_build(self.root))

    def test_success_and_state_commits_do_not_rebuild(self):
        self.success()
        self.commit()
        self.assertFalse(updater.needs_build(self.root))
        updater.refresh(self.root, now=self.now + timedelta(hours=73),
                        resolve=lambda url, branch: next(self.commits[name] for name, src in updater.SOURCES.items() if src == (url, branch)))
        self.commit()
        self.assertFalse(updater.needs_build(self.root))

    def test_source_changes_require_release(self):
        self.success()
        (self.root / "config").write_text("updated stock profile\n")
        self.commit()
        self.assertTrue(updater.needs_build(self.root))

    def test_new_pins_require_release(self):
        self.success()
        self.assertTrue(updater.refresh(self.root, force=True, now=self.now,
                                        resolve=lambda *args: "a" * 40))
        self.assertTrue(updater.needs_build(self.root))

    def test_failed_upstream_does_not_advance_clock_or_feeds(self):
        before = self.lock.read_bytes(), (self.root / "feeds.conf.default").read_bytes()
        def fail(url, branch):
            if "packages" in url:
                raise RuntimeError("upstream unavailable")
            return "a" * 40
        with self.assertRaises(RuntimeError):
            updater.refresh(self.root, force=True, now=self.now, resolve=fail)
        self.assertEqual(before, (self.lock.read_bytes(), (self.root / "feeds.conf.default").read_bytes()))

    def test_each_base_feed_update_requires_release_and_pins_exact_commit(self):
        for interval, changed_name in enumerate(("packages", "luci", "routing", "telephony"), 1):
            with self.subTest(feed=changed_name):
                self.success()
                current = json.loads(self.lock.read_text())["commits"]
                expected = dict(current, **{changed_name: "a" * 40})
                def resolve(url, branch):
                    return next(expected[name] for name, source in updater.SOURCES.items()
                                if source == (url, branch))
                self.assertTrue(updater.refresh(self.root, now=self.now + timedelta(hours=73 * interval),
                                                resolve=resolve))
                self.assertTrue(updater.needs_build(self.root))
                feeds = (self.root / "feeds.conf.default").read_text().splitlines()
                for name in updater.FEED_SOURCES:
                    self.assertIn(f"src-git {name} {updater.SOURCES[name][0]}^{expected[name]}", feeds)
                self.assertEqual(json.loads(self.lock.read_text())["commits"], expected)

    def test_last_feed_failure_preserves_all_pins_and_check_time(self):
        before = self.lock.read_bytes(), (self.root / "feeds.conf.default").read_bytes()
        def resolve(url, branch):
            if (url, branch) == updater.SOURCES["telephony"]:
                raise RuntimeError("last feed unavailable")
            return "a" * 40
        with self.assertRaises(RuntimeError):
            updater.refresh(self.root, now=self.now + timedelta(hours=73), resolve=resolve)
        self.assertEqual(before, (self.lock.read_bytes(), (self.root / "feeds.conf.default").read_bytes()))

    def test_missing_feed_entry_does_not_partially_write_pins(self):
        feeds = self.root / "feeds.conf.default"
        feeds.write_text("\n".join(line for line in feeds.read_text().splitlines()
                                   if not line.startswith("src-git telephony ")) + "\n")
        before = self.lock.read_bytes(), feeds.read_bytes()
        with self.assertRaises(ValueError):
            updater.refresh(self.root, force=True, now=self.now, resolve=lambda *args: "a" * 40)
        self.assertEqual(before, (self.lock.read_bytes(), feeds.read_bytes()))

    def make_assets(self):
        target = self.root / "bin/targets/mediatek/filogic"
        target.mkdir(parents=True)
        for name in ("firmware-xiaomi_mi-router-ax3000t-mtkuboot-squashfs-factory.bin",
                     "firmware-xiaomi_mi-router-ax3000t-mtkuboot-squashfs-sysupgrade.bin",
                     "firmware.manifest", "profiles.json", "passwall-upstream.json", "config.buildinfo"):
            (target / name).write_text(name)
        (self.root / "ax3000t.build.config").write_text("CONFIG_TARGET=y\n")
        return target

    def test_flat_assets_and_all_checksums(self):
        self.make_assets()
        collector.collect(self.root)
        output = self.root / "firmware"
        lines = (output / "sha256sums").read_text().splitlines()
        self.assertEqual(len(lines), 7)
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(digest, hashlib.sha256((output / name).read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            collector.collect(self.root)

    def test_missing_upgrade_image_blocks_publication(self):
        target = self.make_assets()
        next(target.glob("*sysupgrade.bin")).unlink()
        with self.assertRaises(ValueError):
            collector.collect(self.root)
        self.assertFalse((self.root / "firmware").exists())

    def test_stock_and_ubootmod_images_cannot_replace_mtkuboot(self):
        target = self.make_assets()
        next(target.glob("*sysupgrade.bin")).unlink()
        for name in ("firmware-xiaomi_mi-router-ax3000t-squashfs-sysupgrade.bin",
                     "firmware-xiaomi_mi-router-ax3000t-ubootmod-sysupgrade.itb"):
            (target / name).write_text(name)
        with self.assertRaises(ValueError):
            collector.collect(self.root)
        self.assertFalse((self.root / "firmware").exists())


if __name__ == "__main__":
    unittest.main()
