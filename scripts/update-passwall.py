#!/usr/bin/env python3
"""Refresh pinned PassWall feeds at most once every 72 hours."""
import argparse
from datetime import datetime, timedelta, timezone
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
    # Resolve every source before modifying files; failed checks are retried tomorrow.
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
    args = parser.parse_args()
    changed = refresh(force=args.force)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"changed={str(changed).lower()}\n")
