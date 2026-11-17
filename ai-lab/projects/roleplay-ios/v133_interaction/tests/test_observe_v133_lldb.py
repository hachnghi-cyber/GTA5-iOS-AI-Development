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
