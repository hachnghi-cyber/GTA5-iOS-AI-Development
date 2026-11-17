"""Synthetic read-only OnNetEvent pre-dispatch observer; never a device claim."""
import importlib.util
import unittest
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"tools"/"observe_v133_lldb.py"
spec=importlib.util.spec_from_file_location("observer_pre_dispatch",path)
observer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
class PreDispatchTests(unittest.TestCase):
    @staticmethod
    def fixture():
        mem={0x1000+0x128:0x2000,0x5000+0x3c:77,
             0x2000+0x18:76,0x2000+0x38:0x3000,
             0x3000+0x18:77,0x3000+0x38:0}
        return mem,(0x1000,0x5000,0x3000,0x4000)
    def run_probe(self,mem,args):
        read=lambda a:mem[a]
        return observer.scan_pre_dispatch(read,read,*args)
    def test_candidate_never_auth(self):
        mem,args=self.fixture();r=self.run_probe(mem,args)
        self.assertEqual(r["status"],"connection_candidate_only")
        self.assertEqual(r["players_scanned"],2)
        self.assertTrue(r["selected_sender_in_player_list"])
        for name in ("authenticated_rp_sender_verified",
                     "session_membership_verified","session_generation_verified"):
            self.assertFalse(r[name])
        self.assertNotIn("player_ptr",r);self.assertNotIn("connection_id",r)
    def test_wrong_selected_or_local_rejected(self):
        mem,args=self.fixture()
        self.assertEqual(self.run_probe(mem,(args[0],args[1],args[2],args[2]))["status"],"sender_aliases_local")
        mem[0x3000+0x18]=99
        self.assertEqual(self.run_probe(mem,args)["status"],"sender_connection_mismatch")
        mem[0x3000+0x18]=77
        self.assertEqual(self.run_probe(mem,(0,args[1],args[2],args[3]))["status"],"invalid_entry")
        del mem[0x5000+0x3c]
        self.assertEqual(self.run_probe(mem,args)["status"],"read_failed")
    def test_ambiguous_and_cycle_rejected(self):
        mem,args=self.fixture();mem[0x2000+0x18]=77
        self.assertEqual(self.run_probe(mem,args)["status"],"no_unique_selected_sender")
        mem[0x2000+0x18]=76;mem[0x3000+0x38]=0x2000
        self.assertEqual(self.run_probe(mem,args)["status"],"list_cycle")
    def test_bounded_32(self):
        mem,args=self.fixture();mem[0x1000+0x128]=0x2000
        for i in range(33):
            p=0x2000+0x100*i
            mem[p+0x18]=77 if p==0x3000 else 100+i
            mem[p+0x38]=p+0x100 if i<32 else 0
        self.assertEqual(self.run_probe(mem,args)["status"],"list_exceeds_32")
    def test_internal_site_is_not_a_fake_symbol(self):
        import json
        b=json.loads(observer.BASELINE.read_text())
        self.assertEqual(b["internal_sites"]["on_net_event_pre_dispatch"],"0x1020249a8")
        self.assertEqual(b["trace_sites"]["on_net_event_pre_dispatch"],"0xa9012be9")
        self.assertNotIn("on_net_event_pre_dispatch",b["symbols"])
if __name__=="__main__":unittest.main()
