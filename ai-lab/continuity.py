#!/usr/bin/env python3
"""Validate versioned Roleplay project state and export a human-readable handoff.

Read-only by design. CI artifacts do not modify authoritative state.json.
Every coding task must update that state in its pull request.
"""
import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "projects" / "roleplay-ios" / "state.json"
ALLOWED = {"not-started", "in-progress", "blocked", "passed", "failed", "complete"}

def read_state(path=STATE):
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    validate(state)
    return state

def validate(state):
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("Invalid project state schema_version")
    for field in ("project_id", "repository", "phase", "next_action", "update_policy"):
        if not isinstance(state.get(field), str) or not state[field].strip():
            raise ValueError("Missing/empty field: " + field)
    baseline = state.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("Missing baseline")
    for field in ("ipa_sha256", "game_version", "macho_uuid", "device_tested"):
        if field not in baseline:
            raise ValueError("Missing baseline." + field)
    if not isinstance(baseline["device_tested"], bool):
        raise ValueError("device_tested must be boolean")
    for field in ("verified_facts", "unknowns", "backlog"):
        if not isinstance(state.get(field), list):
            raise ValueError("Missing/invalid list: " + field)
    if not state["backlog"]:
        raise ValueError("Empty backlog")
    seen = set()
    for task in state["backlog"]:
        if not isinstance(task, dict):
            raise ValueError("Invalid backlog entry")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("Missing/duplicate task id")
        seen.add(task_id)
        if task.get("status") not in ALLOWED:
            raise ValueError("Invalid task status: " + str(task.get("status")))
        if not isinstance(task.get("priority"), int):
            raise ValueError("Task priority must be integer")
        if not isinstance(task.get("title"), str) or not task["title"]:
            raise ValueError("Task title missing")
        if task["status"] == "complete" and not task.get("evidence"):
            raise ValueError("Completed task must have evidence: " + task_id)
    for fact in state["verified_facts"]:
        if not isinstance(fact.get("claim"), str) or not fact.get("evidence"):
            raise ValueError("Verified fact requires claim and evidence")
    return True

def generate_handoff(state):
    lines = ["# GTA V iOS Roleplay — CI project handoff",
             "", "Auto-generated from versioned state.json; a snapshot, not an autonomous AI session.",
             "", "Project: " + state["display_name"],
             "Repository: " + state["repository"],
             "Current phase: " + state["phase"],
             "CI commit (not necessarily a Roleplay build): " + os.getenv("GITHUB_SHA", "local"),
             "On-device tested: " + ("yes" if state["baseline"]["device_tested"] else "not verified"),
             "", "## Verified facts"]
    for item in state["verified_facts"]:
        lines.append("- " + item["claim"] + " — " + item["evidence"])
    lines.extend(["", "## Backlog (status is from state.json)"])
    for task in sorted(state["backlog"], key=lambda x: (x["priority"], x["id"])):
        lines.append("- " + task["id"] + " [" + task["status"] + "]: " + task["title"])
        if task.get("blocked_on"):
            lines.append("  Blocked on: " + ", ".join(task["blocked_on"]))
    lines.extend(["", "## Next action", state["next_action"], "",
                  "## New ChatGPT conversation",
                  "Read ai-lab/projects/roleplay-ios/CONTINUE_HERE.md and state.json "
                  "from the latest accessible GitHub branch before working.",
                  "Update state.json with verified evidence in the same PR as your changes.",
                  ""])
    return "\n".join(lines)

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Check state schema and evidence requirements")
    handoff = sub.add_parser("handoff", help="Export Markdown handoff")
    handoff.add_argument("--output")
    args = p.parse_args()
    state = read_state()
    if args.command == "validate":
        print("VALID: " + state["project_id"] + " / " + str(len(state["backlog"])) + " tasks")
        return
    content = generate_handoff(state)
    if args.output:
        file = Path(args.output)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    print(content)

if __name__ == "__main__":
    main()
