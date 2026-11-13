"""P0 proof: copied Git blobs and reconciled source evidence are immutable.

Host-only assertions. No IPA data, signing or device session inspected.
"""
import copy
import importlib.util
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "p0_integration_audit", ROOT / "ai-lab/p0_integration_audit.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

MANIFEST = ROOT / "ai-lab/projects/roleplay-ios/P0_SOURCE_PROVENANCE.json"
STATE = ROOT / "ai-lab/projects/roleplay-ios/state.json"
PHASES = ROOT / "ai-lab/projects/roleplay-ios/PHASE_GATES.json"
PREVIEW = "feature/rp-p0-integration-preview-20261113"


class P0IntegrationAuditTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.state = json.loads(STATE.read_text(encoding="utf-8"))
        self.phases = json.loads(PHASES.read_text(encoding="utf-8"))

    def run_audit(self):
        return gate.audit(ROOT, self.manifest, self.state, self.phases)

    def test_manifest_covers_exactly_38_unique_source_pr_paths(self):
        self.assertEqual(self.manifest["expected_copied_file_count"], 38)
        self.assertEqual(len(self.manifest["source_files"]), 38)
        self.assertEqual(len({x["path"] for x in self.manifest["source_files"]}), 38)

    def test_pinned_copy_matches_upstream_only_on_preview_branch(self):
        if PREVIEW not in (os.getenv("GITHUB_REF_NAME"),
                           os.getenv("GITHUB_HEAD_REF")):
            self.skipTest("Frozen P0 provenance applies only on its source review branch")
        result = self.run_audit()
        self.assertTrue(result["source_verified"], result["blocking_checks"])
        self.assertEqual(result["source_count"], 38)
        self.assertFalse(result["auto_merge_allowed"])
        self.assertFalse(result["auto_release_allowed"])

    def test_unauthorized_changed_copy_is_blocked(self):
        self.manifest["source_files"][0]["expected_git_blob_sha1"] = "0"*40
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertTrue(any(x.startswith("git_blob:") for x in report["blocking_checks"]))

    def test_changed_workflow_without_matching_review_hash_is_blocked(self):
        override = self.manifest["review_overrides"][0]
        override["reviewed_integration_git_blob_sha1"] = "0"*40
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertIn("git_blob:" + override["path"], report["blocking_checks"])

    def test_review_override_for_unlisted_source_is_blocked(self):
        self.manifest["review_overrides"].append({
            "path": "ai-lab/not-in-source.py",
            "original_git_blob_sha1": "a"*40,
            "reviewed_integration_git_blob_sha1": "b"*40,
            "reason": "synthetic invalid review",
        })
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertIn("override_coverage", report["blocking_checks"])

    def test_missing_source_is_blocked(self):
        self.manifest["source_files"][0]["path"] = "missing/definitely_not_a_file.c"
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertIn("missing_source", report["blocking_checks"])

    def test_duplicate_source_is_blocked(self):
        self.manifest["source_files"][1]["path"] = self.manifest["source_files"][0]["path"]
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertIn("duplicate_or_reconciled_path", report["blocking_checks"])

    def test_reject_injected_binary_path(self):
        self.manifest["source_files"][0]["path"] = "Payload/GTA.app/GTA5"
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertIn("invalid_source", report["blocking_checks"])

    def test_reject_dropped_evidence(self):
        self.state["verified_facts"] = self.state["verified_facts"][1:]
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertTrue(any(x.startswith("fact:") for x in report["blocking_checks"]))

    def test_reject_evidence_text_rewriting(self):
        self.state["verified_facts"][0]["scope"] = "altered"
        report = self.run_audit()
        self.assertFalse(report["source_verified"])
        self.assertTrue(any(x.startswith("fact:") for x in report["blocking_checks"]))

    def test_reject_false_iphone_claim(self):
        self.state["baseline"]["device_tested"] = True
        self.assertIn("baseline", self.run_audit()["blocking_checks"])

    def test_preserves_rp006_source_progress(self):
        task = next(t for t in self.state["backlog"] if t["id"] == "RP-006")
        self.assertEqual(task["status"], "in-progress")
        self.assertNotEqual(self.phases["stages"][9]["status"], "verified")
        self.assertTrue(self.run_audit()["source_verified"])

    def test_reject_rp006_status_regression(self):
        task = next(t for t in self.state["backlog"] if t["id"] == "RP-006")
        task["status"] = "not-started"
        report = self.run_audit()
        self.assertIn("task:RP-006", report["blocking_checks"])

    def test_reject_missing_release_readiness_evidence(self):
        task = next(t for t in self.state["backlog"] if t["id"] == "RP-006")
        task["evidence"].remove("ai-lab/release_readiness.py")
        self.assertIn("task:RP-006", self.run_audit()["blocking_checks"])

    def test_reject_lost_pr9_bridge_metadata(self):
        task = next(t for t in self.state["backlog"] if t["id"] == "RP-003")
        task.pop("consent_outage_retry", None)
        self.assertIn("task:RP-003", self.run_audit()["blocking_checks"])

    def test_reject_missing_task_progress_manifest(self):
        self.manifest.pop("required_task_progress")
        self.assertIn("task_inventory", self.run_audit()["blocking_checks"])

    def test_reject_gate_promoted_without_review(self):
        self.phases["stages"][0]["status"] = "verified"
        self.assertIn("phase_p0", self.run_audit()["blocking_checks"])


if __name__ == "__main__":
    unittest.main()
