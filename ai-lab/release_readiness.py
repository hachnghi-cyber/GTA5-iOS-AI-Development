#!/usr/bin/env python3
"""Source-only, fail-closed Roleplay IPA release readiness report.

Never opens, changes, signs, uploads, or publishes an IPA. Evidence references
in state.json are declarations, not independent proof of device runs.
"""
import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "projects" / "roleplay-ios" / "state.json"
BASELINE = HERE / "projects" / "roleplay-ios" / "baselines" / "v12-verified.json"
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
REQUIRED_ATTESTATIONS = (
    ("game_frame_callback", "Engine frame callback verified on exact executable"),
    ("authenticated_transport", "Authenticated multiplayer carrier and trusted sender verified"),
    ("ios_build", "iPhoneOS arm64 build and linker output verified"),
    ("codesign", "Local re-signing and provisioning verified"),
    ("device_multiplayer", "Two-device Online Roleplay and logs verified"),
    ("regression", "Crash and baseline functionality regression reviewed"),
)


def _valid_sha(value):
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def _valid_uuid(value):
    return isinstance(value, str) and bool(UUID.fullmatch(value))


def _attested(record, executable_hash):
    """Require scoped evidence; do NOT authenticate its contents."""
    return (isinstance(record, dict)
            and record.get("status") == "verified"
            and isinstance(record.get("evidence"), str)
            and bool(record["evidence"].strip())
            and record.get("executable_sha256") == executable_hash)


def assess(state, baseline):
    """Evaluate versioned declarations; NEVER authorize unattended publication."""
    if not isinstance(state, dict) or not isinstance(baseline, dict):
        raise ValueError("state and baseline must be JSON objects")
    st = state.get("baseline")
    exe = baseline.get("executable")
    if not isinstance(st, dict) or not isinstance(exe, dict):
        raise ValueError("baseline identity records are missing or malformed")

    checks = []

    def add(key, passed, detail):
        checks.append({"id": key, "passed": bool(passed), "detail": detail})

    ipa_hash = st.get("ipa_sha256")
    executable_hash = st.get("executable_sha256")
    uuid = st.get("macho_uuid")
    add("baseline_ipa_identity",
        _valid_sha(ipa_hash) and ipa_hash.lower() == str(baseline.get("ipa_sha256", "")).lower(),
        "Recorded IPA hashes agree; no IPA was read")
    add("baseline_executable_identity",
        _valid_sha(executable_hash) and executable_hash.lower() == str(exe.get("sha256", "")).lower(),
        "Recorded executable hashes agree; no executable was read")
    add("baseline_macho_uuid",
        _valid_uuid(uuid) and uuid.upper() == str(exe.get("uuid", "")).upper(),
        "Recorded Mach-O UUIDs agree; no new LC_UUID inspection")
    artifact = st.get("actual_build_artifact")
    add("local_ipa_build", isinstance(artifact, str) and bool(artifact.strip()),
        "Actual candidate build artifact identifier/path required")
    add("device_tested", st.get("device_tested") is True,
        "On-device test must be recorded; static CI is insufficient")

    attestations = state.get("release_evidence", {})
    if not isinstance(attestations, dict):
        attestations = {}
    for key, description in REQUIRED_ATTESTATIONS:
        add(key, _attested(attestations.get(key), executable_hash),
            description + "; requires version-matched evidence reference")

    approval = attestations.get("manual_approval")
    add("manual_review", isinstance(approval, dict)
        and approval.get("approved") is True
        and isinstance(approval.get("evidence"), str)
        and bool(approval["evidence"].strip())
        and approval.get("executable_sha256") == executable_hash,
        "Separate human approval required; never grants auto-deployment")
    ready = all(c["passed"] for c in checks)
    return {
        "schema_version": 1,
        "project": state.get("project_id"),
        "status": "ready-for-manual-release-review" if ready else "blocked",
        "ready_for_manual_release_review": ready,
        "auto_publish_allowed": False,
        "signed_ipa_created": False,
        "device_test_performed_by_this_tool": False,
        "checks": checks,
        "blocking_gates": [c["id"] for c in checks if not c["passed"]],
        "scope": "metadata + declared evidence only; independent verification still required"
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", type=Path, default=STATE)
    p.add_argument("--baseline", type=Path, default=BASELINE)
    p.add_argument("--output", type=Path)
    p.add_argument("--require-ready", action="store_true",
                   help="Exit nonzero if any release gate is blocked")
    args = p.parse_args(argv)
    state = json.loads(args.state.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    report = assess(state, baseline)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 2 if args.require_ready and not report["ready_for_manual_release_review"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
