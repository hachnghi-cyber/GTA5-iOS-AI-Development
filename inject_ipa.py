#!/usr/bin/env python3
"""Add a separately compiled iOS dylib to the exact v11.2 IPA.

Only edits the main GTA5 executable's unused Mach-O *header padding* and adds
the dylib as a Frameworks file. It does not modify libgtacompat, game content,
localizations, or the user's current Trainer/Menyoo buttons.

The result is UNSIGNED and MUST be signed correctly before installation.
"""
from __future__ import annotations

import argparse
import hashlib
import plistlib
import struct
import sys
import zipfile
from pathlib import Path

MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_EXECUTE = 2
MH_DYLIB = 6
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC
LC_ID_DYLIB = 0xD
LC_CODE_SIGNATURE = 0x1D
INJECTED_NAME = "GTA5CustomButtons.dylib"
INSTALL_NAME = "@executable_path/Frameworks/" + INJECTED_NAME
GAME_EXE = "Payload/GTAV.app/GTA5"
GAME_PLIST = "Payload/GTAV.app/Info.plist"
DEST_DYLIB = "Payload/GTAV.app/Frameworks/" + INJECTED_NAME


class MachOError(ValueError):
    pass


def read_macho_header(data: bytes):
    if len(data) < 32:
        raise MachOError("Mach-O header truncated")
    magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = (
        struct.unpack_from("<IiiIIIII", data)
    )
    if magic != MH_MAGIC_64 or cputype != CPU_TYPE_ARM64:
        raise MachOError("Expected unencrypted arm64 Mach-O 64-bit, not fat/other arch")
    if ncmds > 500 or 32 + sizeofcmds > len(data):
        raise MachOError("Invalid load command size/count")
    return filetype, ncmds, sizeofcmds


def commands(data: bytes):
    _, count, size = read_macho_header(data)
    p = 32
    for _ in range(count):
        if p + 8 > 32 + size:
            raise MachOError("Truncated load command")
        cmd, length = struct.unpack_from("<II", data, p)
        if length < 8 or length % 8 or p + length > 32 + size:
            raise MachOError("Bad load command length")
        yield cmd, data[p:p + length]
        p += length
    if p != 32 + size:
        raise MachOError("Load command byte count mismatch")


def get_dylib_names(data: bytes):
    result = []
    for cmd, raw in commands(data):
        if cmd not in (LC_LOAD_DYLIB, LC_ID_DYLIB):
            continue
        if len(raw) < 24:
            raise MachOError("Dylib load command is truncated")
        name_offset = struct.unpack_from("<I", raw, 8)[0]
        if name_offset >= len(raw):
            raise MachOError("Dylib path offset beyond load command")
        result.append(raw[name_offset:].split(b"\0", 1)[0].decode("utf-8"))
    return result


def earliest_section_offset(data: bytes) -> int:
    first = len(data)
    for cmd, raw in commands(data):
        if cmd != LC_SEGMENT_64:
            continue
        if len(raw) < 72:
            raise MachOError("Segment command too small")
        nsects = struct.unpack_from("<I", raw, 64)[0]
        if len(raw) < 72 + 80 * nsects:
            raise MachOError("Segment sections truncated")
        for j in range(nsects):
            sect = 72 + j * 80
            offset = struct.unpack_from("<I", raw, sect + 48)[0]
            flags = struct.unpack_from("<I", raw, sect + 64)[0]
            is_zerofill = (flags & 0xFF) in (1, 12, 18)
            if offset > 0 and not is_zerofill:
                first = min(first, offset)
    return first


def assert_valid_library(data: bytes):
    filetype, _, _ = read_macho_header(data)
    if filetype != MH_DYLIB:
        raise MachOError("Expected an arm64 dylib compiled for iOS")


def add_load_command(source: bytes) -> bytes:
    filetype, ncmds, size = read_macho_header(source)
    if filetype != MH_EXECUTE:
        raise MachOError("Cannot inject a dylib into a non-executable Mach-O")
    if INSTALL_NAME in get_dylib_names(source):
        raise MachOError("Custom button dylib already injected")

    encoded_name = INSTALL_NAME.encode("utf-8") + b"\0"
    length = (24 + len(encoded_name) + 7) & ~7
    load = struct.pack("<IIIIII", LC_LOAD_DYLIB, length, 24, 0, 0x10000, 0x10000)
    load += encoded_name.ljust(length - 24, b"\0")

    end = 32 + size
    first_section = earliest_section_offset(source)
    if end + length > first_section:
        raise MachOError("No safe Mach-O header room. Refusing to shift code/data")
    if any(source[end:end + length]):
        raise MachOError("Mach-O header padding is not empty. Refusing to overwrite")

    result = bytearray(source)
    result[end:end + length] = load
    struct.pack_into("<I", result, 16, ncmds + 1)
    struct.pack_into("<I", result, 20, size + length)
    if INSTALL_NAME not in get_dylib_names(result):
        raise MachOError("New dylib command failed post-write readback")
    if bytes(result[end + length:]) != source[end + length:]:
        raise AssertionError("Unexpected executable modification outside header")
    return bytes(result)


def process_ipa(input_path: Path, dylib_path: Path, output_path: Path):
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Output cannot overwrite source IPA")
    dylib = dylib_path.read_bytes()
    assert_valid_library(dylib)
    with zipfile.ZipFile(input_path, "r") as original:
        paths = original.namelist()
        if paths.count(GAME_EXE) != 1 or paths.count(GAME_PLIST) != 1:
            raise ValueError("Expected exact GTAV.app executable and Info.plist")
        if DEST_DYLIB in paths:
            raise ValueError("Custom dylib already present; will not overwrite")
        info = plistlib.loads(original.read(GAME_PLIST))
        if info.get("CFBundleExecutable") != "GTA5":
            raise ValueError("Unexpected GTA executable name")
        exe = original.read(GAME_EXE)
        patched_exe = add_load_command(exe)
        with zipfile.ZipFile(output_path, "w", allowZip64=True) as result:
            result.comment = original.comment
            for item in original.infolist():
                result.writestr(item, patched_exe if item.filename == GAME_EXE
                                else original.read(item.filename))
            result.writestr(DEST_DYLIB, dylib, compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=6)

    with zipfile.ZipFile(input_path) as original, zipfile.ZipFile(output_path) as result:
        if result.testzip() is not None:
            raise ValueError("Output IPA contains corrupt ZIP members")
        assert result.namelist() == original.namelist() + [DEST_DYLIB]
        assert get_dylib_names(result.read(GAME_EXE)).count(INSTALL_NAME) == 1
        for item in original.infolist():
            if item.filename == GAME_EXE:
                continue
            if original.getinfo(item.filename).CRC != result.getinfo(item.filename).CRC:
                raise AssertionError("Original file changed: " + item.filename)
        print("COMPLETE: structure verified; unsigned IPA =", output_path)
        print("Main executable size: unchanged", len(exe))
        print("All existing members preserved byte-for-byte except GTA5 header")
        print("Added:", DEST_DYLIB)
        print("SHA256 of output:", hashlib.sha256(output_path.read_bytes()).hexdigest())
        print("IMPORTANT: must re-sign; NOT tested on a physical iPhone")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--dylib", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    process_ipa(args.ipa, args.dylib, args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
