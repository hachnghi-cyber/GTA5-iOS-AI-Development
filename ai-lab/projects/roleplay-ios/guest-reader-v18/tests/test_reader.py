"""Pure RPR1 fuzz/regression tests for GTA5Port RP v1.8.
No iPhone required; produces deterministic 764-byte fixtures and tests C decoder.
"""
import ctypes
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SIZE=764

def frame(peers=(),generation=1,epoch=0x20261118):
    if len(peers)>31:raise ValueError("too many")
    b=bytearray(SIZE)
    struct.pack_into('<4sBBBBII',b,0,b'RPR1',1,len(peers),0,0,generation,epoch)
    for i,p in enumerate(peers):
        struct.pack_into('<Qffff',b,16+i*24,*p)
    h=2166136261
    for x in b[:-4]:h=((h^x)*16777619)&0xffffffff
    struct.pack_into('<I',b,760,h)
    return bytes(b)

class Summary(ctypes.Structure):
    _fields_=[('generation',ctypes.c_uint32),('epoch',ctypes.c_uint32),
              ('count',ctypes.c_uint)]

class MailboxV18Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        lib=Path(cls.tmp.name)/'rpr18.so'
        result=subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2',
                               '-Wall','-Wextra','-Werror','-fPIC','-shared','-DRP18_TEST',
                               str(ROOT/'RPRemoteMailboxReaderV18.c'),'-o',str(lib)],
                              capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.dll=ctypes.CDLL(str(lib))
        cls.dll.rp18_decode.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(Summary)]
        cls.dll.rp18_decode.restype=ctypes.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def decode(self,raw):
        buf=ctypes.create_string_buffer(raw)
        summary=Summary()
        rc=self.dll.rp18_decode(buf,len(raw),ctypes.byref(summary))
        return rc,summary

    def test_zero_peers_valid(self):
        rc,s=self.decode(frame([],91))
        self.assertEqual(rc,0);self.assertEqual((s.generation,s.count),(91,0))

    def test_one_remote_pose_valid(self):
        rc,s=self.decode(frame([(2,12.25,-14.5,23.5,190.)],4))
        self.assertEqual(rc,0);self.assertEqual((s.count,s.generation),(1,4))

    def test_31_remote_peers_and_unique_ids(self):
        people=[(i+2,float(i),float(-i),0.,90.) for i in range(31)]
        rc,s=self.decode(frame(people,255))
        self.assertEqual(rc,0);self.assertEqual(s.count,31)

    def test_reject_bad_magic_version_count(self):
        for offset,value in [(0,0),(4,2),(5,32),(6,1),(7,1)]:
            raw=bytearray(frame([]));raw[offset]=value
            rc,_=self.decode(raw);self.assertNotEqual(rc,0)

    def test_reject_crc_and_extra_bytes(self):
        raw=bytearray(frame([(2,1.,2.,3.,90.)]))
        raw[40]^=1
        self.assertNotEqual(self.decode(raw)[0],0)
        self.assertNotEqual(self.decode(frame([])+b'x')[0],0)
        self.assertNotEqual(self.decode(frame([])[:-1])[0],0)

    def test_reject_zero_epoch_or_generation(self):
        for g,e in [(0,1),(1,0)]:
            self.assertNotEqual(self.decode(frame([],g,e))[0],0)

    def test_reject_duplicate_and_invalid_ids(self):
        self.assertNotEqual(self.decode(frame([(5,1.,2.,3.,0.),(5,2.,3.,4.,0.)]))[0],0)
        self.assertNotEqual(self.decode(frame([(0,1.,2.,3.,0.)]))[0],0)
        self.assertNotEqual(self.decode(frame([((1<<48),1.,2.,3.,0.)]))[0],0)

    def test_reject_nan_inf_out_of_range(self):
        cases=[(1.,2.,float('nan'),0.),
               (1.,float('inf'),3.,0.),
               (100001.,0.,0.,0.),
               (1.,2.,20001.,0.),
               (1.,2.,3.,360001.)]
        for values in cases:
            rc,_=self.decode(frame([(7,*values)]))
            self.assertNotEqual(rc,0,values)

if __name__=='__main__':unittest.main()
