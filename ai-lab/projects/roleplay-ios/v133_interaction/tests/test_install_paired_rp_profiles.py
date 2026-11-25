"""Offline checks for handing distinct account profiles to two iOS app containers."""
import ipaddress
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_paired_rp_profiles import GUEST_APP, PROFILE, ProfileWrite, guest_documents, install_pair, read_profiles
from prepare_private_rp import prepare


class MemoryAFC:
    def __init__(self, previous=None):
        self.target = '/Documents/' + PROFILE
        self.files = {} if previous is None else {self.target: previous}
        self.fault = None
        self.renames = 0

    async def exists(self, name):
        return name in self.files

    async def get_file_contents(self, name):
        if self.fault == 'staging' and name.endswith('.tmp'):
            return b'truncated'
        return self.files[name]

    async def set_file_contents(self, name, data):
        self.files[name] = data

    async def rename(self, source, target):
        self.files[target] = self.files.pop(source)
        self.renames += 1
        if self.fault == 'after_rename':
            self.fault = None
            raise OSError('acknowledgement lost')

    async def rm_single(self, name):
        del self.files[name]

    async def listdir(self, folder):
        return [k[len(folder) + 1:] for k in self.files if k.startswith(folder + '/')]


class InstallPairTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.kit = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.gta, self.lc = MemoryAFC(b'old-officer'), MemoryAFC()
        self.pair = (ProfileWrite(self.gta, self.gta.target, 'officer', b'new-officer'),
                     ProfileWrite(self.lc, self.lc.target, 'citizen', b'new-citizen'))

    async def test_second_stage_failure_leaves_old_pair(self):
        self.lc.fault = 'staging'
        with self.assertRaisesRegex(IOError, 'staging readback'):
            await install_pair(self.pair, self.kit)
        self.assertEqual(self.gta.files, {self.gta.target: b'old-officer'})
        self.assertEqual(self.lc.files, {})
        self.assertEqual(self.gta.renames, 0)

    async def test_second_rename_ack_lost_rolls_back_retry_is_idempotent(self):
        self.lc.fault = 'after_rename'
        with self.assertRaisesRegex(IOError, 'acknowledgement lost'):
            await install_pair(self.pair, self.kit)
        self.assertEqual(self.gta.files, {self.gta.target: b'old-officer'})
        self.assertEqual(self.lc.files, {})
        await install_pair(self.pair, self.kit)
        before = self.gta.renames, self.lc.renames
        await install_pair(self.pair, self.kit)
        self.assertEqual(before, (self.gta.renames, self.lc.renames))
        self.assertEqual(self.gta.files, {self.gta.target: b'new-officer'})
        self.assertEqual(self.lc.files, {self.lc.target: b'new-citizen'})
        self.assertTrue(all(p.read_bytes() == b'old-officer' for p in self.kit.iterdir()))

    async def test_ambiguous_livecontainer_does_not_select_a_guest(self):
        self.lc.files[GUEST_APP + '/Info.plist'] = plistlib.dumps({'CFBundleIdentifier': 'com.macport.gtav'})
        self.lc.files[GUEST_APP + '/LCAppInfo.plist'] = plistlib.dumps({'LCContainers': [{}, {}]})
        with self.assertRaisesRegex(ValueError, 'unique'):
            await guest_documents(self.lc)


class KitTests(unittest.TestCase):
    def setUp(self):
        self.kit = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'kit'
        prepare(self.kit, ipaddress.ip_address('127.0.0.1'), 30133, panel=True, login_port=30134)

    def test_generated_pair_and_swapped_identity(self):
        officer, citizen = map(json.loads, read_profiles(self.kit))
        self.assertEqual((officer['rp_id'], citizen['rp_id']), ('11', '22'))
        citizen.update({k: officer[k] for k in ('identity', 'passphrase')})
        (self.kit / 'citizen-iPhone-PRIVATE.json').write_text(json.dumps(citizen))
        with self.assertRaisesRegex(ValueError, 'registry'):
            read_profiles(self.kit)

    def test_expired_pair_is_rejected_before_device_access(self):
        path = self.kit / 'officer-iPhone-PRIVATE.json'
        profile = json.loads(path.read_bytes())
        profile['expires'] = 0
        path.write_text(json.dumps(profile))
        with self.assertRaisesRegex(ValueError, 'expired'):
            read_profiles(self.kit)


if __name__ == '__main__':
    unittest.main()
