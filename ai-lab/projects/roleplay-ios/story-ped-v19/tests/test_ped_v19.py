"""Unit tests for strictly opt-in one-PED Story-only prototype.
Only pure validation/gating functions; NO RAGE engine is executed.
"""
import ctypes
import math
from pathlib import Path
import os
import struct
import subprocess
import tempfile
import unittest

DIR=Path(__file__).resolve().parents[1]
SRC18=DIR.parent/"guest-reader-v18"/"RPRemoteMailboxReaderV18.c"
SRC19=DIR/"RPStoryPedProbeV19.c"

class Pose(ctypes.Structure):
    _fields_=[("x",ctypes.c_float),("y",ctypes.c_float),
              ("z",ctypes.c_float),("heading",ctypes.c_float),
              ("sequence",ctypes.c_uint32)]
class Remote(ctypes.Structure):
    _fields_=[("id",ctypes.c_uint64),("pose",Pose),
              ("generation",ctypes.c_uint32),("epoch",ctypes.c_uint32)]

def fnv(data):
    h=2166136261
    for c in data:h=((h^c)*16777619)&0xffffffff
    return h

def local_frame(seq=10,xyz=(1.,2.,3.),heading=90.):
    b=bytearray(48)
    b[:4]=b"RPF8";b[4]=8;b[6]=48
    struct.pack_into("<IIIffff",b,8,seq,2,4,*xyz,heading)
    struct.pack_into("<I",b,40,0x08112026)
    struct.pack_into("<I",b,44,fnv(b[:44]))
    return bytes(b)

def mailbox(peers=(),generation=10,epoch=0x20261118):
    b=bytearray(764)
    b[:4]=b"RPR1";b[4]=1;b[5]=len(peers)
    struct.pack_into("<II",b,8,generation,epoch)
    for i,peer in enumerate(peers):struct.pack_into("<Qffff",b,16+24*i,*peer)
    struct.pack_into("<I",b,760,fnv(b[:760]))
    return bytes(b)

class PedV19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        so=Path(cls.tmp.name)/"rp19.so"
        cmd=[os.environ.get("CC","cc"),"-std=c11","-O2","-Wall","-Wextra","-Werror",
             "-fPIC","-shared","-DRP18_TEST","-DRP19_TEST",
             str(SRC18),str(SRC19),"-o",str(so)]
        result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+"\n"+result.stderr)
        lib=cls.lib=ctypes.CDLL(str(so))
        lib.rp19_local_decode.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(Pose)]
        lib.rp19_local_decode.restype=ctypes.c_int
        lib.rp19_remote_decode.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(Remote)]
        lib.rp19_remote_decode.restype=ctypes.c_int
        lib.rp19_gate.argtypes=[ctypes.c_int]*6
        lib.rp19_gate.restype=ctypes.c_int
        lib.rp19_test_model.restype=ctypes.c_uint32
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def local(self,blob):
        p=Pose();raw=ctypes.create_string_buffer(bytes(blob))
        n=self.lib.rp19_local_decode(raw,len(blob),ctypes.byref(p))
        return n,p
    def remote(self,blob):
        p=Remote();raw=ctypes.create_string_buffer(bytes(blob))
        n=self.lib.rp19_remote_decode(raw,len(blob),ctypes.byref(p))
        return n,p
    def test_local_valid(self):
        ok,p=self.local(local_frame(81,(120.,-33.,5.),45.))
        self.assertEqual(ok,1)
        self.assertEqual(p.sequence,81)
        self.assertAlmostEqual(p.y,-33.)
    def test_local_torn_or_corrupt_rejected(self):
        blob=bytearray(local_frame());blob[23]^=0x8f
        self.assertEqual(self.local(blob)[0],0)
        self.assertEqual(self.local(local_frame()[:-1])[0],0)
        self.assertEqual(self.local(local_frame()+b"x")[0],0)
    def test_local_bad_model_and_bounds_rejected(self):
        for xyz in ((float("nan"),0.,0.),(100001.,0.,0.),
                    (0.,0.,20001.),(float("inf"),1.,2.)):
            self.assertEqual(self.local(local_frame(xyz=xyz))[0],0)
    def test_one_peer_accepted(self):
        ok,p=self.remote(mailbox([(0x1234,1.25,-2.5,13.,270.)],5))
        self.assertEqual(ok,1)
        self.assertEqual(p.id,0x1234)
        self.assertEqual(p.generation,5)
        self.assertAlmostEqual(p.pose.x,1.25)
    def test_no_remote_and_multiple_peers_fail_closed(self):
        self.assertEqual(self.remote(mailbox([]))[0],0)
        self.assertEqual(self.remote(mailbox([(2,1.,2.,3.,0.),(3,1.,2.,3.,0.)]))[0],0)
    def test_bad_remote_checksum_and_nonfinite(self):
        blob=bytearray(mailbox([(2,1.,2.,3.,10.)]));blob[33]^=8
        self.assertEqual(self.remote(blob)[0],0)
        self.assertEqual(self.remote(mailbox([(2,float("nan"),2.,3.,10.)]))[0],0)
    def test_model_hash_matches_independent_joaat(self):
        h=0
        for v in b"a_m_m_business_01":
            h=(h+v)&0xffffffff
            h=(h+(h<<10))&0xffffffff;h^=h>>6
        h=(h+(h<<3))&0xffffffff;h^=h>>11
        h=(h+(h<<15))&0xffffffff
        self.assertEqual(self.lib.rp19_test_model(),h)
        self.assertNotEqual(h,0)
    def test_all_six_gates_are_mandatory(self):
        self.assertEqual(self.lib.rp19_gate(1,1,1,1,1,1),1)
        for i in range(6):
            gate=[1]*6;gate[i]=0
            self.assertEqual(self.lib.rp19_gate(*gate),0,gate)
    def test_gate_invalid_input_fails_closed(self):
        self.assertEqual(self.lib.rp19_gate(1,1,2,1,1,1),0)
        self.assertEqual(self.lib.rp19_gate(1,1,1,1,1,-1),0)

if __name__=="__main__":unittest.main()
