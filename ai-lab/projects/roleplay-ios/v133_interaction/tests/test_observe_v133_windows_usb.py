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
