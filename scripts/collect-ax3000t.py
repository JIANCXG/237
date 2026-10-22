#!/usr/bin/env python3
"""Collect verified AX3000T firmware into a flat directory for artifacts/releases."""
import hashlib
from pathlib import Path
import shutil


def collect(root=Path.cwd()):
    target = root / "bin/targets/mediatek/filogic"
    output = root / "firmware"
    images = sorted(target.glob("*xiaomi_mi-router-ax3000t*"))
    for suffix in ("-initramfs-factory.ubi", "-squashfs-sysupgrade.bin"):
        matches = [path for path in images if path.name.endswith(suffix)]
        if len(matches) != 1 or matches[0].stat().st_size == 0:
            raise ValueError(f"Expected one nonempty AX3000T {suffix} image")
    files = images + sorted(target.glob("*.manifest")) + sorted(target.glob("*.buildinfo"))
    files += [target / "profiles.json", target / "passwall-upstream.json", root / "ax3000t.build.config"]
    # Validate all inputs before producing release assets.
    for path in files:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty firmware asset: {path}")
    if output.exists():
        raise FileExistsError(f"Refusing to reuse an existing output directory: {output}")
    output.mkdir()
    for path in files:
        shutil.copy2(path, output / path.name)
    sums = []
    for path in sorted(output.iterdir()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sums.append(f"{digest}  {path.name}\n")
    (output / "sha256sums").write_text("".join(sums), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    collect()
