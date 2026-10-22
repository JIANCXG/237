#!/usr/bin/env python3
"""Refresh pinned PassWall feeds at most once every 72 hours."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "passwall_luci": ("https://github.com/Openwrt-Passwall/openwrt-passwall.git", "main"),
    "passwall_packages": ("https://github.com/Openwrt-Passwall/openwrt-passwall-packages.git", "main"),
    "golang": ("https://github.com/sbwml/packages_lang_golang.git", "27.x"),
}
SUCCESS_STATE = ".github/ax3000t-last-success.json"


def fingerprint(root=ROOT):
    """Ignore state-only commits while tracking source, config and pinned feeds."""
    tree = subprocess.check_output(
        ["git", "ls-tree", "-r", "HEAD"], cwd=root, text=True,
    ).splitlines()
    excluded = {"feeds.conf.default", ".github/passwall-upstream.json", SUCCESS_STATE}
    tree = [line for line in tree if line.split("\t", 1)[1] not in excluded]
    lock = json.loads((root / ".github/passwall-upstream.json").read_text(encoding="utf-8"))
    payload = "\n".join(tree) + "\n" + (root / "feeds.conf.default").read_text(encoding="utf-8")
    payload += json.dumps(lock["commits"], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def needs_build(root=ROOT):
    state = root / SUCCESS_STATE
    previous = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    return previous.get("fingerprint") != fingerprint(root)


def record_success(source_commit, digest, release_tag, run_url, root=ROOT):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Invalid source commit")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid fingerprint")
    state = {
        "fingerprint": digest, "source_commit": source_commit,
        "release_tag": release_tag, "run_url": run_url,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (root / SUCCESS_STATE).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")


def remote_commit(url, branch):
    output = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", url, f"refs/heads/{branch}"],
        text=True, timeout=90,
    )
    sha = output.split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"Invalid upstream commit for {url}")
    return sha


def refresh(root=ROOT, force=False, now=None, resolve=remote_commit):
    now = now or datetime.now(timezone.utc)
    lock_path = root / ".github/passwall-upstream.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    previous = datetime.fromisoformat(lock["checked_at"])
    if not force and now - previous < timedelta(hours=72):
        print("Less than 72 hours since the last successful check; skipping.")
        return False
    # Resolve every source before modifying files; failed checks are retried next hour.
    commits = {name: resolve(*source) for name, source in SOURCES.items()}
    changed = any(lock["commits"].get(name) != sha for name, sha in commits.items())
    feeds_path = root / "feeds.conf.default"
    feeds = feeds_path.read_text(encoding="utf-8")
    for name in ("passwall_luci", "passwall_packages"):
        line = f"src-git {name} {SOURCES[name][0]}^{commits[name]}"
        feeds, count = re.subn(rf"^src-git {name} .+$", line, feeds, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"Expected exactly one feed entry for {name}")
    lock["commits"] = commits
    lock["checked_at"] = now.isoformat(timespec="seconds")
    feeds_path.write_text(feeds, encoding="utf-8", newline="\n")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Upstream changed." if changed else "No upstream changes.")
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Check even within 72 hours")
    parser.add_argument("--fingerprint", action="store_true", help="Print the current build fingerprint")
    parser.add_argument("--record-success", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--build-fingerprint")
    parser.add_argument("--release-tag")
    parser.add_argument("--run-url")
    args = parser.parse_args()
    if args.fingerprint:
        print(fingerprint())
        raise SystemExit(0)
    if args.record_success:
        if not all((args.source_commit, args.build_fingerprint, args.release_tag, args.run_url)):
            parser.error("Recording success requires source commit, fingerprint, release tag and run URL")
        record_success(args.source_commit, args.build_fingerprint, args.release_tag, args.run_url)
        raise SystemExit(0)
    refresh(force=args.force)
    # Only a published release counts as success, so failed builds remain pending.
    changed = needs_build()
    print("Build/release pending." if changed else "Current firmware already published.")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"changed={str(changed).lower()}\n")
