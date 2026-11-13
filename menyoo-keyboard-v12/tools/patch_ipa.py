#!/usr/bin/env python3
"""Version-locked Mach-O chained-import rebinding. No ARM64 opcode edits."""
import hashlib
import json
import struct
import zipfile
from pathlib import Path
import argparse

MENYOO = "Payload/GTAV.app/Frameworks/Menyoo.shv.dylib"
BRIDGE = "Payload/GTAV.app/Frameworks/MenyooKeyboardBridge.dylib"
EXPECTED_IPA = "23c039cb59e24f0107243a32252a3a60fbca1c934ac482d285109c323132f0dc"
EXPECTED_MENYOO = "7dab057f15d87e50ebc5512fd4be3f5535ae6a732ca68c61294d3037d52eeee8"
BRIDGE_NAME = b"@rpath/MenyooKeyboardBridge.dylib\x00"
IMPORTS = {"_nativeInit", "_nativePush64", "_nativeCall"}
LC_LOAD_DYLIB = 0xC
LC_SEGMENT_64 = 0x19
LC_DYLD_CHAINED_FIXUPS = 0x80000034

def sha(b):
    return hashlib.sha256(b).hexdigest()

def u32(b, offset):
    return struct.unpack_from("<I", b, offset)[0]

def commands(b):
    if len(b) < 32 or b[:4] != b"\xcf\xfa\xed\xfe" or u32(b, 4) != 0x0100000c or u32(b, 12) != 6:
        raise ValueError("expected thin ARM64 MH_DYLIB")
    n, size = u32(b, 16), u32(b, 20)
    result, off = [], 32
    for _ in range(n):
        if off + 8 > len(b):
            raise ValueError("truncated Mach-O header")
        cmd, length = struct.unpack_from("<II", b, off)
        if length < 8 or length % 8 or off + length > len(b):
            raise ValueError("invalid load command")
        result.append((cmd, off, length))
        off += length
    if off != 32 + size:
        raise ValueError("inconsistent sizeofcmds")
    return result

def patch_menyoo(data):
    if sha(data) != EXPECTED_MENYOO:
        raise ValueError("Menyoo SHA mismatch; refusing patch for another version")
    b = bytearray(data)
    cmds = commands(b)
    dylibs = [(off, size) for c, off, size in cmds if c == LC_LOAD_DYLIB]
    if len(dylibs) != 6:
        raise ValueError("expected 6 dylib dependencies")
    first_off, first_size = dylibs[0]
    name_off = u32(b, first_off + 8)
    if bytes(b[first_off + name_off:first_off + first_size]).split(b"\x00")[0] != b"@rpath/ScriptHookV.dylib":
        raise ValueError("ScriptHookV is not dependency ordinal 1")
    text_offsets = []
    for cmd, off, length in cmds:
        if cmd == LC_SEGMENT_64:
            count = u32(b, off + 64)
            if off + 72 + 80 * count > off + length:
                raise ValueError("invalid section table")
            for j in range(count):
                section = off + 72 + j * 80
                if bytes(b[section:section + 16]).split(b"\x00")[0] == b"__text":
                    text_offsets.append(u32(b, section + 48))
    if not text_offsets:
        raise ValueError("missing __text")
    fixes = [off for c, off, size in cmds if c == LC_DYLD_CHAINED_FIXUPS]
    if len(fixes) != 1:
        raise ValueError("expected one chained fixups command")
    data_off, data_size = struct.unpack_from("<II", b, fixes[0] + 8)
    if data_off + data_size > len(b):
        raise ValueError("invalid chained fixups bounds")
    ver, starts, imp, syms, count, fmt, symfmt = struct.unpack_from("<7I", b, data_off)
    if (ver, fmt, symfmt) != (0, 1, 0):
        raise ValueError("unsupported chained imports format")
    found = {}
    for idx in range(count):
        off = data_off + imp + 4 * idx
        if off + 4 > data_off + data_size:
            raise ValueError("truncated chained import")
        word = u32(b, off)
        start = data_off + syms + (word >> 9)
        if start < data_off or start >= data_off + data_size:
            raise ValueError("invalid symbol string offset")
        symbol = bytes(b[start:data_off + data_size]).split(b"\x00")[0].decode("utf-8")
        if symbol in IMPORTS:
            if symbol in found or (word & 255) != 1:
                raise ValueError("duplicate/incorrect existing keyboard shim import")
            found[symbol] = off
    if set(found) != IMPORTS:
        raise ValueError(f"missing imports {IMPORTS - set(found)}")
    command_size = (24 + len(BRIDGE_NAME) + 7) & ~7
    header_end = 32 + u32(b, 20)
    if header_end + command_size > min(text_offsets) or any(b[header_end:header_end + command_size]):
        raise ValueError("no Mach-O header padding for dylib load command")
    new_command = bytearray(command_size)
    struct.pack_into("<6I", new_command, 0, LC_LOAD_DYLIB, command_size, 24, 2, 0, 0)
    new_command[24:24 + len(BRIDGE_NAME)] = BRIDGE_NAME
    b[header_end:header_end + command_size] = new_command
    struct.pack_into("<I", b, 16, u32(b, 16) + 1)
    struct.pack_into("<I", b, 20, u32(b, 20) + command_size)
    for name, pos in found.items():
        struct.pack_into("<I", b, pos, (u32(b, pos) & ~255) | 7)
    if len(commands(b)) != len(cmds) + 1:
        raise AssertionError("new Mach-O load command missing")
    diffs = [i for i, (x, y) in enumerate(zip(b, data)) if x != y]
    allowed = set(range(16, 24)) | set(range(header_end, header_end + command_size))
    for pos in found.values():
        allowed.update(range(pos, pos + 4))
    if not set(diffs) <= allowed:
        raise AssertionError("unexpected bytes modified")
    return bytes(b), {"input_sha256": sha(data), "patched_sha256": sha(b),
                       "bound_symbols": sorted(found), "import_offsets": found,
                       "new_dependency_ordinal": 7, "instruction_bytes_modified": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ipa", type=Path, required=True)
    ap.add_argument("--dylib", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if sha(args.ipa.read_bytes()) != EXPECTED_IPA:
        raise SystemExit("IPA SHA mismatch: only the exact user-supplied v12 IPA is accepted")
    dylib = args.dylib.read_bytes()
    if len(dylib) < 32 or dylib[:4] != b"\xcf\xfa\xed\xfe" or u32(dylib, 4) != 0x0100000c:
        raise SystemExit("bridge must be ARM64 Mach-O")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.ipa) as preflight:
        expected_shv = "f8272dc62894dc45bf0d8bc75ef6ff23c6b1ea35d22b6bc4a65fb7df62b6f176"
        shv_entry = "Payload/GTAV.app/Frameworks/ScriptHookV.dylib"
        if hashlib.sha256(preflight.read(shv_entry)).hexdigest() != expected_shv:
            raise SystemExit("Wrong v12 ScriptHookV ABI fingerprint")
    with zipfile.ZipFile(args.ipa) as src, zipfile.ZipFile(args.out, "w") as dest:
        if src.testzip() is not None or MENYOO not in src.namelist() or BRIDGE in src.namelist():
            raise ValueError("invalid base IPA layout")
        patched, detail = patch_menyoo(src.read(MENYOO))
        for info in src.infolist():
            dest.writestr(info, patched if info.filename == MENYOO else src.read(info.filename))
        bridge_info = zipfile.ZipInfo(BRIDGE)
        bridge_info.create_system = 3
        bridge_info.external_attr = (0o100755 << 16)
        bridge_info.compress_type = zipfile.ZIP_DEFLATED
        dest.writestr(bridge_info, dylib, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(args.out) as z:
        if z.testzip() is not None or z.read(MENYOO) != patched:
            raise AssertionError("output IPA validation failed")
    report = {"base_sha256": EXPECTED_IPA, "output_sha256": sha(args.out.read_bytes()),
              "bridge_sha256": sha(dylib), "binding_patch": detail,
              "codesigning": "REQUIRES_RE-SIGN", "iphone_tested": False}
    args.out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
