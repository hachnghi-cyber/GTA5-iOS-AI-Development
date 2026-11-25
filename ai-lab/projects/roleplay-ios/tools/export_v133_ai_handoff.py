#!/usr/bin/env python3
"""Produce a reproducible, source-only handoff ZIP; never copy game binaries.

Run from repository root:
    python3 ai-lab/projects/roleplay-ios/tools/export_v133_ai_handoff.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[4]
PROJECT = Path("ai-lab/projects/roleplay-ios")
OUTPUT_NAME = "GTA-V-iOS-v13.3-RP-AI-HANDOFF-SOURCE-REPORT.zip"
SAFE_EXTENSIONS = {".md", ".json", ".py", ".c", ".h", ".m", ".mm",
                   ".sh", ".bat", ".txt", ".yml", ".yaml"}
REQUIRED_FILES = [
    Path("AGENTS.md"),
    PROJECT / "AI_HANDOFF_V133_PHASE8.md",
    PROJECT / "PROMPT_CHUYEN_AI_V133.md",
    PROJECT / "state.json",
    PROJECT / "CONTINUE_HERE.md",
    PROJECT / "ROADMAP.md",
    PROJECT / "v133_interaction/include/rp_v133_interact_gate.h",
    PROJECT / "v133_interaction/include/rp_v133_wire.h",
    PROJECT / "v133_interaction/include/rp_v133_mailbox.h",
    PROJECT / "v133_interaction/src/rp_v133_interact_gate.c",
    PROJECT / "v133_interaction/src/rp_v133_wire.c",
    PROJECT / "v133_interaction/src/rp_v133_mailbox.c",
    PROJECT / "v133_interaction/ios/PRPV133LaunchProbe.m",
    PROJECT / "v133_interaction/ios/patch_exact_v133_probe.py",
    PROJECT / "v133_interaction/tools/run_host_tests.sh",
    Path("ai-lab/winstom_rp_audit.py"),
    Path("ai-lab/winstom_lmx_objc_map.py"),
    Path(".github/workflows/winstom-rp-ipa-audit.yml"),
    Path(".github/workflows/build-v133-phase8-probe.yml"),
    Path("police-rp/v1.4/HOOK_CANDIDATES_V12.json"),
    Path("police-rp/v1.4/DIAGNOSTIC_READONLY_REPORT_V13.json"),
]
REFERENCE_DIRS = [
    PROJECT,
    Path("police-rp/v1.4/Integration"),
    Path("police-rp/v1.4/P2P"),
    Path("police-rp/v1.4/NativeBridge"),
]
ADDITIONAL_FILES = [
    Path("ai-lab/tests/test_winstom_rp_audit.py"),
    Path("ai-lab/tests/test_winstom_lmx_objc_map.py"),
]
MAX_FILE_BYTES = 1_500_000
MAX_TOTAL_BYTES = 15_000_000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_sha() -> str:
    env_sha = os.environ.get("GITHUB_SHA", "")
    if len(env_sha) == 40 and all(c in "0123456789abcdefABCDEF" for c in env_sha):
        return env_sha.lower()
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def collect() -> dict[str, bytes]:
    names = set(REQUIRED_FILES + ADDITIONAL_FILES)
    for folder in REFERENCE_DIRS:
        target = REPO_ROOT / folder
        if not target.is_dir():
            raise FileNotFoundError(f"Required project folder missing: {folder}")
        for path in target.rglob("*"):
            if path.is_file() and path.suffix.lower() in SAFE_EXTENSIONS:
                names.add(path.relative_to(REPO_ROOT))
    files: dict[str, bytes] = {}
    total = 0
    for rel in sorted(names, key=str):
        absolute = REPO_ROOT / rel
        if not absolute.is_file() or absolute.is_symlink():
            raise FileNotFoundError(f"Missing or symlinked source: {rel}")
        if absolute.suffix.lower() not in SAFE_EXTENSIONS:
            raise ValueError(f"Unapproved file extension: {rel}")
        raw = absolute.read_bytes()
        if len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
            raise ValueError(f"Refusing potentially binary/oversized content: {rel}")
        raw.decode("utf-8")
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Archive would exceed source-only size limit")
        files[rel.as_posix()] = raw
    if len(files) < 35:
        raise ValueError(f"Unexpectedly incomplete handoff: {len(files)} files")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("dist/ai-handoff"))
    parser.add_argument("--evidence-dir", type=Path, default=Path("handoff_evidence"))
    opts = parser.parse_args()
    files = collect()
    sha = git_sha()
    if opts.evidence_dir.is_dir():
        for candidate in sorted(opts.evidence_dir.iterdir()):
            if candidate.is_file() and candidate.suffix == ".log":
                raw = candidate.read_bytes()
                if len(raw) <= MAX_FILE_BYTES and b"\x00" not in raw:
                    raw.decode("utf-8")
                    files["evidence/CI_" + candidate.name] = raw

    readme = f"""# GTA V iOS v13.3 — AI handoff / START HERE

- Snapshot source commit: {sha}
- Repository: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development
- Branch: feature/winstom-rp-ipa-audit-20261116
- Draft PR: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/16
- Main report: ai-lab/projects/roleplay-ios/AI_HANDOFF_V133_PHASE8.md
- Prompt for another AI: ai-lab/projects/roleplay-ios/PROMPT_CHUYEN_AI_V133.md
- State: ai-lab/projects/roleplay-ios/state.json
- Main source: ai-lab/projects/roleplay-ios/v133_interaction/
- iPhone diagnostic source: .../v133_interaction/ios/
- Proof: CI logs, when present, are in evidence/; static source reports are in project folder.

THIS IS SOURCE ONLY. NO GTA V IPA, NO Winstom proprietary binary, NO SIGNING MATERIAL.
NO REAL IPHONE OR TWO-PLAYER POLICE RP GAMEPLAY HAS BEEN VERIFIED.
The older police-rp/v1.4/ sources are legacy REFERENCE and MUST NOT be
loaded into v13.3 using their old ABI, hook RVAs, or 56-byte wire format.
Read AGENTS.md and the report before making any change.

Host tests from repo root:
    cd ai-lab/projects/roleplay-ios/v133_interaction
    CC=gcc bash tools/run_host_tests.sh
    CC=clang bash tools/run_host_tests.sh
    python3 -m unittest discover -s tests -p 'test_verify_device_trace.py' -v
    python3 -m unittest discover -s tests -p 'test_audit_hook_fingerprint.py' -v
    python3 -m unittest discover -s ios -p 'test_v133_probe_packer.py' -v
"""
    files["START_HERE_AI.md"] = readme.encode("utf-8")
    manifest = {
        "schema": "v133-ai-handoff-source-only-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_repository": "hachnghi-cyber/GTA5-iOS-AI-Development",
        "branch": "feature/winstom-rp-ipa-audit-20261116",
        "commit_sha": sha,
        "contains_game_binary": False,
        "iphone_rp_gameplay_verified": False,
        "files": [
            {"path": p, "sha256": sha256(blob), "size_bytes": len(blob)}
            for p, blob in sorted(files.items())
        ],
    }
    files["MANIFEST_SHA256.json"] = (json.dumps(manifest, indent=2,
                                                 ensure_ascii=False) + "\n").encode("utf-8")
    output = opts.out_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / OUTPUT_NAME
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=False) as zf:
        for rel, blob in sorted(files.items()):
            zf.writestr(rel, blob)
    with zipfile.ZipFile(archive_path, "r") as zf:
        if zf.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        if sorted(zf.namelist()) != sorted(files):
            raise ValueError("ZIP manifest/files mismatch")
        for rel, blob in files.items():
            if zf.read(rel) != blob:
                raise ValueError(f"ZIP payload changed: {rel}")
    digest = sha256(archive_path.read_bytes())
    (output / (OUTPUT_NAME + ".sha256")).write_text(
        f"{digest}  {OUTPUT_NAME}\n", encoding="utf-8")
    print(f"HANDOFF_ARCHIVE={archive_path}")
    print(f"FILE_COUNT={len(files)}")
    print(f"SHA256={digest}")
    print(f"SOURCE_SHA={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
