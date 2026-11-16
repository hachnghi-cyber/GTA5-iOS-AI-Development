"""Synthetic transport fixtures for the Windows observer. No device evidence."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools" / "observe_v133_windows_usb.py"
spec = importlib.util.spec_from_file_location("observer_usb", path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class Connection:
    def __init__(self, *chunks):
        self.chunks = iter(chunks)
        self.sent = []

    def recv(self, _):
        return next(self.chunks, b"")

    def sendall(self, data):
        self.sent.append(data)


class DebugReplyTests(unittest.TestCase):
    def test_split_reply_preserves_next_frame(self):
        conn = Connection(b"+$O", b"K#9", b"a$#00")
        remote = observer.Remote(conn)
        self.assertEqual(remote.receive(), b"OK")
        self.assertEqual(remote.receive(), b"")
        self.assertEqual(conn.sent, [b"+", b"+"])

    def test_corrupt_or_oversized_reply_is_rejected(self):
        for frame in (b"$OK#00", b"$" + b"A" * (observer.MAX_REPLY + 1) + b"#00"):
            with self.subTest(length=len(frame)):
                conn = Connection(frame)
                with self.assertRaises(observer.DebugProtocolError):
                    observer.Remote(conn).receive()
                self.assertEqual(conn.sent, [])

    def test_non_stop_reply_cannot_supply_a_thread(self):
        self.assertIsNone(observer.stop_thread(b"OK"))
        self.assertIsNone(observer.stop_thread(b"T05name:Game;"))
        self.assertEqual(observer.stop_thread(b"T05thread:abcd;"), b"abcd")


class LocalStockJobTests(unittest.TestCase):
    def test_read_only_sample_does_not_report_unknown_job_ids_or_roles(self):
        fields = {"id_va": "0x100000100", "kind_va": "0x100000200", "state_va": "0x100000300"}
        base = 0x101000000

        class Memory:
            def __init__(self, value):
                self.values = {base+0x100: value.ljust(40, b"\0"),
                               base+0x200: (4).to_bytes(4, "little"),
                               base+0x300: (1).to_bytes(4, "little")}

            def memory(self, address, size):
                assert len(self.values[address]) == size
                return self.values[address]

        candidate = observer.read_stock_job(Memory(b"cop_ls"), base, fields)
        self.assertTrue(candidate["job_id_is_cop_ls"])
        self.assertFalse(candidate["police_role_authorized"])
        unknown = observer.read_stock_job(Memory(b"unrelated_job"), base, fields)
        self.assertFalse(unknown["job_id_known"])
        self.assertNotIn("unrelated_job", str(unknown))


class _BreakConn:
    def __init__(self):
        self.timeouts = []
        self.sent = []

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def sendall(self, data):
        self.sent.append(data)


class _BreakRemote:
    def __init__(self, pc, lr=0, time_out=False):
        self.conn = _BreakConn()
        self.pc = pc
        self.lr = lr
        self.time_out = time_out
        self.sent = []
        self.requests = []
        self.register_reads = []

    def request(self, packet):
        self.requests.append(packet)
        if packet == b"qRegisterInfo20":
            return b"name:pc;bitsize:64;"
        if packet == b"qRegisterInfo1e":
            return b"name:lr;bitsize:64;"
        if packet.startswith((b"Z1,", b"z1,", b"Hg")):
            return b"OK"
        raise AssertionError("unexpected debugger packet")

    def send(self, packet):
        self.sent.append(packet)

    def receive(self):
        if self.time_out:
            self.time_out = False
            raise TimeoutError()
        return b"T05thread:abcd;"

    def read_register(self, number):
        self.register_reads.append(number)
        return {32: self.pc, 30: self.lr}[number]


class ScriptEventObserverTests(unittest.TestCase):
    def setUp(self):
        self.base = 0x102000000
        self.va = "0x100012340"
        self.pc = self.base + int(self.va, 16) - observer.IMAGE_VMADDR
        self.metadata = {"symbols": {"script_event_handler": {"va": self.va}}, "branches": []}

    def test_read_only_script_handler_hit_never_claims_authenticated_event(self):
        remote = _BreakRemote(self.pc)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler", wait_seconds=30)
        self.assertEqual(sample["site"], "script_event_handler")
        self.assertTrue(sample["hardware_stop_at_expected_pc"])
        for key in ("network_receive_stack_confirmed", "authenticated_rp_sender_verified",
                    "session_generation_verified", "custom_rp_event_received"):
            self.assertIs(sample[key], False)
        self.assertEqual(sample["observed_path"], "undetermined")
        self.assertFalse(sample["macport_online_update_callsite_matches"])
        self.assertEqual(remote.sent, [b"c"])
        self.assertEqual(remote.conn.timeouts, [30])
        self.assertEqual(remote.register_reads, [32])
        self.assertEqual(remote.requests[-1], f"z1,{self.pc:x},4".encode())
        self.assertFalse(any(request.startswith(b"Z0,") for request in remote.requests))

    def test_script_site_with_unexpected_pc_does_not_report_hit(self):
        remote = _BreakRemote(self.pc + 4)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler")
        self.assertFalse(sample["hardware_stop_at_expected_pc"])

    def test_timeout_is_not_a_breakpoint_hit_even_if_pc_matches(self):
        remote = _BreakRemote(self.pc, time_out=True)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler")
        self.assertTrue(sample["timed_out"])
        self.assertFalse(sample["hardware_stop_at_expected_pc"])
        self.assertEqual(remote.conn.sent, [bytes([3])])
        self.assertTrue(remote.requests[-1].startswith(b"z1,"))

    def test_reject_unsupported_site_stock_job_and_unbounded_wait(self):
        for kwargs in ({"site": "unverified_hook"},
                       {"site": "script_event_handler", "stock_job": True},
                       {"site": "script_event_handler", "wait_seconds": 0},
                       {"site": "script_event_handler", "wait_seconds": 61}):
            with self.subTest(kwargs=kwargs):
                remote = _BreakRemote(self.pc)
                with self.assertRaises(ValueError):
                    observer.capture(remote, self.base, self.metadata, **kwargs)
                self.assertEqual(remote.sent, [])
                self.assertEqual(remote.requests, [])
