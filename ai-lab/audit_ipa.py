#!/usr/bin/env python3
"""Static IPA audit. Never extracts or executes game content."""
import argparse
import hashlib
import json
import plistlib
import struct
import zipfile
from pathlib import Path, PurePosixPath

MAX_ITEMS = 200000
MACHO_SAMPLE = 1048576
MAGIC64 = {b"\xcf\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">"}

def is_unsafe_path(name):
    return name.startswith("/") or "\\" in name or "\0" in name or ".." in PurePosixPath(name).parts

def parse_macho(data):
    if len(data) < 32 or data[:4] not in MAGIC64:
        return None
    order = MAGIC64[data[:4]]
    _, cpu, _, kind, ncmds, sizeofcmds, _, _ = struct.unpack_from(order + "IIIIIIII", data)
    result = {"kind": "thin64", "cpu_type": hex(cpu), "is_arm64": cpu == 0x0100000c,
              "file_type": kind, "load_commands": ncmds, "dylibs": [], "uuid": None}
    offset = 32
    for i in range(min(ncmds, 10000)):
        if offset + 8 > min(len(data), 32 + sizeofcmds):
            result["warning"] = "load-commands-truncated"
            break
        cmd, size = struct.unpack_from(order + "II", data, offset)
        if size < 8 or offset + size > min(len(data), 32 + sizeofcmds):
            result["warning"] = "invalid-or-truncated-command"
            break
        base = cmd & 0x7fffffff
        if base in (0xc, 0x18, 0x1f, 0x23, 0x20) and size >= 24:
            nameoffset = struct.unpack_from(order + "I", data, offset + 8)[0]
            if 8 <= nameoffset < size:
                start = offset + nameoffset
                result["dylibs"].append(data[start:offset + size].split(b"\0")[0].decode("utf-8", "replace"))
        if base == 0x1b and size >= 24:
            result["uuid"] = data[offset + 8:offset + 24].hex()
        offset += size
    return result

def audit(path):
    path = Path(path)
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    result = {"file": path.name, "sha256": sha.hexdigest(), "status": "static-only",
              "issues": [], "app_bundles": [], "macho": []}
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if len(entries) > MAX_ITEMS:
            raise ValueError("too-many-zip-entries")
        names = set()
        for item in entries:
            if is_unsafe_path(item.filename):
                result["issues"].append("unsafe-path: " + item.filename[:160])
            if item.filename in names:
                result["issues"].append("duplicate-path: " + item.filename[:160])
            names.add(item.filename)
            if item.filename.startswith("Payload/") and item.filename.count("/") == 2 and item.filename.endswith(".app/Info.plist"):
                if item.file_size > 2 * 1024 * 1024:
                    result["issues"].append("oversized-plist")
                    continue
                try:
                    obj = plistlib.loads(z.read(item))
                    result["app_bundles"].append({
                        "path": item.filename, "bundle_id": obj.get("CFBundleIdentifier"),
                        "executable": obj.get("CFBundleExecutable"),
                        "minimum_os": obj.get("MinimumOSVersion")})
                except Exception as exc:
                    result["issues"].append("bad-plist: " + type(exc).__name__)
        inspected = 0
        for item in entries:
            if inspected >= 250:
                break
            name = item.filename
            if item.is_dir() or is_unsafe_path(name):
                continue
            if not (name.endswith((".dylib", ".so")) or "/Frameworks/" in name or
                    any(name == b["path"].removesuffix("Info.plist") + str(b["executable"])
                        for b in result["app_bundles"])):
                continue
            with z.open(item) as f:
                parsed = parse_macho(f.read(min(MACHO_SAMPLE, item.file_size)))
            inspected += 1
            if parsed:
                result["macho"].append({"path": name, **parsed})
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("ipa")
    p.add_argument("--output")
    args = p.parse_args()
    output = json.dumps(audit(args.ipa), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(output, encoding="utf-8")
    print(output)

if __name__ == "__main__":
    main()
