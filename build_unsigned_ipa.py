#!/usr/bin/env python3
"""Repack an *unsigned* GTA V iOS v11.3 CustomTouch test IPA on Linux/macOS.

This intentionally does not attempt iOS code signing. It patches only the
Mach-O load-command header in verified v11.3, then adds one already-compiled
arm64 dylib. The resulting IPA MUST be re-signed before installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import struct
import tempfile
import zipfile


EXE = "Payload/GTAV.app/GTA5"
COMPAT = "Payload/GTAV.app/Frameworks/libgtacompat.dylib"
PLUGIN = "Payload/GTAV.app/Frameworks/libCustomTouch.dylib"
DYLIB_NAME = b"@executable_path/Frameworks/libCustomTouch.dylib\x00"
EXPECTED_EXE_SHA = "606aa87f9c22b40f167ae2bdf00ddf451b957801efb27169e38fa7af5c673aeb"
EXPECTED_COMPAT_SHA = "992148cae5866e20768b1e054075cbc7b9480731ffc3996a4a6f69d61177cb64"
MACHO_MAGIC = 0xFEEDFACF
ARM64 = 0x0100000C
LC_LOAD_DYLIB = 0xC
LC_SEGMENT_64 = 0x19


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_commands(image: bytes):
    if len(image) < 32:
        raise ValueError("Truncated Mach-O")
    magic, cpu, _, filetype, count, size, _, _ = struct.unpack_from("<8I", image)
    if magic != MACHO_MAGIC or cpu != ARM64:
        raise ValueError("Not an ARM64 Mach-O")
    end = 32 + size
    if end > len(image):
        raise ValueError("Invalid Mach-O command size")
    position = 32
    commands = []
    for _ in range(count):
        if position + 8 > end:
            raise ValueError("Corrupt load-command header")
        command, length = struct.unpack_from("<II", image, position)
        if length < 8 or length % 8 or position + length > end:
            raise ValueError("Corrupt load command")
        commands.append((command, position, length))
        position += length
    if position != end:
        raise ValueError("Unexpected bytes inside Mach-O load-command table")
    return filetype, commands, end


def patch_executable(original: bytes) -> bytes:
    if digest(original) != EXPECTED_EXE_SHA:
        raise ValueError("GTA5 executable differs from verified v11.3; refusing patch")
    filetype, commands, command_end = load_commands(original)
    if filetype != 2:  # MH_EXECUTE
        raise ValueError("GTA5 is not a Mach-O executable")
    nearest_section = len(original)
    for command, position, length in commands:
        if command in (0xC, 0xD, 0x18, 0x1F, 0x23):
            if length >= 24:
                name_offset = struct.unpack_from("<I", original, position + 8)[0]
                if 24 <= name_offset < length:
                    name = original[position + name_offset:position + length].split(b"\x00", 1)[0]
                    if b"libCustomTouch.dylib" in name:
                        raise ValueError("GTA5 already loads libCustomTouch.dylib")
        if command == LC_SEGMENT_64:
            if length < 72:
                raise ValueError("Invalid 64-bit segment")
            sections = struct.unpack_from("<I", original, position + 64)[0]
            if 72 + 80 * sections > length:
                raise ValueError("Invalid section table")
            for section in range(sections):
                section_position = position + 72 + 80 * section
                section_size = struct.unpack_from("<Q", original, section_position + 40)[0]
                section_offset = struct.unpack_from("<I", original, section_position + 48)[0]
                if section_size and section_offset:
                    nearest_section = min(nearest_section, section_offset)

    length = (24 + len(DYLIB_NAME) + 7) & ~7
    if command_end + length > nearest_section:
        raise ValueError("Insufficient verified header padding for LC_LOAD_DYLIB")
    if any(original[command_end:command_end + length]):
        raise ValueError("Header padding is not zero; refusing to overwrite")
    load_command = struct.pack("<6I", LC_LOAD_DYLIB, length, 24, 0, 0x10000, 0x10000)
    load_command += DYLIB_NAME
    load_command += bytes(length - len(load_command))
    modified = bytearray(original)
    count = struct.unpack_from("<I", modified, 16)[0]
    size = struct.unpack_from("<I", modified, 20)[0]
    struct.pack_into("<II", modified, 16, count + 1, size + length)
    modified[command_end:command_end + length] = load_command
    result = bytes(modified)
    _, new_commands, _ = load_commands(result)
    if len(new_commands) != len(commands) + 1 or new_commands[-1][0] != LC_LOAD_DYLIB:
        raise RuntimeError("Postpatch Mach-O structure check failed")
    return result


def create_ipa(ipa: pathlib.Path, plugin_zip: pathlib.Path, output: pathlib.Path) -> dict:
    if output.exists() or output == ipa or output == plugin_zip:
        raise ValueError("Output must be a new file; existing inputs cannot be overwritten")
    with zipfile.ZipFile(plugin_zip) as plugin_archive:
        if plugin_archive.namelist() != ["libCustomTouch.dylib"]:
            raise ValueError("Expected artifact ZIP containing only libCustomTouch.dylib")
        dylib = plugin_archive.read("libCustomTouch.dylib")
    dylib_type, _, _ = load_commands(dylib)
    if dylib_type != 6 or b"hachnghi.customtouch.v113" not in dylib:
        raise ValueError("Artifact is not the expected v11.3 CustomTouch ARM64 dylib")

    output.parent.mkdir(parents=True, exist_ok=True)
    changed = {EXE, PLUGIN}
    original_hashes = {}
    with zipfile.ZipFile(ipa, "r") as zin:
        names = zin.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate IPA entry paths")
        if EXE not in names or COMPAT not in names or PLUGIN in names:
            raise ValueError("Unexpected IPA structure or existing CustomTouch plugin")
        if digest(zin.read(COMPAT)) != EXPECTED_COMPAT_SHA:
            raise ValueError("libgtacompat differs from the verified v11.3 build")
        patched_executable = patch_executable(zin.read(EXE))

        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".ipa", delete=True) as temp:
            with zipfile.ZipFile(temp.name, "w") as zout:
                zout.comment = zin.comment
                for info in zin.infolist():
                    original_payload = zin.read(info)
                    payload = patched_executable if info.filename == EXE else original_payload
                    original_hashes[info.filename] = digest(original_payload)
                    zout.writestr(info, payload)
                new_info = zipfile.ZipInfo(PLUGIN, date_time=(2026, 11, 10, 0, 0, 0))
                new_info.compress_type = zipfile.ZIP_DEFLATED
                new_info.external_attr = (0o100755 << 16)
                new_info.create_system = 3
                zout.writestr(new_info, dylib)

            with zipfile.ZipFile(temp.name) as result:
                if result.testzip() is not None:
                    raise RuntimeError("Output IPA archive is corrupt")
                if set(result.namelist()) != set(names) | {PLUGIN}:
                    raise RuntimeError("Output IPA lost or gained an unexpected file")
                for name in names:
                    if name not in changed and digest(result.read(name)) != original_hashes[name]:
                        raise RuntimeError(f"Unrelated IPA resource changed: {name}")
                if result.read(EXE) != patched_executable or result.read(PLUGIN) != dylib:
                    raise RuntimeError("Patched executable or plugin mismatch")

            # Commit only after all validation succeeds. Never overwrite.
            with output.open("xb") as destination:
                temp.seek(0)
                shutil.copyfileobj(temp, destination, length=1 << 20)

    report = {
        "input_ipa": ipa.name,
        "input_ipa_sha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
        "input_plugin_sha256": digest(dylib),
        "output_ipa": output.name,
        "output_ipa_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "changed_or_added_entries": sorted(changed),
        "unchanged_entries_verified": len(original_hashes) - 1,
        "status": "UNSIGNED - installation requires a valid full IPA re-sign",
        "device_tested": False,
    }
    return report


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ipa", required=True, type=pathlib.Path)
    cli.add_argument("--plugin-zip", required=True, type=pathlib.Path)
    cli.add_argument("--output", required=True, type=pathlib.Path)
    args = cli.parse_args()
    report = create_ipa(args.ipa.resolve(), args.plugin_zip.resolve(), args.output.resolve())
    args.output.with_suffix(".report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
