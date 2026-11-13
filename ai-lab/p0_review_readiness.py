#!/usr/bin/env python3
"""P0 GitHub review-readiness report. Read-only; NEVER merges a PR.

Inputs: live PR/review metadata plus locally computed pinned-source audit.
Reports blockers without auto-promoting phase P0. No IPA/game data processed.
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "ai-lab/reports/RP_P0_AUDIT.json"
MANIFEST = ROOT / "ai-lab/projects/roleplay-ios/P0_SOURCE_PROVENANCE.json"


def evaluate(pr, reviews, manifest, audit):
    """Check exact integration head and independent reviewer status, fail-closed."""
    if not all(isinstance(x, dict) for x in (pr, manifest, audit)):
        raise ValueError("PR, manifest, and audit must be JSON objects")
    if not isinstance(reviews, list):
        raise ValueError("GitHub reviews must be an array")
    checks = []

    def require(name, passed, detail):
        checks.append({"id": name, "passed": bool(passed), "detail": detail})

    base = pr.get("base") or {}
    head = pr.get("head") or {}
    author = pr.get("user") or {}
    if not all(isinstance(x, dict) for x in (base, head, author)):
        base = head = author = {}
    source_heads = manifest.get("source_heads")
    require("source_manifest", manifest.get("schema_version") == 1 and
            manifest.get("automerge_allowed") is False and
            isinstance(source_heads, list) and len(source_heads) == 4,
            "Pinned source PRs and review-only manifest")
    require("source_audit", audit.get("status") == "p0-source-consistent" and
            audit.get("source_verified") is True and
            audit.get("blocking_checks") == [] and
            audit.get("source_count") == manifest.get("expected_copied_file_count") and
            audit.get("p0_human_review_complete") is False,
            "Current preview source audit must pass; source alone is not review")
    require("target_pr", pr.get("number") == 10 and
            head.get("ref") == manifest.get("preview_branch") and
            base.get("ref") == "main",
            "P0 review is for PR #10, exact preview branch into main")
    require("pr_open", pr.get("state") == "open", "PR must still be open")
    require("not_draft", pr.get("draft") is False, "Draft PR requires explicit readiness transition")
    require("base_unchanged", base.get("sha") == manifest.get("base_commit"),
            "main SHA must match pinned source base; re-audit on base drift")
    require("mergeable", pr.get("mergeable") is True, "GitHub reports mergeable=true")
    require("head_sha_valid", isinstance(head.get("sha"), str) and
            len(head["sha"]) == 40 and all(c in "0123456789abcdef" for c in head["sha"]),
            "Exact SHA of current PR head must be known")
    latest_by_user = {}
    for rev in reviews:
        if not isinstance(rev, dict):
            continue
        reviewer = rev.get("user") or {}
        if not isinstance(reviewer, dict):
            continue
        name = reviewer.get("login")
        if isinstance(name, str) and name:
            # GitHub REST returns submissions in chronological order.
            latest_by_user[name] = rev
    author_name = author.get("login")
    latest = {name: rev for name, rev in latest_by_user.items() if name != author_name}
    head_sha = head.get("sha")
    approvals = sorted(name for name, rev in latest.items()
                       if rev.get("state") == "APPROVED" and
                       rev.get("commit_id") == head_sha)
    objections = sorted(name for name, rev in latest.items()
                        if rev.get("state") == "CHANGES_REQUESTED")
    require("independent_head_approval", bool(approvals),
            "Requires non-author APPROVED review on exact current head commit")
    require("no_outstanding_changes_requested", not objections,
            "Latest non-author reviews must not request changes")
    passed = all(c["passed"] for c in checks)
    return {
        "schema_version": 1,
        "status": "ready-for-human-merge-decision" if passed else "blocked-review",
        "source_review_ready": passed,
        "pr_number": pr.get("number"),
        "head_sha": head_sha,
        "approved_reviewer_count": len(approvals),
        "blocking_checks": [c["id"] for c in checks if not c["passed"]],
        "checks": checks,
        "auto_merge_allowed": False,
        "p0_phase_verified_by_this_check": False,
        "auto_release_allowed": False,
        "device_gameplay_tested": False,
        "scope": "GitHub draft/review/mergeability and pinned source audit only; not IPA/device proof",
    }


def fetch_json(url, token):
    if not url.startswith("https://api.github.com/"):
        raise ValueError("Only GitHub API HTTPS endpoint allowed")
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gta-ios-p0-review-readiness",
        "Authorization": "Bearer " + token,
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(1_048_577)
        if len(data) > 1_048_576:
            raise ValueError("Oversize GitHub REST response")
        return json.loads(data)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default="hachnghi-cyber/GTA5-iOS-AI-Development")
    p.add_argument("--pr", type=int, default=10)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--audit", type=Path, default=AUDIT)
    p.add_argument("--output", type=Path)
    p.add_argument("--require-ready", action="store_true",
                   help="Exit 2 when an independent approved PR is not ready")
    args = p.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = args.repo
    if repo != "hachnghi-cyber/GTA5-iOS-AI-Development" or args.pr != 10:
        raise ValueError("Only authorized project P0 review PR #10 supported")
    if not token:
        report = {
            "status": "blocked-review",
            "blocking_checks": ["no_github_token"],
            "source_review_ready": False, "auto_merge_allowed": False,
            "auto_release_allowed": False, "p0_phase_verified_by_this_check": False,
            "scope": "No GitHub credentials available; cannot confirm live review state",
        }
    else:
        root = "https://api.github.com/repos/" + repo
        try:
            pr = fetch_json(root + "/pulls/10", token)
            # Full review history, up to a bounded 1,000 submissions.
            reviews = []
            for page in range(1, 11):
                batch = fetch_json(root + "/pulls/10/reviews?per_page=100&page=" + str(page), token)
                if not isinstance(batch, list):
                    raise ValueError("Reviews API returned non-array")
                reviews.extend(batch)
                if len(batch) < 100:
                    break
            else:
                raise ValueError("Review pagination exceeded safe bound")
            report = evaluate(pr, reviews, manifest, audit)
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as exc:
            report = {
                "status": "blocked-review", "blocking_checks": ["github_review_query_failed"],
                "source_review_ready": False,
                "error_type": type(exc).__name__,
                "auto_merge_allowed": False,
                "auto_release_allowed": False,
                "p0_phase_verified_by_this_check": False,
                "scope": "Unable to independently confirm live PR reviews",
            }
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 2 if args.require_ready and not report["source_review_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
