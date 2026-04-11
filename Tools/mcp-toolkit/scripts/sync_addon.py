#!/usr/bin/env python3
"""Sync veilbreakers_mcp_bridge addon to every detected Blender install.

Covers Blender 4.5 LTS and 5.x in parallel. Blender reads addons from the
user-config dir (``%APPDATA%/Blender Foundation/Blender/<major.minor>/scripts/addons``)
regardless of whether the Blender binary itself is a portable zip or an MSI
install, so this script targets that path per detected version.

Usage:
    python scripts/sync_addon.py                # sync to every detected version
    python scripts/sync_addon.py --list         # show detected versions, no changes
    python scripts/sync_addon.py --dry-run      # show what would copy
    python scripts/sync_addon.py --version 4.5  # restrict to one version
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ADDON_NAME = "veilbreakers_mcp_bridge"
REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ADDON = REPO_ROOT / "blender_addon"


@dataclass
class BlenderTarget:
    version: str  # "4.5", "5.0", ...
    config_root: Path  # .../Blender Foundation/Blender/<version>
    addons_dir: Path  # .../<version>/scripts/addons
    binary: Path | None  # best-guess blender.exe if we can find one

    @property
    def dest(self) -> Path:
        return self.addons_dir / ADDON_NAME


def _appdata_roaming() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def _appdata_local() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local)
    return Path.home() / "AppData" / "Local"


def _candidate_binaries(version: str) -> list[Path]:
    candidates: list[Path] = []
    program_files_dirs = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation" / f"Blender {version}",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Blender Foundation" / f"Blender {version}",
    ]
    for pf in program_files_dirs:
        candidates.append(pf / "blender.exe")
    # Portable installs commonly live under %LOCALAPPDATA%\Programs\blender-<version>*
    local_programs = _appdata_local() / "Programs"
    if local_programs.exists():
        for child in local_programs.iterdir():
            if child.is_dir() and child.name.lower().startswith(f"blender-{version}"):
                candidates.append(child / "blender.exe")
    return [c for c in candidates if c.exists()]


def detect_targets() -> list[BlenderTarget]:
    root = _appdata_roaming() / "Blender Foundation" / "Blender"
    if not root.exists():
        return []
    out: list[BlenderTarget] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        version = child.name
        # Skip non-versioned entries like "Custom" or stray folders.
        if not version.replace(".", "").isdigit():
            continue
        addons = child / "scripts" / "addons"
        binaries = _candidate_binaries(version)
        out.append(
            BlenderTarget(
                version=version,
                config_root=child,
                addons_dir=addons,
                binary=binaries[0] if binaries else None,
            )
        )
    return out


def _dir_signature(path: Path) -> tuple[int, str]:
    """Return (file_count, sha1-of-content-digest) so we can tell if sync is needed."""
    if not path.exists():
        return (0, "")
    h = hashlib.sha1()
    count = 0
    for p in sorted(path.rglob("*")):
        if p.is_file():
            count += 1
            h.update(str(p.relative_to(path)).encode("utf-8"))
            h.update(b"\0")
            try:
                h.update(p.read_bytes())
            except OSError:
                pass
    return (count, h.hexdigest())


def sync_target(target: BlenderTarget, dry_run: bool) -> str:
    src_sig = _dir_signature(SOURCE_ADDON)
    dst_sig = _dir_signature(target.dest)
    if src_sig == dst_sig:
        return f"up-to-date ({src_sig[0]} files)"
    if dry_run:
        return f"WOULD SYNC ({dst_sig[0]} -> {src_sig[0]} files)"
    target.addons_dir.mkdir(parents=True, exist_ok=True)
    if target.dest.exists():
        shutil.rmtree(target.dest)
    shutil.copytree(SOURCE_ADDON, target.dest)
    new_sig = _dir_signature(target.dest)
    if new_sig != src_sig:
        return f"SYNC MISMATCH after copy (src={src_sig[0]} dst={new_sig[0]})"
    return f"synced ({new_sig[0]} files)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list detected installs and exit")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    parser.add_argument("--version", help="only act on this version (e.g. '4.5')")
    args = parser.parse_args()

    if not SOURCE_ADDON.exists():
        print(f"ERROR: source addon tree not found at {SOURCE_ADDON}", file=sys.stderr)
        return 2

    targets = detect_targets()
    if args.version:
        targets = [t for t in targets if t.version == args.version]

    if not targets:
        print("No Blender installs detected under %APPDATA%/Blender Foundation/Blender.")
        return 1

    print(f"Source: {SOURCE_ADDON}")
    print(f"Detected {len(targets)} target(s):")
    for t in targets:
        bin_note = str(t.binary) if t.binary else "(no binary located)"
        print(f"  - Blender {t.version}")
        print(f"      addons dir : {t.addons_dir}")
        print(f"      binary     : {bin_note}")

    if args.list:
        return 0

    print()
    rc = 0
    for t in targets:
        status = sync_target(t, dry_run=args.dry_run)
        print(f"  [{t.version}] {status}")
        if "MISMATCH" in status:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
