import importlib.util
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "continuous_watch.py"
spec = importlib.util.spec_from_file_location("continuous_watch", source)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

class ContinuousWatchTests(unittest.TestCase):
    def mock(self):
        return {
            "project_id":"gta-v-ios-roleplay",
            "baseline":{"ipa_sha256":"abc"},
            "backlog":[
                {"id":"RP-001","title":"IPA","priority":1,"status":"in-progress","blocked_on":["device"]},
                {"id":"RP-003","title":"Source","priority":3,"status":"in-progress","blocked_on":[]},
                {"id":"RP-006","title":"iPhone","priority":6,"status":"not-started","blocked_on":["RP-001"]}],
            "next_action":"Continue source inspection"
        }
    def test_ready_task_skips_blockers(self):
        result=watch.snapshot(self.mock(),{"ipa_sha256":"abc","executable":{"sha256":"def"}})
        self.assertEqual(result["next_task"],"RP-003")
        self.assertEqual(result["blocked_tasks"],["RP-001","RP-006"])
        self.assertTrue(result["verified_ipa_baseline"])
    def test_modified_baseline_is_not_verified(self):
        result=watch.snapshot(self.mock(),{"ipa_sha256":"other"})
        self.assertFalse(result["verified_ipa_baseline"])
    def test_no_task_when_everything_blocked(self):
        s=self.mock()
        for t in s["backlog"]:
            t["status"]="blocked"
        self.assertIsNone(watch.snapshot(s,{"ipa_sha256":"abc"})["next_task"])

if __name__=="__main__":
    unittest.main()
