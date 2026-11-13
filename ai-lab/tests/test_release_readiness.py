"""Host-only release gate tests. Synthetic declarations, never an IPA/device."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PATH = Path(__file__).resolve().parents[1] / "release_readiness.py"
spec = importlib.util.spec_from_file_location("release_readiness", PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.state = {"project_id": "gta-v-ios-roleplay", "baseline": {
            "ipa_sha256": "a" * 64, "executable_sha256": "b" * 64,
            "macho_uuid": "12345678-1234-1234-1234-1234567890AB",
            "actual_build_artifact": None, "device_tested": False}}
        self.baseline = {"ipa_sha256": "a" * 64, "executable": {
            "sha256": "b" * 64, "uuid": "12345678-1234-1234-1234-1234567890AB"}}

    def blocked(self):
        return gate.assess(self.state, self.baseline)["blocking_gates"]

    def test_no_device_or_transport_evidence_is_blocked(self):
        self.assertIn("device_tested", self.blocked())
        self.assertIn("authenticated_transport", self.blocked())
        self.assertIn("local_ipa_build", self.blocked())

    def test_wrong_ipa_hash_blocks(self):
        self.state["baseline"]["ipa_sha256"] = "c" * 64
        self.assertIn("baseline_ipa_identity", self.blocked())

    def test_bad_executable_hash_blocks(self):
        self.state["baseline"]["executable_sha256"] = "bad"
        self.assertIn("baseline_executable_identity", self.blocked())

    def test_bad_macho_uuid_blocks(self):
        self.state["baseline"]["macho_uuid"] = "bad"
        self.assertIn("baseline_macho_uuid", self.blocked())

    def test_false_evidence_is_rejected(self):
        self.state["release_evidence"] = {"authenticated_transport": {
            "status": "verified", "evidence": " ", "executable_sha256": "b" * 64}}
        self.assertIn("authenticated_transport", self.blocked())
        self.state["release_evidence"]["authenticated_transport"]["evidence"] = "synthetic-log"
        self.state["release_evidence"]["authenticated_transport"]["executable_sha256"] = "0" * 64
        self.assertIn("authenticated_transport", self.blocked())

    def test_nonboolean_device_claim_blocks(self):
        self.state["baseline"]["device_tested"] = "yes"
        self.assertIn("device_tested", self.blocked())

    def test_malformed_evidence_is_safe(self):
        self.state["release_evidence"] = ["not dict"]
        self.assertIn("regression", self.blocked())
        self.state["release_evidence"] = {"regression": ["not dict"]}
        self.assertIn("regression", self.blocked())

    def test_synthetic_full_attestation_is_never_auto_published(self):
        self.state["baseline"]["device_tested"] = True
        self.state["baseline"]["actual_build_artifact"] = "synthetic-local-build"
        self.state["release_evidence"] = {
            k: {"status": "verified", "evidence": "synthetic-test-ref", "executable_sha256": "b" * 64}
            for k, _ in gate.REQUIRED_ATTESTATIONS}
        self.state["release_evidence"]["manual_approval"] = {
            "approved": True, "evidence": "synthetic-review", "executable_sha256": "b" * 64}
        report = gate.assess(self.state, self.baseline)
        self.assertTrue(report["ready_for_manual_release_review"])
        self.assertFalse(report["auto_publish_allowed"])
        self.assertFalse(report["signed_ipa_created"])

    def test_strict_mode_fails_closed(self):
        with TemporaryDirectory() as td:
            p, q, report = (Path(td) / f for f in ("state.json", "baseline.json", "report.json"))
            p.write_text(json.dumps(self.state), encoding="utf-8")
            q.write_text(json.dumps(self.baseline), encoding="utf-8")
            self.assertEqual(gate.main(["--state", str(p), "--baseline", str(q),
                                       "--output", str(report), "--require-ready"]), 2)
            self.assertFalse(json.loads(report.read_text())["ready_for_manual_release_review"])

    def test_invalid_structure_raises(self):
        with self.assertRaises(ValueError):
            gate.assess([], {})
        with self.assertRaises(ValueError):
            gate.assess({"baseline": []}, {})


if __name__ == "__main__":
    unittest.main()
