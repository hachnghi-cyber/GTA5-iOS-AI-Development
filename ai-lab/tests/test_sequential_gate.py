"""Fail-closed checks for ordered GTA v12 RP execution phases."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sequential_gate", ROOT / "sequential_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
PLAN = ROOT / "projects/roleplay-ios/PHASE_GATES.json"
STATE = ROOT / "projects/roleplay-ios/state.json"


class SequentialGateTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_real_plan_starts_at_p0_and_never_authorizes_release(self):
        result = gate.validate(self.plan, self.state)
        self.assertEqual(result["current_phase"], "P0")
        self.assertEqual(result["verified_prefix_count"], 0)
        self.assertFalse(result["auto_merge_allowed"])
        self.assertFalse(result["auto_release_allowed"])
        self.assertFalse(result["gameplay_tested_by_this_check"])

    def test_reject_skipping_p0(self):
        self.plan["stages"][1]["status"] = "in-progress"
        with self.assertRaisesRegex(ValueError, "first unverified"):
            gate.validate(self.plan, self.state)

    def test_reject_unreviewed_p0(self):
        self.plan["stages"][0]["status"] = "verified"
        with self.assertRaisesRegex(ValueError, "evidence"):
            gate.validate(self.plan, self.state)

    def test_reviewed_p0_allows_p1_to_begin_without_auto_release(self):
        p0 = self.plan["stages"][0]
        p0["status"] = "verified"
        p0["gate_evidence"] = ["synthetic-CI-evidence"]
        p0["reviewed_by"] = "test-only-reviewer"
        self.plan["stages"][1]["status"] = "in-progress"
        self.state["sequential_execution"]["current_phase"] = "P1"
        result = gate.validate(self.plan, self.state)
        self.assertEqual(result["current_phase"], "P1")
        self.assertEqual(result["verified_prefix_count"], 1)
        self.assertFalse(result["auto_release_allowed"])

    def test_reject_verified_p2_if_p1_is_blocked(self):
        stage = self.plan["stages"][2]
        stage["status"] = "verified"
        stage["gate_evidence"] = ["synthetic-proof"]
        stage["reviewed_by"] = "test-reviewer"
        with self.assertRaisesRegex(ValueError, "unverified prerequisite"):
            gate.validate(self.plan, self.state)

    def test_reject_duplicate_phase_id(self):
        self.plan["stages"][4]["id"] = "P3"
        with self.assertRaisesRegex(ValueError, "ordering"):
            gate.validate(self.plan, self.state)

    def test_reject_bad_evidence_format(self):
        self.plan["stages"][0]["gate_evidence"] = ["", None]
        with self.assertRaisesRegex(ValueError, "gate_evidence"):
            gate.validate(self.plan, self.state)

    def test_p9_requires_device_test_and_manual_approval(self):
        for phase in self.plan["stages"]:
            phase["status"] = "verified"
            phase["gate_evidence"] = ["synthetic-ref"]
            phase["reviewed_by"] = "synthetic-reviewer"
        with self.assertRaisesRegex(ValueError, "device"):
            gate.validate(self.plan, self.state)
        self.state["baseline"]["device_tested"] = True
        with self.assertRaisesRegex(ValueError, "approval"):
            gate.validate(self.plan, self.state)
        self.state["release_evidence"] = {"manual_approval": {"approved": True}}
        self.state["sequential_execution"]["current_phase"] = None
        result = gate.validate(self.plan, self.state)
        self.assertEqual(result["status"], "all-gates-declared-verified")
        self.assertFalse(result["auto_release_allowed"])

    def test_state_and_plan_phase_disagreement_fails(self):
        self.state["sequential_execution"]["current_phase"] = "P1"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            gate.validate(self.plan, self.state)

    def test_boolean_order_is_not_integer(self):
        self.plan["stages"][0]["order"] = False
        with self.assertRaisesRegex(ValueError, "ordering"):
            gate.validate(self.plan, self.state)


if __name__ == "__main__":
    unittest.main()
