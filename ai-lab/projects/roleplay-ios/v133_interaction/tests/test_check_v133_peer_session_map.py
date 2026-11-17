"""Synthetic memory snapshots only; no actual snSession pointer supplied."""
import importlib.util
import unittest
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"tools"/"check_v133_peer_session_map.py"
spec=importlib.util.spec_from_file_location("map_check",path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PeerMappingTests(unittest.TestCase):
    def fixture(self):
        player,session,getter=0x1000,0x7000,0x5000
        ptr_a,ptr_b=0x8000,0x9000
        mem={player+0x18:77,player:0x2000,0x2000+0x38:getter,
             player+0xa0:0x3000,0x3000+0x1f0:222,
             session+0xba30:2,
             session+0xb930:ptr_a,session+0xb938:ptr_b,
             ptr_a:33,ptr_a+0x1d8:111,ptr_b:77,ptr_b+0x1d8:222}
        return mem,(player,session,77,getter)
    def probe(self,mem,params):
        read=lambda addr:mem[addr]
        return mod.check_peer_session_map(read,read,*params)
    def test_unique_consistent_is_candidate_only(self):
        mem,params=self.fixture()
        r=self.probe(mem,params)
        self.assertEqual(r["status"],"session_connection_peer_candidate_only")
        self.assertTrue(r["peer_map_consistent"])
        self.assertEqual(r["remote_entries_seen"],2)
        for flag in ("authenticated_rage_sender_verified",
                     "session_membership_verified","session_generation_verified"):
            self.assertFalse(r[flag])
        for secret in ("peer_id","connection_id","netplayer","session"):
            self.assertNotIn(secret,r)
    def test_wrong_connection_or_vtable(self):
        mem,args=self.fixture()
        self.assertEqual(self.probe(mem,(args[0],args[1],44,args[3]))["status"],
                         "netplayer_connection_mismatch")
        mem[0x2000+0x38]=0x1234
        self.assertEqual(self.probe(mem,args)["status"],
                         "unexpected_gamer_info_vtable")
    def test_peer_mapping_mismatch_and_alias(self):
        mem,args=self.fixture()
        mem[0x9000+0x1d8]=333
        self.assertEqual(self.probe(mem,args)["status"],
                         "connection_to_peer_mismatch")
        mem,args=self.fixture();mem[0x8000+0x1d8]=222
        self.assertEqual(self.probe(mem,args)["status"],
                         "peer_alias_different_connection")
    def test_duplicate_and_missing_cxn(self):
        mem,args=self.fixture()
        mem[0x8000]=77;mem[0x8000+0x1d8]=222
        self.assertEqual(self.probe(mem,args)["status"],
                         "no_unique_session_connection")
        mem,args=self.fixture();mem[0x9000]=22
        # Same peer ID moved to a different connection; reject alias explicitly.
        self.assertEqual(self.probe(mem,args)["status"],
                         "peer_alias_different_connection")
    def test_session_count_and_invalid_peer(self):
        mem,args=self.fixture()
        for count in (0,33,999,0xffffffff):
            mem[args[1]+0xba30]=count
            self.assertEqual(self.probe(mem,args)["status"],
                             "session_peer_count_out_of_bounds")
        mem,args=self.fixture();mem[0x9000+0x1d8]=0
        self.assertEqual(self.probe(mem,args)["status"],"invalid_session_entry")
        mem,args=self.fixture();mem[0x3000+0x1f0]=mod.U64MAX
        self.assertEqual(self.probe(mem,args)["status"],"invalid_netplayer_peer")
    def test_invalid_input_and_missing_memory(self):
        mem,args=self.fixture()
        for bad in (0,-1,0x80000000,0xffffffff):
            self.assertEqual(self.probe(mem,(args[0],args[1],bad,args[3]))["status"],
                             "invalid_input")
        self.assertEqual(self.probe(mem,(0,args[1],77,args[3]))["status"],
                         "invalid_input")
        del mem[0x9000+0x1d8]
        self.assertEqual(self.probe(mem,args)["status"],"read_failed")
    def test_no_false_persistent_ownership(self):
        mem,args=self.fixture()
        r=self.probe(mem,args)
        self.assertTrue(r["peer_map_consistent"])
        # Network migration creates a different mapping; stale pair fails.
        mem[0x9000]=88
        self.assertFalse(self.probe(mem,args)["peer_map_consistent"])
        self.assertFalse(self.probe(mem,args)["authenticated_rage_sender_verified"])

    def test_same_event_register_peer_must_match(self):
        mem,args=self.fixture()
        read=lambda a:mem[a]
        good=mod.check_peer_session_map(read,read,*args,expected_peer_id=222)
        self.assertTrue(good["peer_map_consistent"])
        bad=mod.check_peer_session_map(read,read,*args,expected_peer_id=123)
        self.assertEqual(bad["status"],"same_callback_peer_register_mismatch")
        self.assertFalse(bad["authenticated_rage_sender_verified"])

if __name__=="__main__":unittest.main()
