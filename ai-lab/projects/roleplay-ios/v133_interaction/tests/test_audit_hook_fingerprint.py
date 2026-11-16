"""Regression for v12-versus-v13.3 hook site confusion (static only)."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[5]
SCRIPT = HERE.parents[1] / "tools" / "audit_hook_fingerprint.py"
SPEC = importlib.util.spec_from_file_location("audit_hook_fingerprint", SCRIPT)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class FingerprintGuardTests(unittest.TestCase):
    def test_real_v12_hook_candidates_rejected_for_v133(self):
        p = ROOT / "police-rp/v1.4/HOOK_CANDIDATES_V12.json"
        record = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(record["GTA5_UUID"].lower(), "6a498e32e70c334cbca3affd35e8d171")
        result = GUARD.audit_hook_record(record)
        self.assertEqual(result["classification"], "VERSION_MISMATCH_BLOCKED")
        self.assertFalse(result["may_hook_v133"])
        self.assertFalse(result["may_use_as_authenticated_sender"])

    def test_v13_named_report_actually_has_v12_fingerprint(self):
        p = ROOT / "police-rp/v1.4/DIAGNOSTIC_READONLY_REPORT_V13.json"
        report = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(report["input_gta5_uuid"].lower(), "6a498e32e70c334cbca3affd35e8d171")
        result = GUARD.audit_hook_record(report)
        self.assertEqual(result["classification"], "VERSION_MISMATCH_BLOCKED")
        self.assertFalse(result["exact_build_match"])

    def test_matching_uuid_and_sha_is_still_not_hook_proof(self):
        doc = {
            "GTA5_UUID": GUARD.V133_GTA5_UUID.lower().replace("-", ""),
            "GTA5_SHA256": GUARD.V133_GTA5_SHA256.upper(),
            "candidate_sites": {"MacportOnlineUpdate": {"vmaddr": "0x100000000"}}
        }
        result = GUARD.audit_hook_record(doc)
        self.assertEqual(result["classification"], "EXACT_BUILD_UNVERIFIED_HOOK")
        self.assertTrue(result["exact_build_match"])
        self.assertFalse(result["may_hook_v133"])
        self.assertTrue(result["needs_game_thread_proof"])
        self.assertTrue(result["needs_authenticated_sender_proof"])

    def test_uuid_only_or_sha_only_never_approves(self):
        for data in (
            {"GTA5_UUID": GUARD.V133_GTA5_UUID},
            {"GTA5_SHA256": GUARD.V133_GTA5_SHA256},
            {"GTA5_UUID": "junk", "GTA5_SHA256": GUARD.V133_GTA5_SHA256},
            {"GTA5_UUID": GUARD.V133_GTA5_UUID, "GTA5_SHA256": "bad-hash"},
            {},
        ):
            with self.subTest(data=data):
                result = GUARD.audit_hook_record(data)
                self.assertEqual(result["classification"], "INVALID_FINGERPRINT")
                self.assertFalse(result["may_hook_v133"])

    def test_invalid_document_rejected(self):
        for data in (None, [], "v13.3"):
            self.assertEqual(GUARD.audit_hook_record(data)["classification"], "INVALID_DOCUMENT")
            self.assertFalse(GUARD.audit_hook_record(data)["may_hook_v133"])


if __name__ == "__main__":
    unittest.main()
