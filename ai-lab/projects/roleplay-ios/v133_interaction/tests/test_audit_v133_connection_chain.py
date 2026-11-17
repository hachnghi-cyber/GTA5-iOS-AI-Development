"""Synthetic parser/pin contract; no game binary required on GitHub runner."""
import importlib.util
import struct
import unittest
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/"tools"/"audit_v133_connection_chain.py"
spec=importlib.util.spec_from_file_location("connection_chain",MODULE)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
def header():
    b=bytearray(56)
    struct.pack_into("<8I",b,0,0xfeedfacf,0x0100000c,0,2,1,24,0,0)
    struct.pack_into("<II",b,32,0x1b,24)
    b[40:56]=bytes.fromhex(audit.UUID)
    return b
class TestConnectionChainContract(unittest.TestCase):
    def test_pins_expected(self):
        audit.verify_pins(audit.PINS.__getitem__)
        self.assertEqual(len(audit.PINS),51)
    def test_opcode_tampering_fails(self):
        pins=dict(audit.PINS);first=next(iter(pins));pins[first]^=1
        with self.assertRaisesRegex(audit.AuditError,"opcode mismatch"):
            audit.verify_pins(pins.__getitem__)
    def test_macho_uuid(self):
        self.assertEqual(audit.macho_uuid(header()),audit.UUID)
    def test_wrong_macho_arch(self):
        b=header(); b[4]=0
        with self.assertRaises(audit.AuditError):audit.macho_uuid(b)
    def test_uuid_load_command_malformed(self):
        b=header();struct.pack_into("<I",b,36,7)
        with self.assertRaises(audit.AuditError):audit.macho_uuid(b)
    def test_peer_session_and_dual_dispatch_pins_never_authorize(self):
        self.assertEqual(audit.PINS[0x1019d255c],0x9102a000)
        self.assertEqual(audit.PINS[0x101d6b2b8],0xf9429000)
        self.assertEqual(audit.PINS[0x1019d6358],0x12800000)
        self.assertEqual(audit.PINS[0x1019d3158],0x12800000)
        self.assertNotEqual(audit.PINS[0x1019d6304],audit.PINS[0x1019d3104])
        self.assertIn(0x101ffeecc,audit.PINS)
        self.assertIn(0x1020249b8,audit.PINS)
        self.assertNotIn("authenticated_sender_verified",audit.PINS)
    def test_original_hash_is_required(self):
        with self.assertRaisesRegex(audit.AuditError,"wrong GTA5 SHA256"):
            audit.audit(header())
    def test_false_authentication_is_not_encoded(self):
        self.assertFalse("authenticated_sender_verified" in audit.PINS)
        self.assertIn(0x101cd6128,audit.PINS)
        self.assertIn(0x101cd6130,audit.PINS)
if __name__=="__main__":unittest.main()
