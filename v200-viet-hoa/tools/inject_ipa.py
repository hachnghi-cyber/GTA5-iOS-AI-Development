#!/usr/bin/env python3
"""Experimental structural Mach-O dylib injection; unsigned IPA only.

Inputs must be user-supplied locally or provided through authorized private storage.
This does not bypass application or Online integrity checks.
"""
import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import struct
import zipfile

BASE_SHA256 = "a267c2683ce9df5cd68bc3498ade9282ee6d7dd201a2f0b2afeae0f64b0f587e"
NVP_SHA256 = "a66869101865158c6d480834a7fec0d17ef5170c5e5c33cd037aa8507e4bfaea"
DYLIB_NAME = "libVietHoaBoot.dylib"
DYLIB_LOAD = "@executable_path/Frameworks/" + DYLIB_NAME
MH_MAGIC_64, CPU_ARM64, MH_EXECUTE, MH_DYLIB = 0xFEEDFACF, 0x0100000C, 2, 6
LC_SEGMENT_64, LC_LOAD_DYLIB, LC_ID_DYLIB = 0x19, 0xC, 0xD


def sha256_file(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def iter_macho_commands(data, filetype):
    if len(data) < 32:
        raise ValueError("Incomplete Mach-O header")
    magic, cpu, subtype, actual_type, count, length, flags, reserved = struct.unpack_from("<IiiIIIII", data)
    if magic != MH_MAGIC_64 or cpu != CPU_ARM64 or actual_type != filetype:
        raise ValueError("Expected thin ARM64 Mach-O file of requested type")
    end = 32 + length
    if count > 512 or end > len(data):
        raise ValueError("Invalid Mach-O commands")
    at = 32
    cmds = []
    for _ in range(count):
        if at + 8 > end:
            raise ValueError("Truncated load command")
        cmd, size = struct.unpack_from("<II", data, at)
        if size < 8 or size % 8 or at + size > end:
            raise ValueError("Invalid Mach-O command size")
        cmds.append((at, cmd, size))
        at += size
    if at != end:
        raise ValueError("Mismatched Mach-O load-command size")
    return count, length, end, cmds


def macho_info(data):
    count, length, end, commands = iter_macho_commands(data, MH_EXECUTE)
    first_section = len(data)
    libraries = []
    for at, cmd, size in commands:
        if cmd == LC_SEGMENT_64:
            if size < 72:
                raise ValueError("Malformed segment")
            section_count = struct.unpack_from("<I", data, at + 64)[0]
            if 72 + section_count * 80 > size:
                raise ValueError("Malformed section table")
            for index in range(section_count):
                section = at + 72 + index * 80
                sec_size = struct.unpack_from("<Q", data, section + 40)[0]
                sec_offset = struct.unpack_from("<I", data, section + 48)[0]
                if sec_size and sec_offset:
                    first_section = min(first_section, sec_offset)
        if cmd == LC_LOAD_DYLIB:
            name_offset = struct.unpack_from("<I", data, at + 8)[0]
            if not 24 <= name_offset < size:
                raise ValueError("Bad library name offset")
            name = data[at + name_offset : at + size].split(b"\0", 1)[0].decode()
            libraries.append(name)
    return {"ncmds": count, "sizeofcmds": length, "command_end": end,
            "first_section": first_section, "padding": first_section - end,
            "libraries": libraries}


def patch_macho_load(data):
    before = macho_info(data)
    if DYLIB_LOAD in before["libraries"]:
        raise ValueError("Already injected")
    name = DYLIB_LOAD.encode() + b"\0"
    size = (24 + len(name) + 7) & ~7
    start = before["command_end"]
    if before["padding"] < size or any(data[start:start + size]):
        raise ValueError("No safe zero-filled command header padding")
    command = struct.pack("<IIIIII", LC_LOAD_DYLIB, size, 24, 2, 0, 0) + name
    command += b"\0" * (size - len(command))
    patched = bytearray(data)
    patched[start : start + size] = command
    struct.pack_into("<II", patched, 16, before["ncmds"] + 1, before["sizeofcmds"] + size)
    result = bytes(patched)
    after = macho_info(result)
    if (len(data) != len(result) or before["first_section"] != after["first_section"]
            or after["ncmds"] != before["ncmds"] + 1 or DYLIB_LOAD not in after["libraries"]):
        raise AssertionError("Mach-O patch verification failed")
    return result, before, after


def validate_dylib(path):
    data = Path(path).read_bytes()
    _, _, _, cmds = iter_macho_commands(data, MH_DYLIB)
    names = []
    for at, cmd, size in cmds:
        if cmd != LC_ID_DYLIB:
            continue
        offset = struct.unpack_from("<I", data, at + 8)[0]
        if not 24 <= offset < size:
            raise ValueError("Invalid dylib install name offset")
        names.append(data[at + offset : at + size].split(b"\0", 1)[0].decode())
    if names != [DYLIB_LOAD]:
        raise ValueError("Unexpected LC_ID_DYLIB install name")


def make_ipa(original_ipa, dylib, pack, output):
    if sha256_file(original_ipa) != BASE_SHA256:
        raise ValueError("Base IPA SHA-256 mismatch")
    if sha256_file(pack) != NVP_SHA256:
        raise ValueError("Vietnamese NVP SHA-256 mismatch")
    validate_dylib(dylib)
    with zipfile.ZipFile(original_ipa) as source:
        paths = source.namelist()
        plist_path = next((p for p in paths if p.endswith(".app/Info.plist")), None)
        if plist_path is None:
            raise ValueError("Missing Info.plist")
        prefix = plist_path.rsplit("/", 1)[0] + "/"
        metadata = plistlib.loads(source.read(plist_path))
        if metadata.get("CFBundleIdentifier") != "io.github.playgta5ios.app":
            raise ValueError("Unexpected bundle identifier")
        executable = prefix + metadata["CFBundleExecutable"]
        if executable not in paths:
            raise ValueError("Missing executable")
        if any(prefix + p in paths for p in ["Frameworks/" + DYLIB_NAME, "VietnameseAccented.nvp"]):
            raise ValueError("Already contains patch assets")
        patched, old, new = patch_macho_load(source.read(executable))
        temp = str(output) + ".building"
        try:
            with zipfile.ZipFile(temp, "w", allowZip64=True) as target:
                for info in source.infolist():
                    if "/_CodeSignature/" in info.filename:
                        continue
                    target.writestr(info, patched if info.filename == executable else source.read(info.filename))
                target.write(dylib, prefix + "Frameworks/" + DYLIB_NAME, compress_type=zipfile.ZIP_DEFLATED)
                target.write(pack, prefix + "VietnameseAccented.nvp", compress_type=zipfile.ZIP_DEFLATED)
            with zipfile.ZipFile(temp) as result:
                bad = result.testzip()
                if bad:
                    raise ValueError("ZIP CRC mismatch: " + bad)
                assert DYLIB_LOAD in macho_info(result.read(executable))["libraries"]
            os.replace(temp, output)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return {"before": old["ncmds"], "after": new["ncmds"],
                "output": str(output), "signed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--nvp", type=Path)
    parser.add_argument("--dylib", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    if args.inspect_only:
        with zipfile.ZipFile(args.ipa) as source:
            plist = next(p for p in source.namelist() if p.endswith(".app/Info.plist"))
            meta = plistlib.loads(source.read(plist))
            executable = plist.rsplit("/", 1)[0] + "/" + meta["CFBundleExecutable"]
            print(macho_info(source.read(executable)))
            print("IPA SHA256:", sha256_file(args.ipa))
        return
    if not all([args.dylib, args.nvp, args.output]):
        parser.error("--dylib, --nvp and --output required")
    print(make_ipa(args.ipa, args.dylib, args.nvp, args.output))
    print("Unsigned experimental IPA. Re-sign and test on device. Online integrity may reject it.")


if __name__ == "__main__":
    main()
