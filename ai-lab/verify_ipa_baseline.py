#!/usr/bin/env python3
"""Local read-only IPA fingerprint gate for GTA V iOS Roleplay.

Never extracts/distributes game binaries. Engine SHA256 & LC_UUID both must
match the approved baseline. A resign may change IPA SHA256 without changing
the executable; report it separately rather than silently accepting it.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASELINE = HERE / "projects" / "roleplay-ios" / "baselines" / "v12-verified.json"
EXECUTABLE = "Payload/GTAV.app/GTA5"

def executable_fingerprint(ipa_path, member=EXECUTABLE):
    with zipfile.ZipFile(ipa_path, "r") as z:
        matching = [item for item in z.infolist() if item.filename == member]
        if len(matching) != 1:
            raise ValueError("Expected exactly one game executable in IPA")
        with z.open(matching[0]) as f:
            header = f.read(1048576)
            sha = hashlib.sha256(header)
            for chunk in iter(lambda: f.read(1048576), b""):
                sha.update(chunk)
    if len(header) < 32 or header[:4] not in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        raise ValueError("Executable is not a recognized thin Mach-O 64 image")
    endian = "<" if header[:4] == b"\xcf\xfa\xed\xfe" else ">"
    magic, cpu, subtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from(endian + "IIIIIIII", header, 0)
    if cpu != 0x0100000c:
        raise ValueError("Executable Mach-O is not ARM64")
    offset, uuid = 32, None
    for _ in range(min(ncmds, 10000)):
        if offset + 8 > len(header):
            raise ValueError("Truncated Mach-O load commands")
        cmd, cmdsize = struct.unpack_from(endian + "II", header, offset)
        if cmdsize < 8 or offset + cmdsize > len(header):
            raise ValueError("Invalid Mach-O load command size")
        if (cmd & 0x7fffffff) == 0x1b and cmdsize >= 24:
            uuid = header[offset+8:offset+24].hex().upper()
        offset += cmdsize
    if uuid is None:
        raise ValueError("Mach-O LC_UUID not present")
    fmt = lambda u: "-".join((u[:8],u[8:12],u[12:16],u[16:20],u[20:]))
    return {"executable_sha256": sha.hexdigest(), "macho_uuid": fmt(uuid)}

def verify(ipa_path, baseline_path=DEFAULT_BASELINE):
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    measured = executable_fingerprint(ipa_path)
    expected = baseline["executable"]
    expected_sha = expected["sha256"].lower()
    expected_uuid = expected["uuid"].upper()
    matches_sha = measured["executable_sha256"].lower() == expected_sha
    matches_uuid = measured["macho_uuid"].upper() == expected_uuid
    return {"status": "matched-executable" if matches_sha and matches_uuid else "REJECTED-MISMATCH",
            "version_gate_passed": matches_sha and matches_uuid,
            "checks": {"executable_sha256": matches_sha, "macho_uuid": matches_uuid},
            "measured": measured,
            "expected": {"executable_sha256": expected["sha256"], "macho_uuid": expected["uuid"]},
            "scope": "read-only identity check, not a gameplay test or source decompilation"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ipa")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--output")
    args = parser.parse_args()
    r = verify(args.ipa, args.baseline)
    report = json.dumps(r, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(report, encoding="utf8")
    print(report)
    return 0 if r["version_gate_passed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
