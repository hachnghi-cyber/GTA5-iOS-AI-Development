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
