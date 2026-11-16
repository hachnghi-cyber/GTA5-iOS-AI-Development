import unittest
from evaluate_e0_log import evaluate

FIRST = """[RBP_E0] RUN_BEGIN VERSION=1 pid=1 timestamp_ms=111
[RBP_E0] DLLMAIN_ATTACH
[RBP_E0] SCRIPT_HOOK_UUID_MATCH=1
[RBP_E0] SCRIPT_REGISTER_ATTEMPTED=1 (void API)
[RBP_E0] CALLBACK_ENTER
[RBP_E0] SCRIPT_TICK=1
[RBP_E0] SCRIPT_TICK=30
[RBP_E0] SCRIPT_TICK=120
[RBP_E0] SCRIPT_CALLBACK_COMPLETE=1
"""
SECOND = "[RBP_E0] RUN_BEGIN VERSION=1 pid=2 timestamp_ms=222\n[RBP_E0] DLLMAIN_ATTACH\n"
class LogClassifier(unittest.TestCase):
    def test_complete(self):
        self.assertEqual(evaluate(FIRST)["status"], "LOG_CONSISTENT_NOT_DEVICE_PROOF")
    def test_empty(self):
        self.assertEqual(evaluate("")["status"], "NO_RUN_MARKER")
    def test_stale_success(self):
        self.assertFalse(evaluate(FIRST+SECOND)["pass"])
    def test_order(self):
        broken=FIRST.replace("[RBP_E0] CALLBACK_ENTER\n[RBP_E0] SCRIPT_TICK=1",
                             "[RBP_E0] SCRIPT_TICK=1\n[RBP_E0] CALLBACK_ENTER")
        self.assertEqual(evaluate(broken)["status"], "OUT_OF_ORDER")
    def test_uuid_failure(self):
        self.assertEqual(evaluate(FIRST+"[RBP_E0] SCRIPT_HOOK_UUID_MATCH=0 FAIL_CLOSED\n")["status"],"FAIL_CLOSED")
    def test_fast_return(self):
        self.assertEqual(evaluate(FIRST+"[RBP_E0] SCRIPT_WAIT_FAST_RETURN=1 FAIL_CLOSED\n")["status"],"FAIL_CLOSED")
    def test_missing_completion(self):
        self.assertEqual(evaluate(FIRST.replace("[RBP_E0] SCRIPT_CALLBACK_COMPLETE=1\n",""))["status"],"INCOMPLETE_LAST_RUN")
    def test_host_mock_rejected(self):
        self.assertEqual(evaluate(FIRST+"[RBP_E0] SCRIPT_HOOK_UUID_CHECK=HOST_MOCK_ONLY\n")["status"],"FAIL_CLOSED")
    def test_no_cross_run(self):
        self.assertEqual(evaluate(SECOND+"[RBP_E0] SCRIPT_TICK=1\n")["status"],"INCOMPLETE_LAST_RUN")
if __name__ == "__main__":
    unittest.main()
