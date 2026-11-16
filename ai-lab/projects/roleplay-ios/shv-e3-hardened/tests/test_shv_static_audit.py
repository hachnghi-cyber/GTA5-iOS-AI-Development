"""Exact-SHV static ABI audit negative and positive cases.
Does not run a ScriptHook function or mock device success.
"""
import os
import struct
import unittest
import zipfile
from pathlib import Path
from tools.audit_shv_native_bridge import static_audit

class ScriptHookStaticAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ipa=os.environ.get('RBP_IPA_PATH')
        if not ipa or not Path(ipa).exists():
            raise unittest.SkipTest('RBP_IPA_PATH is not a mounted original IPA')
        with zipfile.ZipFile(ipa) as z:
            cls.shv=z.read('Payload/GTAV.app/Frameworks/ScriptHookV.dylib')

    def test_exact_symbol_offsets_and_hash_literals(self):
        r=static_audit(self.shv)
        self.assertTrue(r['uuid_matches_baseline'])
        self.assertTrue(r['api_symbol_locations_match'])
        for v in r['hud_hash_literals'].values():
            self.assertEqual(v['little_endian_occurrences'],1)
            self.assertTrue(v['name_in_binary'])
        self.assertFalse(r['native_action_executed'])

    def test_changed_symbol_table_address_rejected(self):
        data=bytearray(self.shv)
        # Mutate the source symbol _scriptRegister's n_value entry.
        cmds=struct.unpack_from('<I',data,16)[0]
        pos=32
        for _ in range(cmds):
            cmd,size=struct.unpack_from('<II',data,pos)
            if cmd==2:
                symoff,nsyms,stroff,strsize=struct.unpack_from('<IIII',data,pos+8)
                break
            pos+=size
        else:raise AssertionError('missing symbol table')
        for i in range(nsyms):
            row=symoff+i*16
            ix=struct.unpack_from('<I',data,row)[0]
            if not ix or ix>=strsize:continue
            start=stroff+ix
            end=data.find(b'\0',start,stroff+strsize)
            if data[start:end]==b'_scriptRegister':
                struct.pack_into('<Q',data,row+8,0x123456)
                break
        else:raise AssertionError('missing symbol')
        self.assertFalse(static_audit(bytes(data))['api_symbol_locations_match'])

    def test_uuid_modification_fails_closed(self):
        data=bytearray(self.shv)
        n=struct.unpack_from('<I',data,16)[0];pos=32
        for _ in range(n):
            cmd,size=struct.unpack_from('<II',data,pos)
            if cmd==0x1b:
                data[pos+8]^=0x20
                break
            pos+=size
        else:raise AssertionError('missing LC_UUID')
        self.assertFalse(static_audit(bytes(data))['uuid_matches_baseline'])
