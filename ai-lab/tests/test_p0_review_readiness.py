"""Host-only tests for P0 GitHub PR review readiness; no real API calls."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("p0_review_readiness", ROOT / "ai-lab/p0_review_readiness.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MANIFEST = ROOT / "ai-lab/projects/roleplay-ios/P0_SOURCE_PROVENANCE.json"


class P0ReviewReadinessTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.audit = {
            "status": "p0-source-consistent", "source_verified": True,
            "blocking_checks": [], "source_count": 38,
            "p0_human_review_complete": False,
        }
        self.pr = {
            "number": 10, "state": "open", "draft": False, "mergeable": True,
            "user": {"login": "owner"},
            "head": {"ref": "feature/rp-p0-integration-preview-20261113",
                     "sha": "a"*40},
            "base": {"ref": "main", "sha": self.manifest["base_commit"]},
        }
        self.reviews = [{"user": {"login": "reviewer", "type": "User"},
                         "author_association": "COLLABORATOR",
                         "state": "APPROVED", "commit_id": "a"*40}]

    def check(self, ci_head=None):
        if ci_head is None:
            ci_head = "a"*40
        return mod.evaluate(self.pr, self.reviews, self.manifest, self.audit, ci_head)

    def test_approval_on_current_commit_is_only_advisory(self):
        result = self.check()
        self.assertEqual(result["status"], "ready-for-human-merge-decision")
        self.assertTrue(result["source_review_ready"])
        self.assertFalse(result["auto_merge_allowed"])
        self.assertFalse(result["p0_phase_verified_by_this_check"])
        self.assertFalse(result["device_gameplay_tested"])

    def test_draft_pr_still_blocks(self):
        self.pr["draft"] = True
        self.assertIn("not_draft", self.check()["blocking_checks"])

    def test_missing_review_blocks(self):
        self.reviews.clear()
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_self_approval_does_not_count(self):
        self.reviews[0]["user"]["login"] = "owner"
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_stale_review_does_not_count(self):
        self.reviews[0]["commit_id"] = "b"*40
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_latest_request_changes_supersedes_approval(self):
        self.reviews.append({"user": {"login": "reviewer"},
                             "state": "CHANGES_REQUESTED", "commit_id": "a"*40})
        blockers = self.check()["blocking_checks"]
        self.assertIn("independent_head_approval", blockers)
        self.assertIn("no_outstanding_changes_requested", blockers)

    def test_comment_after_approval_does_not_revoke_decision(self):
        self.reviews.append({
            "user": {"login": "reviewer", "type": "User"},
            "state": "COMMENTED", "commit_id": "a"*40,
        })
        self.assertTrue(self.check()["source_review_ready"])

    def test_comment_after_request_changes_does_not_clear_objection(self):
        self.reviews[0]["state"] = "CHANGES_REQUESTED"
        self.reviews.append({
            "user": {"login": "reviewer", "type": "User"},
            "state": "COMMENTED", "commit_id": "a"*40,
        })
        blockers = self.check()["blocking_checks"]
        self.assertIn("independent_head_approval", blockers)
        self.assertIn("no_outstanding_changes_requested", blockers)

    def test_dismissed_approval_does_not_count(self):
        self.reviews.append({
            "user": {"login": "reviewer", "type": "User"},
            "state": "DISMISSED", "commit_id": "a"*40,
        })
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_new_approval_resolves_previous_changes_requested(self):
        self.reviews.insert(0, {
            "user": {"login": "reviewer", "type": "User"},
            "state": "CHANGES_REQUESTED", "commit_id": "a"*40,
        })
        self.assertTrue(self.check()["source_review_ready"])

    def test_bot_approval_cannot_authorize_review(self):
        self.reviews[0]["user"]["type"] = "Bot"
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_external_untrusted_approval_cannot_authorize_review(self):
        self.reviews[0]["author_association"] = "NONE"
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_author_login_comparison_case_insensitive(self):
        self.reviews[0]["user"]["login"] = "OwNeR"
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_base_sha_drift_blocks(self):
        self.pr["base"]["sha"] = "c"*40
        self.assertIn("base_unchanged", self.check()["blocking_checks"])

    def test_merge_conflict_blocks(self):
        self.pr["mergeable"] = False
        self.assertIn("mergeable", self.check()["blocking_checks"])

    def test_failed_source_audit_blocks(self):
        self.audit["blocking_checks"] = ["git_blob:tampered"]
        self.assertIn("source_audit", self.check()["blocking_checks"])

    def test_wrong_preview_head_blocks(self):
        self.pr["head"]["ref"] = "unrelated-branch"
        self.assertIn("target_pr", self.check()["blocking_checks"])

    def test_no_approvals_after_head_update(self):
        self.pr["head"]["sha"] = "b"*40
        self.assertIn("independent_head_approval", self.check()["blocking_checks"])

    def test_new_commit_during_ci_invalidates_previous_review(self):
        # Simulates an approved new commit appearing while CI is still running
        # against the old event SHA. Approval alone must never hide the drift.
        self.pr["head"]["sha"] = "b"*40
        self.reviews[0]["commit_id"] = "b"*40
        blockers = self.check(ci_head="a"*40)["blocking_checks"]
        self.assertIn("head_matches_ci_event", blockers)
        self.assertNotIn("independent_head_approval", blockers)

    def test_missing_ci_head_sha_fails_closed(self):
        result = self.check(ci_head="")
        self.assertIn("head_matches_ci_event", result["blocking_checks"])
        self.assertFalse(result["source_review_ready"])

    def test_malformed_ci_head_sha_fails_closed(self):
        self.assertIn("head_matches_ci_event",
                      self.check(ci_head="not-a-sha")["blocking_checks"])

    def test_closed_pr_blocks(self):
        self.pr["state"] = "closed"
        self.assertIn("pr_open", self.check()["blocking_checks"])


if __name__ == "__main__":
    unittest.main()
