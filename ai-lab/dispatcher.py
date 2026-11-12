#!/usr/bin/env python3
"""Deterministic 100-role router with optional read-only Codex CLI execution."""
import argparse
import datetime as dt
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def load_agents():
    agents = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))["agents"]
    if len(agents) != 100 or len({a["id"] for a in agents}) != 100:
        raise ValueError("Agent registry must define 100 unique roles")
    return agents

def route(task, limit=5):
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    words = set(re.findall(r"[a-z0-9]+", task.lower()))
    words -= {"ios", "iphone", "ipad", "gta", "v", "game", "port",
              "mod", "app", "fix", "error", "bug", "code", "source", "v12", "v11", "v10"}
    agents = load_agents()
    document_frequency = Counter(k for a in agents for k in set(a["keywords"]))
    scores = []
    for a in agents:
        matches = words.intersection(a["keywords"])
        score = sum(1 + 12 / math.sqrt(document_frequency[k]) for k in matches)
        if a["name"].lower() in task.lower():
            score += 14
        scores.append((score, a))
    scores.sort(key=lambda x: (-x[0], x[1]["id"]))
    relevant = [a for s, a in scores if s > 0]
    if not relevant:
        defaults = ["RES-04", "RE-01", "QA-09", "OPS-05", "RES-10"]
        lookup = {a["id"]: a for a in agents}
        return [lookup[k] for k in defaults[:limit]]
    selected, teams = [], set()
    for a in relevant:
        if a["team"] not in teams:
            selected.append(a)
            teams.add(a["team"])
        if len(selected) >= limit:
            return selected
    for a in relevant:
        if a not in selected:
            selected.append(a)
        if len(selected) >= limit:
            break
    return selected

def prompt_for(task, agent):
    return (f"You are specialist {agent['id']}: {agent['name']}.\n"
            f"Mission: {agent['mission']}\n"
            "Follow AGENTS.md and ai-lab/AGENTS.md. Use read-only analysis, "
            "never reveal credentials or execute untrusted binaries. Mark claims "
            "as verified, static-analysis, or hypothesis; include risks, evidence, "
            "minimal fix, reproducible tests and rollback.\n"
            f"Task: {task}\n")

def plan(args):
    result = {"task": args.task, "status": "planned-not-executed",
              "agents": [{"id": a["id"], "name": a["name"], "team": a["team"],
                          "prompt": prompt_for(args.task, a)}
                         for a in route(args.task, args.top)]}
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(output)
    return 0

def run(args):
    if shutil.which("codex") is None:
        print("Codex CLI missing. Use 'plan' or install and authenticate Codex CLI.", file=sys.stderr)
        return 2
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = HERE / "reports" / stamp
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for agent in route(args.task, min(args.top, 3)):
        command = ["codex", "exec", "--sandbox", "read-only", "--ephemeral",
                   prompt_for(args.task, agent)]
        try:
            output = subprocess.run(command, cwd=ROOT, capture_output=True,
                                    text=True, check=False, timeout=args.timeout)
            (folder / (agent["id"] + ".md")).write_text(output.stdout, encoding="utf-8")
            (folder / (agent["id"] + ".stderr.txt")).write_text(
                output.stderr[:16000], encoding="utf-8")
            results.append({"agent": agent["id"], "exit_code": output.returncode})
        except subprocess.TimeoutExpired:
            results.append({"agent": agent["id"], "error": "timeout"})
    (folder / "manifest.json").write_text(
        json.dumps({"task": args.task, "results": results}, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"report_dir": str(folder), "results": results}, indent=2))
    return 0 if all(x.get("exit_code") == 0 for x in results) else 1

def main():
    parser = argparse.ArgumentParser(description="GTA V iOS AI Lab (100 roles, not 100 live AI models)")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("plan", help="Offline specialist routing")
    p.add_argument("--task", required=True)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--output")
    p.set_defaults(func=plan)
    q = subs.add_parser("run", help="Execute up to three read-only Codex CLI passes")
    q.add_argument("--task", required=True)
    q.add_argument("--top", type=int, default=2, choices=(1, 2, 3))
    q.add_argument("--timeout", type=int, default=600)
    q.set_defaults(func=run)
    args = parser.parse_args()
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
