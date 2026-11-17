"""Synthetic branch/BL pins; proprietary GTA binary never used by GitHub CI."""
import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).resolve().parents[1]/'tools'/'audit_v133_event_route.py'
spec=importlib.util.spec_from_file_location('net_event_route',MODULE)
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class TestEventRoute(unittest.TestCase):
    def test_exact_pin_contract(self):
        a.verify_event_pins(a.EVENT_PINS.__getitem__)
        self.assertEqual(len(a.EVENT_PINS),29)
    def test_mutated_event_opcode_fail_closed(self):
        d=dict(a.EVENT_PINS);d[0x1020249b8] ^= 1
        with self.assertRaisesRegex(a.chain.AuditError,'opcode mismatch'):
            a.verify_event_pins(d.__getitem__)
    def test_wrong_branch_target_fails(self):
        with self.assertRaisesRegex(a.chain.AuditError,'not BL'):
            a.decode_bl_target(0x1020249b8,0xd65f03c0)
        self.assertEqual(a.decode_bl_target(0x1020249b8,0x940005d7),0x102026114)
        self.assertEqual(a.decode_bl_target(0x1020249d8,0x977f9ff0),0x10000c998)
        self.assertEqual(a.decode_bl_target(0x1020249e4,0x978047ab),0x100036890)
    def test_order_is_pre_header(self):
        dispatch,parse,game=0x1020249b8,0x1020249e4,0x102024a10
        self.assertLess(dispatch,parse)
        self.assertLess(parse,game)
        self.assertIn(dispatch,a.BL_TARGETS)
        self.assertIn(parse,a.BL_TARGETS)
        self.assertIn(game,a.BL_TARGETS)
    def test_exact_binary_sha_is_required(self):
        with self.assertRaisesRegex(a.chain.AuditError,'SHA256'):
            a.audit(b'fake')

if __name__=='__main__':unittest.main()
