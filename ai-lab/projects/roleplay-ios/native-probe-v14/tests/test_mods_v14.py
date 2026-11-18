import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest

LIB = Path(__file__).resolve().parents[1] / "build" / "RPBridgeProbe.so"

def frame(seq, corrupt=False):
    b = bytearray(48)
    b[:4] = b'RPF8'
    b[4] = 8; b[6] = 48
    struct.pack_into("<IIIffffI", b, 8, seq, 2, 4, 1., 2., 3., 90., 0)
    struct.pack_into("<I", b, 40, 0x08112026)
    h = 2166136261
    for x in b[:44]:
        h = ((h ^ x) * 16777619) & 0xffffffff
    struct.pack_into("<I", b, 44, h ^ (1 if corrupt else 0))
    return b

def run(home, after=None):
    log = home / "Documents" / "RPBridgeProbe_v14.log"
    p = subprocess.Popen([sys.executable, "-c",
        "import ctypes,time; ctypes.CDLL(%r); time.sleep(2.2)" % str(LIB)],
        env={**os.environ, "HOME": str(home)}, cwd=home)
    try:
        if after:
            end = time.monotonic() + 1.5
            while time.monotonic() < end:
                s = log.read_text() if log.exists() else ""
                if "POSE_FIRST_FRAME" in s or "INVALID_FRAME" in s:
                    break
                time.sleep(.03)
            else:
                raise AssertionError("no first frame before producer update")
            after()
        p.wait(timeout=5)
        assert p.returncode == 0
    finally:
        if p.poll() is None:
            p.kill(); p.wait()
    return log.read_text()

class ModsPriorityProof(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "Documents" / "Mods").mkdir(parents=True)
    def tearDown(self):
        self.tmp.cleanup()
    def test_mods_root(self):
        f = self.home / "Documents/Mods/RPV08_pose.bin"
        f.write_bytes(frame(12))
        s = run(self.home, lambda: f.write_bytes(frame(14)))
        self.assertIn("FILE_SOURCE bucket=mods_root", s)
        self.assertIn("POSE_LIVE", s)
    def test_mod_folder_before_large_unrelated_assets(self):
        d = self.home / "Documents" / "0huge"
        d.mkdir()
        for i in range(3200):
            (d / ("%04d.txt" % i)).touch()
        f = self.home / "Documents" / "Mods" / "RPPoseToFile-v0.8-E" / "RPV08_pose.bin"
        f.parent.mkdir()
        f.write_bytes(frame(17))
        s = run(self.home, lambda: f.write_bytes(frame(18)))
        self.assertIn("FILE_SOURCE bucket=mods_child", s)
        self.assertIn("POSE_LIVE", s)
    def test_reject_bad_crc(self):
        f = self.home / "Documents/Mods/RPV08_pose.bin"
        f.write_bytes(frame(12, corrupt=True))
        s = run(self.home)
        self.assertIn("INVALID_FRAME", s)
        self.assertNotIn("POSE_LIVE", s)
    def test_symlink_rejected(self):
        target = self.home / "outside.bin"
        target.write_bytes(frame(12))
        (self.home / "Documents/Mods/RPV08_pose.bin").symlink_to(target)
        s = run(self.home)
        self.assertIn("FILE_NOT_FOUND", s)
        self.assertNotIn("FILE_SOURCE", s)

if __name__ == "__main__":
    unittest.main()
