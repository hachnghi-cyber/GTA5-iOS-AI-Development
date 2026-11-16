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
