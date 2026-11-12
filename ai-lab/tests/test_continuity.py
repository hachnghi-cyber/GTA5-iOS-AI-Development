import copy
import importlib.util
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("continuity", root / "continuity.py")
continuity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(continuity)

class ContinuityTests(unittest.TestCase):
    def test_state_schema(self):
        state = continuity.read_state()
        self.assertEqual(state["project_id"], "gta-v-ios-roleplay")
    def test_handoff_contains_next_action(self):
        state = continuity.read_state()
        markdown = continuity.generate_handoff(state)
        self.assertIn(state["next_action"], markdown)
        self.assertIn("RP-001", markdown)
    def test_completed_tasks_must_have_evidence(self):
        state = copy.deepcopy(continuity.read_state())
        state["backlog"][0]["status"] = "complete"
        state["backlog"][0].pop("evidence", None)  # enforce missing-evidence scenario
        with self.assertRaisesRegex(ValueError, "evidence"):
            continuity.validate(state)
    def test_no_fake_device_test(self):
        self.assertFalse(continuity.read_state()["baseline"]["device_tested"])

if __name__ == "__main__":
    unittest.main()
