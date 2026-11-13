"""Host-only build/regression for the v1.4 synthetic engine snapshot bridge.

Compiles the real C bridge and its existing C simulator; neither an IPA nor a
GTA game-frame callback is executed. No iPhone/iPad test is implied.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RP = ROOT / "police-rp" / "v1.4"


class EngineBridgeHostTests(unittest.TestCase):
    def test_duplicate_connected_ids_fail_closed_and_valid_frame_recovers(self):
        cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if cc is None:
            self.skipTest("Host C11 compiler unavailable")
        sources = (
            "NativeBridge/police_rp_only.c",
            "NativeBridge/police_rp_adapter.c",
            "P2P/prp_p2p.c",
            "P2P/prp_runtime.c",
            "Integration/prp_mailbox.c",
            "Integration/prp_engine_binding.c",
            "Integration/test_engine_binding.c",
        )
        with tempfile.TemporaryDirectory(prefix="rp-bridge-host-") as temp:
            binary = Path(temp) / "test_engine_binding"
            # Main still has two pre-existing GCC indentation warnings in
            # prp_p2p.c (already corrected separately in draft PR #4).
            # Keep all other warnings fatal; do not alter P2P logic here.
            cmd = [cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                   "-Wno-error=misleading-indentation", "-pedantic",
                   *[str(RP / item) for item in sources],
                   "-lm", "-o", str(binary)]
            compile_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=90, check=False
            )
            self.assertEqual(compile_result.returncode, 0,
                             "Host C compilation failed:\n" +
                             compile_result.stdout + compile_result.stderr)
            test_result = subprocess.run(
                [str(binary)], capture_output=True, text=True,
                timeout=30, check=False
            )
            self.assertEqual(test_result.returncode, 0,
                             "Host C engine bridge test failed:\n" +
                             test_result.stdout + test_result.stderr)
            self.assertIn("engine binding simulation passed", test_result.stdout)


if __name__ == "__main__":
    unittest.main()
