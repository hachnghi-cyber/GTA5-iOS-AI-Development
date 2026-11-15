#!/usr/bin/env python3
"""Read-only Winstom/GTA V iOS IPA structural audit and optional v13 comparison.

No code execution, asset extraction, decryption, or original-game files in output.
A filename, linked library, or keyword is not proof that RP works on a device.
"""
import argparse
import hashlib
import json
import plistlib
import re
import struct
import uuid
import zipfile
from pathlib import Path, PurePosixPath

MAX_ZIP_ITEMS = 200_000
MAX_BINARY_ITEMS = 256
MAX_BINARY_SIZE = 512 * 1024 * 1024
HEAD_SIZE = 1024 * 1024
BLOCK = 1024 * 1024
MARKERS = (
    b"police", b"cuff", b"escort", b"arrest", b"jail",
    b"roleplay", b"network", b"packet", b"rpc", b"rage",
    b"script", b"libgtacompat", b"winstom", b"fivem",
)
MACH64_MAGICS = {b"\xcf\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">"}
APP_INFO = re.compile(r"^Payload/[^/]+\.app/Info\.plist$")


def unsafe_path(name):
    return (
        name.startswith("/") or "\\" in name or "\x00" in name
        or ".." in PurePosixPath(name).parts
    )


def _c_string(command, offset):
    if offset < 8 or offset >= len(command):
        return None
    return command[offset:].split(b"\x00", 1)[0].decode("utf-8", "replace")


def macho_metadata(data):
    """Parse a bounded Mach-O header sample; never disassemble or execute it."""
    # zipfile audit passes mutable bytearray; uuid.UUID and dylib parsing need bytes.
    # Bounded to the first 1 MiB per candidate in audit_ipa().
    data = bytes(data)
    if len(data) < 32:
        return None
    magic = bytes(data[:4])  # zf streaming header is a bytearray, not hashable
    if magic in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
        endian = ">" if magic in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf") else "<"
        is64 = magic in (b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
        count = struct.unpack_from(endian + "I", data, 4)[0]
        arch_size = 32 if is64 else 20
        archs = []
        for i in range(min(count, 32)):
            pos = 8 + i * arch_size
            if pos + arch_size > len(data):
                break
            cpu = struct.unpack_from(endian + "I", data, pos)[0]
            offset = struct.unpack_from(endian + ("Q" if is64 else "I"), data, pos + 8)[0]
            archs.append({"cpu_type": hex(cpu), "slice_offset": offset})
        return {"format": "fat", "archs": archs,
                "warning": "fat-slices-not-parsed; use per-slice Mach-O tooling"}
    endian = MACH64_MAGICS.get(magic)
    if endian is None:
        return None
    _, cpu, subtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from(
        endian + "IiiIIIII", data, 0)
    out = {
        "format": "macho64", "cpu_type": hex(cpu & 0xFFFFFFFF),
        "is_arm64": (cpu & 0xFFFFFFFF) == 0x0100000c,
        "cpu_subtype": hex(subtype & 0xFFFFFFFF),
        "file_type": filetype, "ncmds": ncmds, "uuid": None,
        "cryptid": None, "linked_libraries": [], "rpaths": [],
        "code_signature_command": False,
    }
    if ncmds > 10000 or sizeofcmds > len(data) - 32:
        out["warning"] = "load-command-table-outside-header-sample"
        return out
    pos = 32
    end = 32 + sizeofcmds
    for _ in range(ncmds):
        if pos + 8 > end:
            out["warning"] = "truncated-load-command"
            break
        cmd, size = struct.unpack_from(endian + "II", data, pos)
        if size < 8 or pos + size > end:
            out["warning"] = "malformed-load-command"
            break
        command = data[pos:pos + size]
        base = cmd & 0x7FFFFFFF
        if base == 0x1B and size >= 24:  # LC_UUID
            out["uuid"] = str(uuid.UUID(bytes=command[8:24])).upper()
        elif base in (0x21, 0x2C) and size >= 20:  # LC_ENCRYPTION_INFO[_64]
            out["cryptid"] = struct.unpack_from(endian + "I", command, 16)[0]
        elif base in (0xC, 0xD, 0x18, 0x1F, 0x23, 0x20) and size >= 24:
            # LC_LOAD_DYLIB/ID_DYLIB/WEAK/REEXPORT/UPWARD/LAZY
            name_off = struct.unpack_from(endian + "I", command, 8)[0]
            name = _c_string(command, name_off)
            if name:
                out["linked_libraries"].append(name)
        elif base == 0x1C and size >= 12:  # LC_RPATH
            name = _c_string(command, struct.unpack_from(endian + "I", command, 8)[0])
            if name:
                out["rpaths"].append(name)
        elif base == 0x1D:  # LC_CODE_SIGNATURE (presence only)
            out["code_signature_command"] = True
        pos += size
    return out


def _bundle_root(plist_path):
    return plist_path[: -len("Info.plist")]


def _binary_candidate(name, bundles):
    if name.endswith((".dylib", ".so")):
        return True
    for bundle in bundles:
        if name == bundle["root"] + bundle["executable"]:
            return True
    if ".framework/" in name:
        prefix, inner = name.rsplit(".framework/", 1)
        framework_name = prefix.rsplit("/", 1)[-1]
        if inner == framework_name:
            return True
    return False


def _normalize(name):
    return re.sub(r"^Payload/[^/]+\.app/", "Payload/@APP/", name, count=1)


def audit_ipa(filename):
    path = Path(filename)
    overall = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            overall.update(block)
    report = {
        "file": path.name, "size_bytes": path.stat().st_size,
        "sha256": overall.hexdigest(), "status": "STATIC_ONLY",
        "warnings": [], "apps": [], "archive": {}, "binaries": [],
        "interpretation": (
            "LC_ENCRYPTION_INFO cryptid is a FairPlay flag, not proof of complete "
            "decryptability. Binary keyword hints are not proof of gameplay, "
            "hook compatibility, networking, or a working RP mode."
        ),
    }
    with zipfile.ZipFile(path) as zf:
        items = zf.infolist()
        if len(items) > MAX_ZIP_ITEMS:
            raise ValueError("too-many-zip-entries")
        known = set()
        safe = {}
        for item in items:
            name = item.filename
            if unsafe_path(name):
                report["warnings"].append("unsafe-zip-entry")
                continue
            if name in known:
                report["warnings"].append("duplicate-zip-entry")
                continue
            known.add(name)
            if not item.is_dir():
                safe[name] = item
        report["archive"] = {
            "files": len(safe),
            "total_uncompressed_bytes": sum(x.file_size for x in safe.values()),
            "zip_test": "NOT_PERFORMED_FULL_ARCHIVE",
        }
        for name, item in safe.items():
            if not APP_INFO.fullmatch(name):
                continue
            if item.file_size > 2 * 1024 * 1024:
                report["warnings"].append("oversized-app-plist")
                continue
            try:
                plist = plistlib.loads(zf.read(item))
                executable = plist.get("CFBundleExecutable", "")
                if not isinstance(executable, str) or "/" in executable or not executable:
                    report["warnings"].append("missing-or-unsafe-bundle-executable")
                    continue
                report["apps"].append({
                    "root": _bundle_root(name),
                    "bundle_id": str(plist.get("CFBundleIdentifier", "")),
                    "version": str(plist.get("CFBundleShortVersionString", "")),
                    "build": str(plist.get("CFBundleVersion", "")),
                    "minimum_ios": str(plist.get("MinimumOSVersion", "")),
                    "executable": executable,
                })
            except (ValueError, TypeError, plistlib.InvalidFileException):
                report["warnings"].append("invalid-app-plist")
        candidates = [(name, info) for name, info in safe.items()
                      if _binary_candidate(name, report["apps"])]
        if len(candidates) > MAX_BINARY_ITEMS:
            report["warnings"].append("binary-candidate-limit-reached")
        for name, info in candidates[:MAX_BINARY_ITEMS]:
            if info.file_size > MAX_BINARY_SIZE:
                report["warnings"].append("oversized-binary-skipped")
                continue
            digest = hashlib.sha256()
            head = bytearray()
            with zf.open(info) as stream:
                while True:
                    chunk = stream.read(BLOCK)
                    if not chunk:
                        break
                    digest.update(chunk)
                    if len(head) < HEAD_SIZE:
                        head.extend(chunk[:HEAD_SIZE - len(head)])
            meta = macho_metadata(head)
            if meta is None:
                continue
            hits = sorted(word.decode("ascii") for word in MARKERS
                          if word in head.lower())
            report["binaries"].append({
                "path": name, "normalized_path": _normalize(name),
                "size_bytes": info.file_size, "sha256": digest.hexdigest(),
                "macho": meta, "markers_in_first_1mib": hits,
            })
    return report


def compare_reports(base, candidate):
    original = {x["normalized_path"]: x for x in base["binaries"]}
    current = {x["normalized_path"]: x for x in candidate["binaries"]}
    shared = original.keys() & current.keys()
    changes = []
    for path in sorted(shared):
        a, b = original[path], current[path]
        if a["sha256"] != b["sha256"]:
            changes.append({
                "path": path,
                "old_sha256": a["sha256"], "new_sha256": b["sha256"],
                "old_uuid": a["macho"].get("uuid"), "new_uuid": b["macho"].get("uuid"),
                "old_cryptid": a["macho"].get("cryptid"),
                "new_cryptid": b["macho"].get("cryptid"),
                "added_linked_libraries": sorted(
                    set(b["macho"].get("linked_libraries", []))
                    - set(a["macho"].get("linked_libraries", []))),
                "removed_linked_libraries": sorted(
                    set(a["macho"].get("linked_libraries", []))
                    - set(b["macho"].get("linked_libraries", []))),
            })
    return {
        "scope": "FULL_SHA256_OF_RECOGNIZED_MACHO_FILES_ONLY",
        "baseline_ipa_sha256": base["sha256"],
        "candidate_ipa_sha256": candidate["sha256"],
        "added_binaries": sorted(current.keys() - original.keys()),
        "removed_binaries": sorted(original.keys() - current.keys()),
        "changed_binaries": changes,
        "identical_binary_count": sum(
            original[p]["sha256"] == current[p]["sha256"] for p in shared),
        "caveat": "No disassembly, in-game test, asset hash comparison, or ABI equivalence proof.",
    }


def markdown_report(report):
    cand = report["candidate"]
    delta = report.get("comparison")
    lines = [
        "# Winstom / GTA V iOS IPA — static audit",
        "",
        "Status: **STATIC_ONLY**. Input is not executed, decrypted or modified.",
        "",
        f"- Input IPA: `{cand['file']}`",
        f"- IPA SHA-256: `{cand['sha256']}`",
        f"- IPA size: {cand['size_bytes']} bytes",
        f"- ZIP files: {cand['archive']['files']}",
        f"- Recognized Mach-O: {len(cand['binaries'])}",
        "",
        "## Application bundles",
    ]
    for app in cand["apps"]:
        lines.append(
            f"- `{app['bundle_id']}`: version={app['version']}, "
            f"build={app['build']}, min iOS={app['minimum_ios']}, "
            f"executable=`{app['executable']}`")
    lines.extend(["", "## Mach-O inventory (UUID / FairPlay flag)"])
    for b in cand["binaries"][:100]:
        m = b["macho"]
        lines.append(f"- `{b['normalized_path']}`: "
                     f"UUID={m.get('uuid')}, cryptid={m.get('cryptid')}, "
                     f"ARM64={m.get('is_arm64')}, SHA256=`{b['sha256']}`")
    if delta:
        lines.extend([
            "", "## Mach-O comparison vs. baseline",
            f"- Added binaries: {len(delta['added_binaries'])}",
            f"- Removed binaries: {len(delta['removed_binaries'])}",
            f"- Changed binaries: {len(delta['changed_binaries'])}",
            f"- Identical binaries: {delta['identical_binary_count']}",
        ])
        for b in delta["changed_binaries"][:100]:
            lines.append(f"- Changed `{b['path']}` "
                         f"UUID {b['old_uuid']} -> {b['new_uuid']}; "
                         f"added deps={b['added_linked_libraries']}")
    lines.extend([
        "", "## Technical limitations",
        "- Keyword hits are weak hints from the first 1 MiB, NOT validated functions.",
        "- Decompilation, packet reconstruction, hook offsets and runtime tests: NOT PERFORMED.",
        "- An unchanged Mach-O does not prove gameplay equivalence.",
        "- A missing RP string does not prove RP functionality is absent.",
        "- Any changed UUID or SHA-256 must be investigated before applying v13 patches.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    report = {"candidate": audit_ipa(args.ipa)}
    if args.baseline:
        report["comparison"] = compare_reports(audit_ipa(args.baseline),
                                               report["candidate"])
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
    args.output_md.write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote {args.output_json} and {args.output_md} (STATIC_ONLY)")


if __name__ == "__main__":
    main()
