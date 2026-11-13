#!/usr/bin/env python3
"""Read-only strict ordering gate for RP project phases P0..P9.

A stage may be marked verified ONLY with nonempty evidence and an identified
reviewer, after all earlier stages are verified. This validates DECLARATIONS,
not source authenticity, iPhone gameplay, or permission to publish an IPA.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "projects" / "roleplay-ios"
PLAN = ROOT / "PHASE_GATES.json"
STATE = ROOT / "state.json"
ORDER = tuple("P" + str(i) for i in range(10))
STATUSES = frozenset(("not-started", "blocked", "in-progress", "verified"))


def validate(plan, state=None):
    if not isinstance(plan, dict) or plan.get("schema_version") != 1 or plan.get("strict_order") is not True:
        raise ValueError("phase gate schema and strict_order required")
    stages = plan.get("stages")
    if not isinstance(stages, list) or len(stages) != len(ORDER):
        raise ValueError("P0-P9 stages must all be present")
    first_unverified = None
    for i, phase in enumerate(stages):
        if not isinstance(phase, dict):
            raise ValueError("phase must be an object")
        phase_id = ORDER[i]
        expected_deps = [ORDER[i - 1]] if i else []
        if (phase.get("id") != phase_id or
                type(phase.get("order")) is not int or phase["order"] != i or
                phase.get("depends_on") != expected_deps):
            raise ValueError("phase ordering/dependency mismatch at " + phase_id)
        status = phase.get("status")
        if status not in STATUSES:
            raise ValueError("invalid stage status: " + phase_id)
        if not isinstance(phase.get("name"), str) or not phase["name"].strip():
            raise ValueError("missing phase name: " + phase_id)
        if not isinstance(phase.get("exit_criterion"), str) or not phase["exit_criterion"].strip():
            raise ValueError("missing exit criterion: " + phase_id)
        evidence = phase.get("gate_evidence")
        if not isinstance(evidence, list) or not all(isinstance(x, str) and x.strip() for x in evidence):
            raise ValueError("gate_evidence must be an array of nonempty strings: " + phase_id)
        reviewer = phase.get("reviewed_by")
        if reviewer is not None and (not isinstance(reviewer, str) or not reviewer.strip()):
            raise ValueError("reviewed_by must be a nonempty string or null: " + phase_id)
        if first_unverified is None and status != "verified":
            first_unverified = i
        if status == "verified":
            if first_unverified is not None:
                raise ValueError("cannot skip an unverified prerequisite before " + phase_id)
            if not evidence or not reviewer:
                raise ValueError("verified phase requires evidence and human reviewer: " + phase_id)
        if status == "in-progress" and first_unverified != i:
            raise ValueError("only the first unverified phase may be in-progress: " + phase_id)
    if state is not None:
        if not isinstance(state, dict):
            raise ValueError("project state must be a JSON object")
        # A completed release with an untested source baseline is prohibited.
        if stages[-1]["status"] == "verified":
            baseline = state.get("baseline", {})
            if not isinstance(baseline, dict) or baseline.get("device_tested") is not True:
                raise ValueError("P9 requires real on-device test evidence in project baseline")
            release_evidence = state.get("release_evidence", {})
            if not isinstance(release_evidence, dict):
                raise ValueError("P9 requires manual release approval")
            approval = release_evidence.get("manual_approval")
            if not isinstance(approval, dict) or approval.get("approved") is not True:
                raise ValueError("P9 requires explicit manual release approval")
    phase = stages[first_unverified] if first_unverified is not None else None
    if state is not None and "sequential_execution" in state:
        execution = state["sequential_execution"]
        expected_phase = phase["id"] if phase else None
        if (not isinstance(execution, dict) or
                execution.get("strict_order") is not True or
                execution.get("current_phase") != expected_phase):
            raise ValueError("state.json sequential_execution phase conflicts with gate plan")
    return {
        "schema_version": 1,
        "status": "all-gates-declared-verified" if phase is None else "work-in-progress",
        "current_phase": phase["id"] if phase else None,
        "current_phase_status": phase["status"] if phase else None,
        "next_exit_criterion": phase["exit_criterion"] if phase else None,
        "verified_prefix_count": len(ORDER) if phase is None else first_unverified,
        "auto_merge_allowed": False,
        "auto_release_allowed": False,
        "gameplay_tested_by_this_check": False,
        "scope": "declaration ordering only; check documentary and device evidence independently",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    report = validate(plan, state)
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
