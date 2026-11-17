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
        self.assertEqual(len(audit.PINS),128)
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
    def test_membership_to_connection_to_endpoint_chain_pinned(self):
        self.assertEqual(audit.PINS[0x101804720],0x940739e1)
        self.assertEqual(audit.PINS[0x101804724],0x34000300)
        self.assertEqual(audit.PINS[0x101804740],0x940746e5)
        self.assertEqual(audit.PINS[0x101804760],0x94073a5d)
        self.assertEqual(audit.PINS[0x101804780],0x52800020)
        self.assertIn(0x10180470c,audit.PINS)
        self.assertFalse("authenticated_sender_verified" in audit.PINS)

    def test_pre_dispatch_guards_are_exact_opcode_pins(self):
        self.assertEqual(audit.PINS[0x102024944],0x7100101f)
        self.assertEqual(audit.PINS[0x102024948],0x54000661)
        self.assertEqual(audit.PINS[0x102024974],0x54000080)
        self.assertEqual(audit.PINS[0x102024984],0xd000a80a)
        self.assertEqual(audit.PINS[0x1020249a8],0xa9012be9)
        self.assertNotIn("authenticated_sender_verified",audit.PINS)

    def test_selected_player_and_session_peer_map_opcodes(self):
        self.assertEqual(audit.PINS[0x1018d92e8],0xf9405008)
        self.assertEqual(audit.PINS[0x101d64b9c],0xf940e800)
        self.assertEqual(audit.PINS[0x1019dc878],0xb94a3128)
        self.assertEqual(audit.PINS[0x1019dc888],0xf840852a)
        self.assertEqual(audit.PINS[0x1019dc8b0],0x92800000)

    def test_onconnection_same_native_callback_pins(self):
        self.assertEqual(audit.PINS[0x1017df9b8],0x97fca16b)
        self.assertEqual(audit.PINS[0x1017df9c4],0x9420d070)
        self.assertEqual(audit.PINS[0x1017dfa30],0xf9401276)
        self.assertEqual(audit.PINS[0x1017dfa3c],0x9420ca75)
        self.assertEqual(audit.PINS[0x1017dfa40],0xaa0003e1)
        self.assertEqual(audit.PINS[0x1017dfa44],0xaa1603e0)
        self.assertEqual(audit.PINS[0x1017dfa48],0x9407da23)
        self.assertEqual(audit.PINS[0x1017dfa50],0x540033c0)

    def test_original_hash_is_required(self):
        with self.assertRaisesRegex(audit.AuditError,"wrong GTA5 SHA256"):
            audit.audit(header())
    def test_false_authentication_is_not_encoded(self):
        self.assertFalse("authenticated_sender_verified" in audit.PINS)
        self.assertIn(0x101cd6128,audit.PINS)
        self.assertIn(0x101cd6130,audit.PINS)
if __name__=="__main__":unittest.main()
