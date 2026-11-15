#!/usr/bin/env python3
"""Winstom 0.7.171 lmx ARM64 Objective-C method map (metadata only).

READ-ONLY. Refuses a different Mach-O fingerprint: class/selector addresses
below are not stable across recompiles, ASLR, or GTA5 v13.3 executable builds.
Does not run, decrypt, inject, disassemble, or extract third-party code.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_LMX_SHA256 = "dd2a00535b4df1118ce5f94bab1434c052233de4d9a04e3d153f5707d0404ec5"
EXPECTED_LMX_UUID = "003f682bd578332c840e7b789cd594dc"
CLASSLIST = (0x3fd688, 26)
TEXT_METHLIST = (0x37a310, 0x37b948)
REBASE_TARGET_BITS = (1 << 36) - 1


def decode_rebase(raw):
    """DYLD_CHAINED_PTR_64_OFFSET with bind=0; imports are NOT local pointers."""
    if raw == 0 or raw >> 63:
        return None
    return raw & REBASE_TARGET_BITS


def resolve(data):
    if len(data) < 0x410000 or data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("not expected thin64 Winstom lmx")
    if hashlib.sha256(data).hexdigest() != EXPECTED_LMX_SHA256:
        raise ValueError("Winstom lmx SHA-256 mismatch; DO NOT reuse offsets")
    if struct.unpack_from("<I", data, 4)[0] != 0x0100000C:
        raise ValueError("not ARM64")
    uuid = None
    cmd_count = struct.unpack_from("<I", data, 16)[0]
    off = 32
    for _ in range(cmd_count):
        cmd, length = struct.unpack_from("<II", data, off)
        if length < 8 or off + length > len(data):
            raise ValueError("malformed Mach-O load commands")
        if cmd == 0x1b and length >= 24:
            uuid = data[off + 8:off + 24].hex()
        off += length
    if uuid != EXPECTED_LMX_UUID:
        raise ValueError("unexpected Mach-O UUID")
    def readq(p):
        if not 0 <= p <= len(data)-8: raise ValueError("pointer out of bounds")
        return decode_rebase(struct.unpack_from("<Q", data, p)[0])
    def text(p):
        if p is None: return None
        if not 0 <= p < len(data): raise ValueError("cstring outside image")
        e = data.find(b"\0", p, min(p+512, len(data)))
        if e < 0: raise ValueError("unterminated class/selector")
        return data[p:e].decode("utf-8", "replace")
    classes = []
    for i in range(CLASSLIST[1]):
        class_va = readq(CLASSLIST[0] + i * 8)
        if class_va is None: continue
        ro_va = readq(class_va + 32)
        if ro_va is None: continue
        class_name = text(readq(ro_va + 24))
        list_va = readq(ro_va + 32)
        methods = []
        if list_va is not None:
            if not TEXT_METHLIST[0] <= list_va < TEXT_METHLIST[1]:
                raise ValueError("method list outside expected range")
            flags, count = struct.unpack_from("<II", data, list_va)
            if flags & 0x80000000 == 0 or flags & 0xffff != 12 or count > 512:
                raise ValueError("unsupported method-list representation")
            if list_va + 8 + count * 12 > TEXT_METHLIST[1]:
                raise ValueError("method list beyond section")
            for j in range(count):
                entry = list_va + 8 + j * 12
                name_delta, types_delta, imp_delta = struct.unpack_from("<iii", data, entry)
                name_va = entry + name_delta
                if not flags & 0x40000000:
                    name_va = readq(name_va)
                imp = entry + 8 + imp_delta
                methods.append({"selector": text(name_va), "imp_vmaddr": f"0x{imp:x}"})
        classes.append({"class": class_name, "methods": methods})
    return {"source": "Winstom-0.7.171 lmx.dylib", "sha256": EXPECTED_LMX_SHA256,
            "uuid": EXPECTED_LMX_UUID, "class_count": len(classes),
            "class_linked_method_count": sum(len(c["methods"]) for c in classes),
            "classes": classes,
            "limitations": "ObjC metadata only; implementation address before ASLR; not a v13.3 hook"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lmx", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = resolve(args.lmx.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("static-only classes", result["class_count"], "methods", result["class_linked_method_count"])


if __name__ == "__main__":
    main()
