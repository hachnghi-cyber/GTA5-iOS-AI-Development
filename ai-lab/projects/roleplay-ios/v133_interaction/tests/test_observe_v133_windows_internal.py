"""Synthetic tests only; no WinUSB/LLDB device is touched."""
import importlib.util
import json
import struct
import unittest
from pathlib import Path
module=Path(__file__).resolve().parents[1]/"tools"/"observe_v133_windows_usb.py"
spec=importlib.util.spec_from_file_location("winusb",module)
winusb=importlib.util.module_from_spec(spec);spec.loader.exec_module(winusb)

class FakeRemote:
    def __init__(self,regs,mem):
        self.regs=regs;self.mem=mem;self.requests=[]
    def read_register(self,n):
        return self.regs[n]
    def memory(self,addr,size):
        self.requests.append((addr,size))
        value=self.mem[addr]
        return value.to_bytes(size,"little") if isinstance(value,int) else value

class InternalUSBTests(unittest.TestCase):
    def meta(self):
        return json.loads(winusb.BASELINE.read_text(encoding="utf-8"))
    def test_internal_sites_are_fingerprinted(self):
        data=self.meta()
        self.assertEqual(winusb.internal_site_va(data,"on_net_event_pre_dispatch"),
                         0x1020249a8)
        self.assertEqual(winusb.internal_site_va(data,"on_connection_peer_verify"),
                         0x1017dfa48)
        self.assertIn("on_net_event_pre_dispatch",winusb.OBSERVABLE_SITES)
        self.assertIn("on_connection_peer_verify",winusb.OBSERVABLE_SITES)
    def test_readonly_pre_dispatch_candidate(self):
        mem={0x1000+0x128:0x2000,0x5000+0x3c:77,
             0x2000+0x18:76,0x2000+0x38:0x3000,
             0x3000+0x18:77,0x3000+0x38:0}
        remote=FakeRemote({19:0x1000,20:0x5000,9:0x3000,10:0x4000},mem)
        r=winusb.read_internal_candidate(remote,0x100000000,self.meta(),
                                         "on_net_event_pre_dispatch")
        self.assertEqual(r["status"],"connection_candidate_only")
        self.assertTrue(r["selected_sender_in_player_list"])
        self.assertFalse(r["authenticated_rp_sender_verified"])
        self.assertNotIn("peer_id",r)
    def test_same_event_player_to_session(self):
        base=0x100000000
        static=self.meta()["peer_info_static"]
        player,session,manager,event,getter=0x1000,0x7000,0x4000,0x5000,int(static["getter_va"],16)
        mem={player:0x2000,player+0x18:77,0x2000+0x38:getter,
             player+0xa0:0x3000,0x3000+0x1f0:222,
             manager+0x20:session,event+0x40:7,event+0x3c:77,
             session+0xba30:2,session+0xb930:0x8000,session+0xb938:0x9000,
             0x8000:33,0x8000+0x1d8:111,0x9000:77,0x9000+0x1d8:222}
        for va,op in (("getter_va","getter_instruction"),("getter_next_va","getter_next_instruction"),("peer_getter_va","peer_getter_instruction")):
            mem[int(static[va],16)]=struct.pack("<I",int(static[op],16))
        remote=FakeRemote({19:manager,21:event,22:session,24:player,1:222},mem)
        result=winusb.read_internal_candidate(remote,base,self.meta(),"on_connection_peer_verify")
        self.assertEqual(result["status"],"session_connection_peer_candidate_only")
        self.assertTrue(result["peer_map_consistent"])
        self.assertFalse(result["authenticated_rage_sender_verified"])
        self.assertNotIn("peer_id",result)
        remote.regs[1]=999
        result=winusb.read_internal_candidate(remote,base,self.meta(),"on_connection_peer_verify")
        self.assertEqual(result["status"],"same_callback_peer_register_mismatch")
    def test_bad_session_or_type_fails_without_peer_scan(self):
        meta=self.meta()
        remote=FakeRemote({19:0x4000,21:0x5000,22:0x7000,24:0x1000,1:222},
                           {0x4000+0x20:0x8000,0x5000+0x40:7})
        r=winusb.read_internal_candidate(remote,0x100000000,meta,
                                         "on_connection_peer_verify")
        self.assertEqual(r["status"],"session_or_event_frame_mismatch")
        self.assertFalse(r["authenticated_rp_sender_verified"])
    def test_bad_or_unknown_site_is_noop(self):
        r=winusb.read_internal_candidate(FakeRemote({},{}),0,{},"not_a_site")
        self.assertEqual(r["status"],"unsupported_site")
        self.assertFalse(r["authenticated_rp_sender_verified"])
if __name__=="__main__":unittest.main()
