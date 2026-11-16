import hashlib
import struct
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_shv_abi import audit, uuid_from_macho, ABIVerificationError, EXPECTED_WORDS, EXPECTED_UUID

def fake_dylib():
    data = bytearray(max(EXPECTED_WORDS) + 4)
    struct.pack_into('<8I', data, 0, 0xfeedfacf, 0x0100000c, 0, 6, 1, 24, 0, 0)
    struct.pack_into('<II', data, 32, 0x1b, 24)
    data[40:56] = bytes.fromhex(EXPECTED_UUID)
    for off, word in EXPECTED_WORDS.items():
        struct.pack_into('<I', data, off, word)
    return data

class TestExactABI(unittest.TestCase):
    def test_synthetic_contract(self):
        d = fake_dylib()
        r = audit(bytes(d), expected_hash=hashlib.sha256(d).hexdigest())
        self.assertEqual(r['inspected_arm64_words'], 9)
        self.assertFalse(r['proves_device_callback'])
    def test_pinned_sha_rejects_fixture(self):
        with self.assertRaisesRegex(ABIVerificationError, 'SHA256_MISMATCH'):
            audit(bytes(fake_dylib()))
    def test_instruction_mutation(self):
        d = fake_dylib()
        d[0x78f34] ^= 1
        with self.assertRaisesRegex(ABIVerificationError, 'ARM64_WORD_MISMATCH_0x78f34'):
            audit(bytes(d), expected_hash=hashlib.sha256(d).hexdigest())
    def test_wrong_uuid(self):
        d = fake_dylib()
        d[40] ^= 1
        with self.assertRaisesRegex(ABIVerificationError, 'MACHO_UUID_MISMATCH'):
            audit(bytes(d), expected_hash=hashlib.sha256(d).hexdigest())
    def test_malformed_macho(self):
        d = fake_dylib()
        d[0] ^= 1
        with self.assertRaisesRegex(ABIVerificationError, 'NOT_ARM64_MACHO_DYLIB'):
            audit(bytes(d), expected_hash=hashlib.sha256(d).hexdigest())
    def test_load_cmd_size(self):
        d = fake_dylib()
        struct.pack_into('<I', d, 36, 65536)
        with self.assertRaisesRegex(ABIVerificationError, 'BAD_LOAD_COMMAND'):
            uuid_from_macho(bytes(d))

if __name__ == '__main__':
    unittest.main()
