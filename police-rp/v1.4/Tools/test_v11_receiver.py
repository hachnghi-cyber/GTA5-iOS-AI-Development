import hashlib
import os
import pathlib
import struct
import sys
import unittest
from unittest import mock

HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import verify_v12_job_receiver as rx
from inspect_v12_calls import sections

# Portable unit fixture: only tests signature-checking logic, NOT the GTA5 binary.
VM=0x1000EA000
SIZE=0x1000

def fixture():
    b=bytearray(SIZE)
    for pc,(word,_) in rx.STEPS.items():
        struct.pack_into('<I',b,pc-VM,word)
    return bytes(b)

class TestReceiver(unittest.TestCase):
    def test_synthetic_signature(self):
        blob=fixture()
        with mock.patch.object(rx,'EXPECTED_GTA5',hashlib.sha256(blob).hexdigest()), \
             mock.patch.object(rx,'sections',lambda b:(VM,len(b),0)):
            r=rx.inspect(blob)
        self.assertEqual(r['receiver_payload_bytes'],244)
        self.assertEqual(r['required_magic'],'MPJ2')
        self.assertFalse(r['accepts_PRC1_without_changes'])
        self.assertFalse(r['trusted_sender_confirmed'])
        self.assertEqual(len(r['verified_arm64_instructions']),len(rx.STEPS))
    def test_synthetic_wrong_hash(self):
        blob=bytearray(fixture())
        h=hashlib.sha256(blob).hexdigest()
        blob[0x168]^=1
        with mock.patch.object(rx,'EXPECTED_GTA5',h), \
             mock.patch.object(rx,'sections',lambda b:(VM,len(b),0)):
            with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):rx.inspect(blob)
    def test_synthetic_mutated_instruction(self):
        blob=bytearray(fixture())
        blob[0x168]^=1
        with mock.patch.object(rx,'EXPECTED_GTA5',hashlib.sha256(blob).hexdigest()), \
             mock.patch.object(rx,'sections',lambda b:(VM,len(b),0)):
            with self.assertRaisesRegex(ValueError,'expected'):rx.inspect(blob)
    def test_real_binary_when_supplied(self):
        path=pathlib.Path(os.environ.get('PRP_GTA5_BIN','/mnt/data/ipa12_inspect/GTA5'))
        if not path.exists():self.skipTest('GTA5 sample not supplied (CI has no copyrighted binary)')
        self.assertEqual(rx.inspect(path.read_bytes())['required_magic'],'MPJ2')

if __name__=='__main__': unittest.main(verbosity=2)
