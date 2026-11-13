import copy
import importlib.util
import json
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "rp_identity_gate.py"
spec = importlib.util.spec_from_file_location("rp_identity_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class RPIdentityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads(gate.STATE.read_text(encoding="utf-8"))
        cls.evidence = json.loads(gate.BASELINE.read_text(encoding="utf-8"))

    def test_committed_baseline_agrees(self):
        self.assertEqual(gate.validate_identity(self.state, self.evidence), [])

    def test_wrong_executable_hash_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["executable"]["sha256"] = "0" * 64
        self.assertTrue(gate.validate_identity(self.state, evidence))

    def test_missing_uuid_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["executable"].pop("uuid")
        self.assertTrue(gate.validate_identity(self.state, evidence))

    def test_wrong_architecture_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["executable"]["architecture"] = "x86_64"
        self.assertTrue(gate.validate_identity(self.state, evidence))

    def test_device_claim_rejected(self):
        state = copy.deepcopy(self.state)
        state["baseline"]["device_tested"] = True
        self.assertTrue(gate.validate_identity(state, self.evidence))

    def test_count_mismatch_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["observed_native_binary_count"] += 1
        self.assertTrue(gate.validate_identity(self.state, evidence))


if __name__ == "__main__":
    unittest.main()
