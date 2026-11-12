"""Offline regression tests for iOS Files-readable loader marker and IPA guard."""
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Tools'))
from check_prp_probe_log import parse_probe_log
from inject_prp_probe import ProbeError,dylib_check,parse_macho,MH_DYLIB,LOAD_NAME
from test_v13_loader import mock_macho

class TestProbeReport(unittest.TestCase):
    def test_expected_success(self):
        s='[PRP_DIAG_V14] dylib_loaded=1 gta5_uuid_verified=1 hooks=0 network_events=0 police_gameplay=0'
        r=parse_probe_log(s)
        self.assertEqual(r['status'],'LOADER_VERIFIED')
        self.assertTrue(r['verified'])

    def test_uuid_mismatch(self):
        s='[PRP_DIAG_V14] dylib_loaded=1 gta5_uuid_verified=0 hooks=0 network_events=0 police_gameplay=0'
        self.assertFalse(parse_probe_log(s)['verified'])

    def test_no_marker_is_not_success(self):
        self.assertEqual(parse_probe_log('') ['status'],'MISSING_MARKER')
        self.assertFalse(parse_probe_log('hello world')['verified'])

    def test_wrong_gameplay_state_rejected(self):
        s='[PRP_DIAG_V14] dylib_loaded=1 gta5_uuid_verified=1 hooks=0 network_events=1 police_gameplay=0'
        self.assertFalse(parse_probe_log(s)['verified'])

    def test_old_v13_marker_not_accepted(self):
        self.assertFalse(parse_probe_log('[PRP_DIAG_V13] dylib loaded')['verified'])

    def test_wrong_install_name_rejected(self):
        original=mock_macho(kind=MH_DYLIB)
        self.assertEqual(dylib_check(original)['dylib_id'],LOAD_NAME)
        modified=original.replace(LOAD_NAME.encode(),b'@executable_path/Frameworks/PoliceRPWrong.dylib')
        with self.assertRaisesRegex(ProbeError,'install_name'):
            dylib_check(modified)

    def test_ios_mock_build_version(self):
        m=mock_macho(kind=MH_DYLIB)
        self.assertEqual(parse_macho(m,MH_DYLIB)['platform'],2)

    def test_packaging_preserves_other_members_and_dylib_mode(self):
        import tempfile,zipfile
        from unittest.mock import patch
        from inject_prp_probe import GTA_PATH,DYLIB_PATH,sha,create_diagnostic_ipa
        exe=mock_macho()
        dylib=mock_macho(kind=MH_DYLIB)
        with tempfile.TemporaryDirectory() as tmp:
            d=pathlib.Path(tmp)
            src=d/'original.ipa'
            lib=d/'probe.dylib'
            out=d/'modified.ipa'
            lib.write_bytes(dylib)
            with zipfile.ZipFile(src,'w') as z:
                z.writestr(GTA_PATH,exe)
                z.writestr('Payload/GTAV.app/test.txt',b'unaltered-data')
            with patch('inject_prp_probe.GTA_SHA256',sha(exe)):
                report=create_diagnostic_ipa(src,lib,out)
            self.assertFalse(report['gameplay_hook_installed'])
            self.assertFalse(report['real_police_network_connected'])
            with zipfile.ZipFile(out) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(z.read('Payload/GTAV.app/test.txt'),b'unaltered-data')
                self.assertEqual(z.read(DYLIB_PATH),dylib)
                self.assertEqual((z.getinfo(DYLIB_PATH).external_attr>>16)&0o777,0o755)

    def test_bundle_is_file_shared(self):
        import plistlib,zipfile
        user_ipa=pathlib.Path('/mnt/data/GTAV-v12(1).ipa')
        if not user_ipa.exists(): self.skipTest('Real IPA not available on CI')
        with zipfile.ZipFile(user_ipa) as z:
            p=plistlib.loads(z.read('Payload/GTAV.app/Info.plist'))
        self.assertTrue(p.get('UIFileSharingEnabled'))
        self.assertTrue(p.get('LSSupportsOpeningDocumentsInPlace'))

if __name__ == '__main__': unittest.main()
