import hashlib
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_shv_abi import ABIVerificationError
from verify_loader_contract import verify_loader_bytes,LOADER_WORDS,LOADER_STRINGS
from test_verify_shv_abi import fake_dylib

def fixture():
    data=fake_dylib()
    for off,word in LOADER_WORDS.items():
        struct.pack_into('<I',data,off,word)
    data.extend(b'\0'.join(LOADER_STRINGS))
    return data

class LoaderStaticTest(unittest.TestCase):
    def test_synthetic_full(self):
        data=fixture()
        result=verify_loader_bytes(data,expected_hash=hashlib.sha256(data).hexdigest())
        self.assertEqual(result['guarded_opcode_count'],16)
        self.assertFalse(result['device_loaded'])
    def test_mutated_delta_opcode_rejected(self):
        data=fixture()
        data[0x4DB4]^=1
        with self.assertRaisesRegex(ABIVerificationError,'LOADER_OPCODE_MISMATCH_0x4db4'):
            verify_loader_bytes(data,expected_hash=hashlib.sha256(data).hexdigest())
    def test_missing_stock_log_literal(self):
        data=fixture()
        data=data.replace(b'[shv] loaded plugin %s',b'[shv] BROKEN plugin %s')
        with self.assertRaisesRegex(ABIVerificationError,'LOADER_LITERAL_MISSING'):
            verify_loader_bytes(data,expected_hash=hashlib.sha256(data).hexdigest())
    def test_pinned_hash_mismatch_rejected(self):
        with self.assertRaisesRegex(ABIVerificationError,'SHA256_MISMATCH'):
            verify_loader_bytes(fixture())
    def test_invalid_uuid_rejected(self):
        data=fixture()
        data[40]^=1
        with self.assertRaisesRegex(ABIVerificationError,'MACHO_UUID_MISMATCH'):
            verify_loader_bytes(data,expected_hash=hashlib.sha256(data).hexdigest())
