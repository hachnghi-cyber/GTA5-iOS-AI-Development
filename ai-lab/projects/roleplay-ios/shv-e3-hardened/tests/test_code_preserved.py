import shutil
import tempfile
import unittest
from pathlib import Path
from tools.verify_code_preserved import identity

# Explicitly skip if user has not supplied the original binary.
import os
SOURCE = Path(os.environ.get('RBP_GTA5_PATH', '/mnt/data/rage_breakthrough/work/Payload/GTAV.app/GTA5'))

class MachOSigningDiffTest(unittest.TestCase):
    @unittest.skipUnless(SOURCE.exists(), 'exact binary not mounted')
    def test_signature_only_vs_code_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'GTA5-copy'
            shutil.copyfile(SOURCE, copy)
            original = identity(SOURCE)
            self.assertEqual(original['uuid'], 'EB122C35-96F4-307F-91C3-A2255DD9C685')
            # Touch a byte in the signature payload; code should be identical.
            offset, size = original['signature']
            self.assertGreater(size, 0)
            with copy.open('r+b') as f:
                f.seek(offset+size-1)
                last=f.read(1);self.assertEqual(len(last),1)
                f.seek(offset+size-1);f.write(bytes([last[0]^1]))
            signed = identity(copy)
            self.assertNotEqual(signed['file_sha256'],original['file_sha256'])
            self.assertEqual(signed['uuid'],original['uuid'])
            self.assertEqual(signed['text'],original['text'])
            # Touch actual executable instruction; verification must fail.
            with copy.open('r+b') as f:
                f.seek(original['text']['file_offset'])
                first=f.read(1);f.seek(original['text']['file_offset'])
                f.write(bytes([first[0]^1]))
            modified=identity(copy)
            self.assertNotEqual(modified['text']['sha256'],original['text']['sha256'])

if __name__=='__main__': unittest.main()
