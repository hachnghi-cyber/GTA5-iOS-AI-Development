#!/usr/bin/env python3
"""P0 source integration provenance audit (read-only, no network/IPA access).

Verifies that every source blob copied into the P0 preview is byte-identical
to the pinned GitHub PR blob recorded by the human-review manifest. Also
checks reconciled state claims and v12 baseline metadata. This is *not*
a code audit, notarization, real iPhone test, or authorization to merge.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = ROOT / "ai-lab/projects/roleplay-ios"
MANIFEST = DOCUMENTS / "P0_SOURCE_PROVENANCE.json"
STATE = DOCUMENTS / "state.json"
PHASES = DOCUMENTS / "PHASE_GATES.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_EXTENSIONS = frozenset({".py", ".c", ".h", ".md", ".json", ".yml", ".yaml"})


def git_blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def _relative_path(path):
    if not isinstance(path, str) or not path:
        return False
    pure = PurePosixPath(path)
    return (not pure.is_absolute() and "\\" not in path and
            all(part not in ("", ".", "..") for part in path.split("/")) and
            pure.suffix.lower() in SAFE_EXTENSIONS)


def audit(root, manifest, state, phases):
    """Produce a falsifiable report. Failing checks never certify P0."""
    root = Path(root)
    checks = []

    def add(check_id, ok, detail):
        checks.append({"id": check_id, "passed": bool(ok), "detail": detail})

    if not isinstance(manifest, dict) or not isinstance(state, dict) or not isinstance(phases, dict):
        raise ValueError("manifest, state and phases must be objects")
    files = manifest.get("source_files")
    if not isinstance(files, list):
        raise ValueError("source_files must be a list")
    add("manifest_schema", manifest.get("schema_version") == 1 and
        manifest.get("kind") == "P0-source-provenance-review-only" and
        manifest.get("automerge_allowed") is False and
        manifest.get("auto_release_allowed") is False,
        "Review-only P0 manifest, no automatic merge or release")
    add("file_count", len(files) == manifest.get("expected_copied_file_count") and
        len(files) > 0, f"Declared {len(files)} source files")
    source_heads = manifest.get("source_heads", [])
    add("source_commits", isinstance(source_heads, list) and len(source_heads) == 4 and
        {x.get("number") for x in source_heads if isinstance(x, dict)} == {4, 7, 8, 9} and
        all(isinstance(x, dict) and isinstance(x.get("commit"), str)
            and HEX40.fullmatch(x["commit"]) for x in source_heads),
        "Immutable source head commit IDs declared for four upstream PRs")
    seen = set()
    counts = {}
    for item in files:
        if not isinstance(item, dict):
            add("source_entry_invalid", False, "Malformed source path record")
            continue
        path, sha, pr = item.get("path"), item.get("expected_git_blob_sha1"), item.get("pr")
        if not _relative_path(path) or not isinstance(sha, str) or not HEX40.fullmatch(sha):
            add("invalid_source", False, f"Unsafe or invalid source record: {path!r}")
            continue
        if path in seen or path == "ai-lab/projects/roleplay-ios/state.json":
            add("duplicate_or_reconciled_path", False, f"Duplicate or explicitly merged: {path}")
            continue
        seen.add(path)
        counts[pr] = counts.get(pr, 0) + 1
        expected_source = root.joinpath(*path.split("/"))
        if expected_source.is_symlink() or not expected_source.is_file():
            add("missing_source", False, f"Missing/symlink: {path}")
            continue
        actual = git_blob_hash(expected_source.read_bytes())
        add("git_blob:" + path, actual == sha,
            f"Source: {path}; pinned PR #{pr}; git blob SHA1 {actual}")
    add("source_coverage", len(seen) == len(files), "Each source file checked once")
    add("per_pr_presence", all(counts.get(n, 0) > 0 for n in (4, 7, 8, 9)),
        "Each PR contributes at least one matched source file")

    baseline = state.get("baseline")
    pinned = manifest.get("baseline_metadata")
    if not isinstance(baseline, dict) or not isinstance(pinned, dict):
        add("baseline", False, "Missing baseline metadata")
    else:
        add("baseline", all(baseline.get(k) == pinned.get(k) for k in
            ("ipa_sha256", "executable_sha256", "macho_uuid")) and
            baseline.get("device_tested") is False and
            baseline.get("actual_build_artifact") is None,
            "Pinned v12 SHA256/UUID; no IPA built or iPhone tested in P0")
    execution = state.get("sequential_execution")
    stages = phases.get("stages")
    add("phase_p0", isinstance(execution, dict) and
        execution.get("current_phase") == "P0" and
        execution.get("auto_release_allowed") is False and
        state.get("phase") == "p0-repository-baseline-pr-review" and
        isinstance(stages, list) and len(stages) == 10 and
        stages[0].get("status") == "in-progress" and
        all(s.get("status") != "verified" for s in stages),
        "P0 remains in progress and no stage is pre-approved")
    claims = manifest.get("required_verified_facts")
    facts = state.get("verified_facts")
    if not isinstance(claims, list) or not isinstance(facts, list):
        add("fact_inventory", False, "Required evidence inventory not found")
    else:
        add("fact_count", manifest.get("expected_unique_fact_count") == len(claims) and
            len(claims) > 0, f"Declared {len(claims)} unique source claims")
        for i, fact in enumerate(claims):
            if not isinstance(fact, dict):
                add("invalid_fact", False, f"Invalid expected fact at index {i}")
                continue
            add("fact:" + str(i), fact in facts,
                "Preserve source evidence claim, scope, and citation: " +
                str(fact.get("claim", ""))[:90])
    passed = all(v["passed"] for v in checks)
    return {
        "schema_version": 1, "status": "p0-source-consistent" if passed else "blocked",
        "source_verified": passed,
        "source_count": len(files),
        "required_fact_count": len(claims) if isinstance(claims, list) else None,
        "checks": checks,
        "blocking_checks": [c["id"] for c in checks if not c["passed"]],
        "verified_on_iphone": False,
        "p0_human_review_complete": False,
        "auto_merge_allowed": False,
        "auto_release_allowed": False,
        "scope": "git blob identity and metadata reconciliation; NOT an iOS gameplay validation",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--state", type=Path, default=STATE)
    p.add_argument("--phases", type=Path, default=PHASES)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    manifest, state, phases = (
        json.loads(path.read_text(encoding="utf-8")) for path in
        (args.manifest, args.state, args.phases)
    )
    report = audit(args.root, manifest, state, phases)
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)
    return 0 if report["source_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
