#!/usr/bin/env python3
"""Read-only sanity tests for confirmed ARM64 call chain; exact binary only."""
import argparse
import hashlib
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_v12_police_carrier import verify, require_branch, branch_target
class TraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(cls.ipa) as z:
            cls.binary=z.read('Payload/GTAV.app/GTA5')
    def test_v12_fingerprint_and_registration(self):
        result=verify(self.binary)
        self.assertEqual(result['job_message']['bytes'], 244)
        self.assertEqual(result['job_message']['magic'], 'MPJ2')
        self.assertFalse(result['hook_installed'])
    def test_tail_branch_is_not_BL(self):
        result=require_branch(self.binary,0x100039e34,0x1000e01a0,'B')
        self.assertEqual(result['kind'],'B')
        with self.assertRaises(ValueError):
            require_branch(self.binary,0x100039e34,0x1000e01a0,'BL')
    def test_modified_binary_rejected(self):
        broken=bytearray(self.binary)
        broken[0x39e34]^=1
        with self.assertRaises(ValueError): verify(broken)
    def test_invalid_signature(self):
        with self.assertRaises(ValueError):verify(bytes(1000))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ipa');args=p.parse_args()
    TraceTests.ipa=args.ipa
    unittest.main(argv=['test_v10_trace.py'],verbosity=2)
