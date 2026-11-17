"""Host checks for diagnostic labels. No real device evidence is synthesized."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools" / "observe_v133_lldb.py"
spec = importlib.util.spec_from_file_location("observer", path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class StackObservationTests(unittest.TestCase):
    def test_route_requires_receive_ancestry_and_no_local_send(self):
        for frames, expected in (
            (["script_event_handler", "dispatch"], "undetermined"),
            (["on_net_event"], "undetermined"),
            (["on_net_event", "connection_dispatch"], "network_receive_stack"),
            (["send_buffer"], "local_send_stack"),
            (["send_buffer", "on_net_event"], "undetermined"),
            (["send_buffer", "on_net_event", "connection_dispatch"], "undetermined"),
        ):
            with self.subTest(frames=frames):
                info = observer.describe_stack("script_event_handler", frames, "T1")
                self.assertEqual(info["observed_path"], expected)
                self.assertEqual(info["thread_label"], "T1")
                self.assertIs(info["authenticated_rp_sender_verified"], False)
                self.assertIs(info["session_generation_verified"], False)


class OnNetConnectionReadOnlyTests(unittest.TestCase):
    @staticmethod
    def memory():
        mem={0x1000+0x128:0x2000,0x5000+0x3c:77,
             0x2000+0x18:76,0x2000+0x38:0x3000,
             0x3000+0x18:77,0x3000+0x38:0}
        return mem

    def test_exact_unique_match_no_auth_or_raw_ids(self):
        mem=self.memory()
        read=lambda addr:mem[addr]
        r=observer.scan_remote_connection(read,read,0x1000,0x5000)
        self.assertEqual(r["status"],"connection_candidate_only")
        self.assertEqual(r["players_scanned"],2)
        self.assertTrue(r["single_connection_match"])
        self.assertFalse(r["authenticated_rp_sender_verified"])
        self.assertFalse(r["session_generation_verified"])
        self.assertNotIn("event_connection_id",r)
        self.assertNotIn("source_pointer",r)

    def test_none_or_ambiguous_is_fail_closed(self):
        mem=self.memory();read=lambda addr:mem[addr]
        mem[0x3000+0x18]=78
        self.assertEqual(observer.scan_remote_connection(read,read,0x1000,0x5000)["status"],
                         "no_matching_player")
        mem[0x3000+0x18]=76
        mem[0x5000+0x3c]=76
        self.assertEqual(observer.scan_remote_connection(read,read,0x1000,0x5000)["status"],
                         "ambiguous_duplicate_connection")

    def test_invalid_cycle_and_read_error(self):
        mem=self.memory();read=lambda addr:mem[addr]
        self.assertEqual(observer.scan_remote_connection(read,read,0,0x5000)["status"],
                         "invalid_entry")
        mem[0x2000+0x38]=0x2000
        self.assertEqual(observer.scan_remote_connection(read,read,0x1000,0x5000)["status"],
                         "cyclic_player_list")
        mem[0x5000+0x3c]=0x80000001
        self.assertEqual(observer.scan_remote_connection(read,read,0x1000,0x5000)["status"],
                         "invalid_event_connection")
        del mem[0x5000+0x3c]
        self.assertEqual(observer.scan_remote_connection(read,read,0x1000,0x5000)["status"],
                         "read_failed")

    def test_player_list_overflow_rejects_partial_match(self):
        mem={0x1000+0x128:0x2000,0x5000+0x3c:77}
        for i in range(33):
            ptr=0x2000+0x100*i
            mem[ptr+0x18]=77 if i==1 else 100+i
            mem[ptr+0x38]=ptr+0x100 if i<32 else 0
        r=observer.scan_remote_connection(lambda a:mem[a],lambda a:mem[a],
                                          0x1000,0x5000)
        self.assertEqual(r["status"],"list_exceeds_32")
        self.assertEqual(r["players_scanned"],32)
        self.assertFalse(r["single_connection_match"])


class NativeGamerInfoReadOnlyTests(unittest.TestCase):
    def test_valid_layout_returns_only_presence(self):
        ptr=0x1000; vtab=0x3000; info=0x5000; expected=0x8000
        mem={ptr:vtab,vtab+0x38:expected,ptr+0xa0:info,
             info+0x1f0:0x123456789}
        result=observer.scan_selected_peer_identity(lambda a:mem[a],ptr,expected)
        self.assertEqual(result["status"],"netplayer_peer_id_candidate_only")
        self.assertTrue(result["peer_id_present"])
        self.assertFalse(result["authenticated_rp_sender_verified"])
        self.assertFalse(result["session_membership_verified"])
        self.assertNotIn("peer_id",result)
        self.assertNotIn("gamer_info_address",result)

    def test_vtable_layout_mismatch_rejected(self):
        ptr=0x1000;mem={ptr:0x2000,0x2000+0x38:0x4000,
                        ptr+0xa0:0x3000,0x3000+0x1f0:456}
        read=lambda a:mem[a]
        self.assertEqual(observer.scan_selected_peer_identity(read,ptr,0x4001)["status"],
                         "unexpected_gamer_info_vtable")
        mem[0x2000+0x38]=0x4001;mem[ptr+0xa0]=0
        self.assertEqual(observer.scan_selected_peer_identity(read,ptr,0x4001)["status"],
                         "missing_player_info")
        mem[ptr+0xa0]=0x3000
        for bad in (0,0xffffffffffffffff):
            mem[0x3000+0x1f0]=bad
            self.assertEqual(observer.scan_selected_peer_identity(read,ptr,0x4001)["status"],
                             "invalid_peer_id")
        del mem[0x3000+0x1f0]
        self.assertEqual(observer.scan_selected_peer_identity(read,ptr,0x4001)["status"],
                         "read_failed")

    def test_pinned_peer_getter_matches_exact_original(self):
        import json
        baseline=json.loads(observer.BASELINE.read_text())
        p=baseline["peer_info_static"]
        self.assertEqual(p["getter_va"],"0x1018d92e8")
        self.assertEqual(p["getter_instruction"],"0xf9405008")
        self.assertEqual(p["getter_next_instruction"],"0x91008100")
        self.assertEqual(p["peer_getter_instruction"],"0xf940e800")

    def test_connection_peer_verify_site_is_internal_not_symbol(self):
        import json
        b=json.loads(observer.BASELINE.read_text())
        self.assertEqual(b["internal_sites"]["on_connection_peer_verify"],"0x1017dfa48")
        self.assertEqual(b["trace_sites"]["on_connection_peer_verify"],"0x9407da23")
        self.assertNotIn("on_connection_peer_verify",b["symbols"])


class OpaqueConnectionTagTests(unittest.TestCase):
    def test_correlates_same_process_without_raw_id(self):
        a=observer.ephemeral_connection_tag(10001,77)
        b=observer.ephemeral_connection_tag(10001,77)
        c=observer.ephemeral_connection_tag(10001,78)
        self.assertEqual(a,b)
        self.assertNotEqual(a,c)
        self.assertIsInstance(a,str)
        self.assertEqual(len(a),24)
        self.assertNotIn(str(77),a)

    def test_rotates_on_new_process_and_rejects_invalid_id(self):
        a=observer.ephemeral_connection_tag(10001,77)
        b=observer.ephemeral_connection_tag(10002,77)
        self.assertNotEqual(a,b)
        self.assertIsNone(observer.ephemeral_connection_tag(0,77))
        self.assertIsNone(observer.ephemeral_connection_tag(10002,-1))
        self.assertIsNone(observer.ephemeral_connection_tag(10002,0x80000000))
