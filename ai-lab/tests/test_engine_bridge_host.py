"""Host-only regression for the GTA v12 Police RP synthetic engine bridge.

Compiles the real C bridge and its existing C simulator. No IPA, genuine GTA
networking, iOS SDK or device is exercised. Sanitizers cover executed paths.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RP = ROOT / "police-rp" / "v1.4"
SOURCES = (
    "NativeBridge/police_rp_only.c",
    "NativeBridge/police_rp_adapter.c",
    "P2P/prp_p2p.c",
    "P2P/prp_runtime.c",
    "Integration/prp_mailbox.c",
    "Integration/prp_engine_binding.c",
    "Integration/test_engine_binding.c",
)


class EngineBridgeHostTests(unittest.TestCase):
    def _compile_and_run(self, cc, sanitized=False):
        with tempfile.TemporaryDirectory(prefix="rp-bridge-host-") as temp:
            binary = Path(temp) / "test_engine_binding"
            flags = ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                     "-pedantic"]
            if sanitized:
                flags += ["-g", "-fno-omit-frame-pointer",
                          "-fsanitize=address,undefined",
                          "-fno-sanitize-recover=all"]
            else:
                # Two existing GCC indentation warnings in prp_p2p.c are
                # addressed separately in draft PR #4. Keep other warnings
                # fatal rather than editing that PR's source from here.
                flags.append("-Wno-error=misleading-indentation")
            cmd = [cc, *flags, *[str(RP / item) for item in SOURCES],
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

    def test_duplicate_ids_fail_closed_and_active_session_resets(self):
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if cc is None:
            self.skipTest("Host C11 compiler unavailable")
        self._compile_and_run(cc)

    def test_clang_asan_ubsan_bridge_regression(self):
        clang = shutil.which("clang")
        if clang is None:
            self.skipTest("Clang sanitizers unavailable")
        self._compile_and_run(clang, sanitized=True)


if __name__ == "__main__":
    unittest.main()
