#!/usr/bin/env python3
"""Experimental, opt-in Mach-O injection; never overwrites the original IPA.

Requires macOS + Xcode code signing tools and the dylib built by
build_on_mac.sh. The v11.3-specific header patch is checked without LIEF.
Output is ad-hoc signed for testing / subsequent sideload resigning,
NOT a production Apple-distribution signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from build_unsigned_ipa import patch_executable

LIBRARY_PATH = "@executable_path/Frameworks/libCustomTouch.dylib"
EXTRA_FILE = "Payload/GTAV.app/Frameworks/libCustomTouch.dylib"
ALLOW_MUTATIONS = {
    "Payload/GTAV.app/GTA5",
    "Payload/GTAV.app/_CodeSignature/CodeResources",
    EXTRA_FILE,
}


def checksum(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def items_from_folder(base: pathlib.Path) -> dict[str, str]:
    return {
        p.relative_to(base).as_posix(): checksum(p)
        for p in base.rglob("*")
        if p.is_file()
    }


def extract_safe(archive: pathlib.Path, destination: pathlib.Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for entry in zf.infolist():
            name = pathlib.PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != "Payload":
                raise ValueError(f"Unsafe or unexpected IPA entry: {entry.filename!r}")
            if stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError(f"Symlink not supported for safe repacking: {entry.filename!r}")
        zf.extractall(destination)


def patch_macho(executable: pathlib.Path) -> None:
    executable.write_bytes(patch_executable(executable.read_bytes()))
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def call(*args: str) -> None:
    subprocess.run(args, check=True)


def original_entitlements(app: pathlib.Path, temporary: pathlib.Path) -> pathlib.Path | None:
    """Keep entitlement data available for re-signing, if a signature has it."""
    result = subprocess.run(
        ["codesign", "-d", "--entitlements", "-", str(app)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout
    if not (raw.startswith(b"<?xml") or raw.startswith(b"bplist")):
        return None
    output = temporary / "original-entitlements.plist"
    output.write_bytes(raw)
    return output


def repack(working: pathlib.Path, output_ipa: pathlib.Path) -> None:
    with zipfile.ZipFile(output_ipa, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(working.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(working).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=pathlib.Path, required=True)
    parser.add_argument("--dylib", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    original, dylib, output = args.ipa.resolve(), args.dylib.resolve(), args.output.resolve()
    if sys.platform != "darwin":
        parser.error("IPA signing/packaging requires macOS; source-only checks work on Linux")
    if not original.is_file() or not dylib.is_file():
        parser.error("IPA or compiled dylib does not exist")
    if output == original or output.exists():
        parser.error("Output must be a new, nonexistent IPA path")
    if not shutil.which("codesign"):
        parser.error("codesign is required on macOS")

    with tempfile.TemporaryDirectory(prefix="v113-custom-") as temporary:
        working = pathlib.Path(temporary)
        extract_safe(original, working)
        before = items_from_folder(working)
        app = working / "Payload" / "GTAV.app"
        executable = app / "GTA5"
        if not executable.is_file() or not (app / "Frameworks/libgtacompat.dylib").is_file():
            raise RuntimeError("Unexpected IPA structure (GTAV.app or libgtacompat missing)")
        entitlements = original_entitlements(app, working)
        shutil.copy2(dylib, app / "Frameworks/libCustomTouch.dylib")
        patch_macho(executable)
        # Original entitlements and signing identity must be applied again by
        # the user's signing tool (e.g. SideStore); these signatures are ad-hoc.
        call("codesign", "--force", "--sign", "-", "--timestamp=none", str(app / "Frameworks/libCustomTouch.dylib"))
        sign_command = ["codesign", "--force", "--sign", "-", "--timestamp=none"]
        if entitlements is not None:
            sign_command += ["--entitlements", str(entitlements)]
        call(*sign_command, str(app))
        call("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app))

        after = items_from_folder(working)
        changed = {k for k in after.keys() | before.keys() if before.get(k) != after.get(k)}
        # The extracted entitlement file stays outside the IPA (removed below)
        # and is not an application resource.
        unexpected = sorted(changed - (ALLOW_MUTATIONS | {"original-entitlements.plist"}))
        if unexpected:
            raise RuntimeError(f"Unexpected files changed in IPA: {unexpected}")
        if entitlements is not None:
            entitlements.unlink()
        repack(working, output)
        with zipfile.ZipFile(output) as zf:
            if zf.testzip() is not None:
                raise RuntimeError("Output ZIP integrity check failed")
        report = {
            "original_ipa_sha256": checksum(original),
            "patched_ipa_sha256": checksum(output),
            "changed_files": sorted(changed),
            "note": "Ad-hoc signed research build. Requires valid sideload signing and device test.",
        }
        output.with_suffix(".report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
