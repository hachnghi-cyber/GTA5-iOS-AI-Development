#!/usr/bin/env python3
"""Fail-closed v13.3 GTA5 hook candidate version guard.

A matched UUID and SHA256 do NOT authenticate a hook site, ABI, call graph,
thread, or sender. No executable is patched. No offset is ever approved here.
"""
import argparse
import json
import re
from pathlib import Path

V133_GTA5_UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
V133_GTA5_SHA256 = "f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc"
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_HEX32 = re.compile(r"^[a-f0-9]{32}$")


def _normalized_uuid(value):
    if not isinstance(value, str):
        return None
    s = value.lower().replace("-", "")
    return s if _HEX32.fullmatch(s) else None


def _normalized_sha256(value):
    if not isinstance(value, str):
        return None
    s = value.lower()
    return s if _HEX64.fullmatch(s) else None


def audit_hook_record(record):
    """Classify only; never approve patching/hooking."""
    if not isinstance(record, dict):
        return {
            "classification": "INVALID_DOCUMENT",
            "may_hook_v133": False,
            "needs_game_thread_proof": True,
            "needs_authenticated_sender_proof": True,
        }
    # Support both legacy hook candidates and the historically named V13 report.
    sha = record.get("GTA5_SHA256", record.get("input_gta5_sha256"))
    uuid = record.get("GTA5_UUID", record.get("input_gta5_uuid"))
    normalized_uuid, normalized_sha = _normalized_uuid(uuid), _normalized_sha256(sha)
    expected_uuid = _normalized_uuid(V133_GTA5_UUID)
    expected_sha = _normalized_sha256(V133_GTA5_SHA256)
    fingerprint_valid = normalized_uuid is not None and normalized_sha is not None
    matches = fingerprint_valid and normalized_uuid == expected_uuid and normalized_sha == expected_sha
    return {
        "classification": (
            "INVALID_FINGERPRINT" if not fingerprint_valid else
            "VERSION_MISMATCH_BLOCKED" if not matches else
            "EXACT_BUILD_UNVERIFIED_HOOK"
        ),
        "input_uuid": uuid,
        "input_sha256": sha,
        "expected_v133_uuid": V133_GTA5_UUID,
        "expected_v133_sha256": V133_GTA5_SHA256,
        "exact_build_match": bool(matches),
        "may_hook_v133": False,
        "may_use_as_authenticated_sender": False,
        "needs_game_thread_proof": True,
        "needs_authenticated_sender_proof": True,
        "reason": (
            "An exact binary fingerprint is necessary, but never sufficient "
            "to verify hook ownership, function ABI, game-thread context, "
            "native transport sender or session identity."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Existing hook/report JSON")
    parser.add_argument("--out", type=Path, help="Optional output JSON path")
    args = parser.parse_args()
    source = json.loads(args.json_path.read_text(encoding="utf-8"))
    result = audit_hook_record(source)
    result["source_file"] = args.json_path.name
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
