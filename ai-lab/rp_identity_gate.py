#!/usr/bin/env python3
"""Fail-closed static identity gate for the documented v12 GTA V iOS binary.

Compares metadata ONLY. It never loads game code, signs an IPA, or asserts
runtime compatibility. No proprietary binary is needed in CI.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "projects/roleplay-ios/baselines/v12-verified.json"
STATE = ROOT / "projects/roleplay-ios/state.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")


def validate_identity(state, evidence):
    """Return a list of mismatches. An empty list means metadata agrees ONLY."""
    errors = []
    if not isinstance(state, dict) or not isinstance(evidence, dict):
        return ["input: expected JSON objects"]
    baseline = state.get("baseline")
    executable = evidence.get("executable")
    bundle = evidence.get("bundle")
    if not all(isinstance(item, dict) for item in (baseline, executable, bundle)):
        return ["structure: missing or invalid baseline/executable/bundle objects"]
    pairs = (
        ("ipa_sha256", baseline.get("ipa_sha256"), evidence.get("ipa_sha256")),
        ("executable_sha256", baseline.get("executable_sha256"), executable.get("sha256")),
        ("macho_uuid", baseline.get("macho_uuid"), executable.get("uuid")),
        ("binary_count", baseline.get("binary_count"), evidence.get("observed_native_binary_count")),
    )
    for key, expected, actual in pairs:
        if expected is None or actual is None or expected != actual:
            errors.append(f"{key}: state/evidence mismatch or missing")
    for key, value in (("ipa_sha256", evidence.get("ipa_sha256")),
                       ("executable_sha256", executable.get("sha256"))):
        if not isinstance(value, str) or not SHA256.fullmatch(value):
            errors.append(f"{key}: invalid SHA-256")
    if not isinstance(executable.get("uuid"), str) or not UUID.fullmatch(executable["uuid"]):
        errors.append("macho_uuid: invalid Mach-O UUID")
    if executable.get("architecture") != "arm64":
        errors.append("architecture: expected arm64")
    if bundle.get("CFBundleExecutable") != "GTA5":
        errors.append("bundle executable: expected GTA5")
    for key, value in (("ipa_sha256", baseline.get("ipa_sha256")),
                       ("executable_sha256", baseline.get("executable_sha256"))):
        if not isinstance(value, str) or not SHA256.fullmatch(value):
            errors.append(f"state.{key}: invalid SHA-256")
    if not isinstance(baseline.get("macho_uuid"), str) or not UUID.fullmatch(baseline["macho_uuid"]):
        errors.append("state.macho_uuid: invalid Mach-O UUID")
    if not isinstance(baseline.get("binary_count"), int) or isinstance(baseline.get("binary_count"), bool) or baseline["binary_count"] < 1:
        errors.append("state.binary_count: invalid")
    if baseline.get("device_tested") is not False:
        errors.append("device_tested: static evidence cannot establish device testing")
    if not isinstance(evidence.get("observed_native_binary_count"), int) or isinstance(evidence.get("observed_native_binary_count"), bool) or evidence["observed_native_binary_count"] < 1:
        errors.append("binary_count: invalid")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--evidence", type=Path, default=BASELINE)
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    errors = validate_identity(state, evidence)
    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    print("PASS: v12 identity metadata agrees; runtime/device compatibility NOT verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
