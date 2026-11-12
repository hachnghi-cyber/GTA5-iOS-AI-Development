#!/usr/bin/env python3
"""Continuous Roleplay watchdog: periodic CI health + work queue snapshot.

This is deterministic, free of AI API calls, and deliberately read-only.
Writing new game code or executing an agent requires a separate authorized service.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "projects" / "roleplay-ios" / "state.json"
BASELINE = HERE / "projects" / "roleplay-ios" / "baselines" / "v12-verified.json"

def snapshot(state, baseline, commit="local"):
    backlog = state["backlog"]
    eligible = sorted([t for t in backlog
        if t["status"] in ("not-started", "in-progress") and not t.get("blocked_on")],
        key=lambda t: (t["status"] != "in-progress", t["priority"], t["id"]))
    blocked = [t["id"] for t in backlog if t["status"] == "blocked" or t.get("blocked_on")]
    return {
        "schema_version": 1,
        "status": "periodic-static-watch-only",
        "ci_commit": commit,
        "project_id": state["project_id"],
        "verified_ipa_baseline": bool(state["baseline"].get("ipa_sha256")
                                      and baseline.get("ipa_sha256")
                                      == state["baseline"].get("ipa_sha256")),
        "game_executable_sha256": baseline.get("executable", {}).get("sha256"),
        "ready_tasks": [{"id": t["id"], "title": t["title"], "issue_url": t.get("issue_url")}
                        for t in eligible],
        "next_task": eligible[0]["id"] if eligible else None,
        "blocked_tasks": sorted(set(blocked)),
        "next_action": state["next_action"],
        "automated_execution": "state validation, unit tests and report only",
        "ai_code_generation": "not enabled in this workflow",
        "device_validation": False
    }

def generate(statefile=STATE, baselinefile=BASELINE):
    state_bytes = Path(statefile).read_bytes()
    base_bytes = Path(baselinefile).read_bytes()
    state = json.loads(state_bytes)
    baseline = json.loads(base_bytes)
    from continuity import validate
    validate(state)
    if baseline.get("schema_version") != 1:
        raise ValueError("Invalid baseline schema")
    report = snapshot(state, baseline, os.getenv("GITHUB_SHA", "local"))
    report["state_file_sha256"] = hashlib.sha256(state_bytes).hexdigest()
    report["baseline_metadata_sha256"] = hashlib.sha256(base_bytes).hexdigest()
    report["observed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output")
    args = p.parse_args()
    result = generate()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf8")
    print(encoded)

if __name__ == "__main__":
    main()
