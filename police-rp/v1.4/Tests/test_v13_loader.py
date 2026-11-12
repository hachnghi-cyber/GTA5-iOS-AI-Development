#!/usr/bin/env python3
"""Unit tests of fail-closed native diagnostic loader packaging (no game files in repo)."""
import sys
import struct
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Tools'))
from inject_prp_probe import (ProbeError, inject_macho,parse_macho,dylib_check,sha,
                              make_load_cmd,LOAD_NAME,GTA_UUID,
                              MH_MAGIC_64,MH_EXECUTE,MH_DYLIB,CPU_TYPE_ARM64)

def mock_macho(kind=MH_EXECUTE,platform=2):
    # Minimal synthetic Mach-O for safe parser/patch tests, NOT runnable.
    segment=struct.pack('<II16sQQQQiiII',0x19,72,b'__TEXT'.ljust(16,b'\0'),
                        0x100000000,0x2000,0x1000,0x400,5,5,0,0)
    uid=struct.pack('<II16s',0x1b,24,GTA_UUID)
    build=struct.pack('<6I',0x32,24,platform,0x100000,0x100000,0)
    id_str=b'@executable_path/Frameworks/PoliceRPProbe.dylib\0'
    id_cmd=struct.pack('<6I',0x0d,(24+len(id_str)+7)&~7,24,0,0x10000,0x10000)+id_str.ljust(((24+len(id_str)+7)&~7)-24,b'\0')
    commands=segment+uid+build+(id_cmd if kind==MH_DYLIB else b'')
    hdr=struct.pack('<8I',MH_MAGIC_64,CPU_TYPE_ARM64,0,kind,4 if kind==MH_DYLIB else 3,len(commands),0,0)
    return (hdr+commands).ljust(0x1000,b'\0')+b'\xab'*0x400

class TestDiagnosticLoader(unittest.TestCase):
    def test_patch_exact_version_and_no_other_offsets(self):
        original=mock_macho()
        updated, report=inject_macho(original, require_digest=False)
        old=parse_macho(original,MH_EXECUTE);new=parse_macho(updated,MH_EXECUTE)
        self.assertEqual(new['ncmds'],old['ncmds']+1)
        self.assertEqual(new['sizeofcmds'],old['sizeofcmds']+len(make_load_cmd()))
        self.assertIn(LOAD_NAME,new['load_names'])
        self.assertEqual(original[0x1000:],updated[0x1000:])
        self.assertEqual(original[32:old['end']],updated[32:old['end']])
        self.assertEqual(len(original),len(updated))
        self.assertGreater(report['bytes_changed'],len(make_load_cmd())//2)

    def test_patch_rejects_second_injection(self):
        updated,_=inject_macho(mock_macho(),require_digest=False)
        with self.assertRaisesRegex(ProbeError,'already installed'):
            inject_macho(updated,require_digest=False)

    def test_patch_refuses_wrong_sha(self):
        with self.assertRaisesRegex(ProbeError,'SHA-256'):
            inject_macho(mock_macho(),require_digest=True)

    def test_patch_refuses_nonzero_header_slack(self):
        tampered=bytearray(mock_macho());tampered[153]=7
        with self.assertRaisesRegex(ProbeError,'slack is not zero'):
            inject_macho(bytes(tampered),require_digest=False)

    def test_patch_refuses_wrong_uuid(self):
        tampered=bytearray(mock_macho());tampered[32+72+8]^=1
        with self.assertRaisesRegex(ProbeError,'UUID'):
            inject_macho(bytes(tampered),require_digest=False)

    def test_dylib_validates_ios_not_macos(self):
        self.assertEqual(dylib_check(mock_macho(kind=MH_DYLIB))['platform'],2)
        with self.assertRaisesRegex(ProbeError,'Not an iOS-device dylib'):
            dylib_check(mock_macho(kind=MH_DYLIB,platform=1))

    def test_dylib_rejects_executable_masquerade(self):
        with self.assertRaisesRegex(ProbeError,'requested filetype'):
            dylib_check(mock_macho(kind=MH_EXECUTE))

    def test_real_v12_loader_patch_if_available(self):
        path=Path('/mnt/data/ipa12_inspect/GTA5')
        if not path.exists(): self.skipTest('No user-supplied v12 GTA5 binary in CI')
        original=path.read_bytes()
        updated,report=inject_macho(original,require_digest=True)
        self.assertNotEqual(sha(original),sha(updated))
        self.assertEqual(len(original),len(updated))
        self.assertEqual(original[16384:],updated[16384:])
        self.assertTrue(report['load_cmd_bytes']>24)
        self.assertIn(LOAD_NAME,parse_macho(updated,MH_EXECUTE)['load_names'])

if __name__=='__main__':unittest.main(verbosity=2)
