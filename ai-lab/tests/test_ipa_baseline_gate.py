import hashlib
import importlib.util
import json
import struct
import tempfile
from unittest import mock
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_ipa_baseline", HERE / "verify_ipa_baseline.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def sample(uuid=bytes.fromhex("6A498E32E70C334CBCA3AFFD35E8D171")):
    # Little-endian MH_MAGIC_64; one LC_UUID command.
    header = struct.pack("<IIIIIIII", 0xfeedfacf, 0x0100000c, 0, 2, 1, 24, 0, 0)
    command = struct.pack("<II", 0x1b, 24) + uuid
    return header + command + b"\x00" * 128

class BaselineGateTests(unittest.TestCase):
    def test_valid_uuid_and_sha(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            ipa, cfg = p/"game.ipa", p/"baseline.json"
            exe = sample()
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr("Payload/GTAV.app/GTA5", exe)
            cfg.write_text(json.dumps({"executable": {
                "sha256": hashlib.sha256(exe).hexdigest(),
                "uuid": "6A498E32-E70C-334C-BCA3-AFFD35E8D171"}}))
            result = mod.verify(ipa, cfg)
            self.assertTrue(result["version_gate_passed"])
            self.assertEqual(result["status"], "matched-executable")
    def test_reject_mismatched_binary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            ipa, cfg = p/"game.ipa", p/"baseline.json"
            exe = sample() + b"patched"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr("Payload/GTAV.app/GTA5", exe)
            cfg.write_text(json.dumps({"executable": {
                "sha256": "0" * 64,
                "uuid": "6A498E32-E70C-334C-BCA3-AFFD35E8D171"}}))
            self.assertFalse(mod.verify(ipa, cfg)["version_gate_passed"])
    def test_duplicate_executable_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ipa = Path(d)/"game.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                with mock.patch("warnings.warn"):
                    z.writestr("Payload/GTAV.app/GTA5", sample())
                    z.writestr("Payload/GTAV.app/GTA5", sample())
            with self.assertRaisesRegex(ValueError, "exactly one"):
                mod.executable_fingerprint(ipa)

if __name__ == "__main__":
    unittest.main()
