#!/usr/bin/env python3
"""Text-only E0 last-run consistency verifier, never hardware proof."""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys

BEGIN = re.compile(r"\[RBP_E0\] RUN_BEGIN VERSION=1 pid=(\d+) timestamp_ms=(\d+)")
NEEDED = [
    "[RBP_E0] DLLMAIN_ATTACH",
    "[RBP_E0] SCRIPT_HOOK_UUID_MATCH=1",
    "[RBP_E0] SCRIPT_REGISTER_ATTEMPTED=1 (void API)",
    "[RBP_E0] CALLBACK_ENTER",
    "[RBP_E0] SCRIPT_TICK=1",
    "[RBP_E0] SCRIPT_TICK=30",
    "[RBP_E0] SCRIPT_TICK=120",
    "[RBP_E0] SCRIPT_CALLBACK_COMPLETE=1",
]
ERRORS = [
    "SHV_IMAGE_COUNT=", "FAIL_CLOSED", "SHV_NOLOAD_RESOLUTION_FAILED",
    "REQUIRED_SYMBOL_MISSING", "SCRIPT_HOOK_UUID_MATCH=0",
    "SCRIPT_HOOK_UUID_CHECK=HOST_MOCK_ONLY", "SCRIPT_WAIT_FAST_RETURN=1",
    "SCRIPT_CLOCK_OR_WAIT_INVALID=1",
]

def evaluate(text: str) -> dict:
    matches = list(BEGIN.finditer(text))
    if not matches:
        return {"status": "NO_RUN_MARKER", "pass": False, "missing": ["RUN_BEGIN"]}
    run = text[matches[-1].start():]
    lines = [line.strip() for line in run.splitlines()]
    positions = [next((i for i, line in enumerate(lines) if line == target), -1)
                 for target in NEEDED]
    errors = [v for v in ERRORS if v in run]
    if errors:
        return {"status": "FAIL_CLOSED", "pass": False, "missing": [], "errors": errors}
    missing = [target for target, pos in zip(NEEDED, positions) if pos == -1]
    if missing:
        return {"status": "INCOMPLETE_LAST_RUN", "pass": False, "missing": missing}
    if positions != sorted(set(positions)):
        return {"status": "OUT_OF_ORDER", "pass": False, "missing": []}
    return {"status": "LOG_CONSISTENT_NOT_DEVICE_PROOF", "pass": True, "missing": []}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=pathlib.Path)
    args = ap.parse_args()
    try:
        result = evaluate(args.log.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        print(json.dumps({"status": "LOG_UNREADABLE", "error": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["pass"] else 1

if __name__ == "__main__":
    sys.exit(main())
