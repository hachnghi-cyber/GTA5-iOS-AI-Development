import ctypes
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ctypes.CDLL(str(ROOT / "libRPBridgeNetworkV15-test.so"))
LIB.rp_test_private.argtypes = [ctypes.c_char_p]
LIB.rp_test_private.restype = ctypes.c_int
LIB.rp_test_config.argtypes = [ctypes.c_char_p]
LIB.rp_test_config.restype = ctypes.c_int

class Pose(ctypes.Structure):
    _fields_ = [("sequence", ctypes.c_uint32), ("ped", ctypes.c_uint32),
                ("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float),
                ("h", ctypes.c_float)]
LIB.rp_test_read.argtypes = [ctypes.c_char_p, ctypes.POINTER(Pose)]
LIB.rp_test_read.restype = ctypes.c_int

def sample(seq, x=1.0):
    raw = bytearray(48)
    raw[:4] = b"RPF8"
    raw[4], raw[6] = 8, 48
    struct.pack_into("<IIIffff", raw, 8, seq, 2, 4, x, 20., 30., 45.)
    struct.pack_into("<I", raw, 40, 0x08112026)
    h = 2166136261
    for c in raw[:44]:
        h = ((h ^ c) * 16777619) & 0xffffffff
    struct.pack_into("<I", raw, 44, h)
    return bytes(raw)

def wait_until(condition, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition(): return
        time.sleep(.035)
    raise AssertionError("Timed out waiting for expected bridge event")

class RPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        (self.home / "Documents/Mods").mkdir(parents=True)
    def tearDown(self):
        self.directory.cleanup()

    def config(self, port, key="test_room_key_2026", host="127.0.0.1", enable="1"):
        (self.home / "Documents/RPBridgeNetwork_v15.conf").write_text(
            f"enabled={enable}\nhost={host}\nport={port}\n"
            f"room=VNTEST\nname=PhoneA\nroom_key={key}\n")

    def test_default_off_and_private_only(self):
        self.assertEqual(LIB.rp_test_config(str(self.home).encode()), 0)
        for a in ("10.0.0.1", "192.168.1.10", "172.16.0.1", "127.0.0.1"):
            self.assertEqual(LIB.rp_test_private(a.encode()), 1)
        for a in ("8.8.8.8", "172.32.0.1", "0.0.0.0", "example.org"):
            self.assertEqual(LIB.rp_test_private(a.encode()), 0)
        self.config(7789, enable="0")
        self.assertEqual(LIB.rp_test_config(str(self.home).encode()), 0)
        self.config(7789, host="1.1.1.1")
        self.assertEqual(LIB.rp_test_config(str(self.home).encode()), -1)

    def test_crc(self):
        f = self.home / "Documents/Mods/RPV08_pose.bin"
        f.write_bytes(sample(5))
        p = Pose()
        self.assertEqual(LIB.rp_test_read(str(f).encode(), ctypes.byref(p)), 1)
        self.assertEqual(p.sequence, 5)
        corrupted = bytearray(sample(6)); corrupted[22] ^= 1
        f.write_bytes(corrupted)
        self.assertEqual(LIB.rp_test_read(str(f).encode(), ctypes.byref(p)), 0)

    def test_tcp_welcome_and_pose_from_mods_child(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(6)
        port = listener.getsockname()[1]
        self.config(port)
        posefile = self.home / "Documents/Mods/RPPoseToFile-v0.8-E/RPV08_pose.bin"
        posefile.parent.mkdir()
        posefile.write_bytes(sample(50))
        events = []

        def mock_server():
            try:
                with listener:
                    conn, _ = listener.accept()
                    with conn:
                        conn.settimeout(5)
                        fp = conn.makefile("rwb", buffering=0)
                        hello = json.loads(fp.readline())
                        events.append(hello)
                        if hello["room_key"] != "test_room_key_2026":
                            return
                        fp.write(b'{"type":"welcome","protocol":1,"id":"000000000001","room":"VNTEST"}\n')
                        packet = json.loads(fp.readline())
                        events.append(packet)
            except Exception as exc:
                events.append(exc)

        server = threading.Thread(target=mock_server, daemon=True)
        server.start()
        worker = subprocess.Popen(
            [sys.executable, "-c",
             f"import ctypes; ctypes.CDLL({str(ROOT / 'libRPBridgeNetworkV15-test.so')!r}).rp_test_main()"],
            env={**os.environ, "HOME": str(self.home)})
        try:
            log = self.home / "Documents/RPBridgeNetwork_v15.log"
            wait_until(lambda: log.exists() and "POSE_INITIAL_READ" in log.read_text())
            posefile.write_bytes(sample(51, 18.0))
            wait_until(lambda: log.exists() and "POSE_SENT_TO_TCP" in log.read_text())
            server.join(timeout=5)
            self.assertEqual(len(events), 2, events)
            self.assertEqual(events[1]["type"], "pose")
            self.assertEqual(events[1]["seq"], 1)
            self.assertAlmostEqual(events[1]["x"], 18.0, places=2)
        finally:
            worker.terminate(); worker.wait(timeout=4)
            listener.close()

if __name__ == "__main__":
    unittest.main()
