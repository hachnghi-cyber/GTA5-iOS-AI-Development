"""P0 combined-source test: PR #4 nearest-player selector + PR #9 game bridge.

Compiles and executes the unmodified C implementations together using a
synthetic three-player engine callback and authenticated-delivery simulation.
This is a host-only source compatibility regression, not GTA gameplay.
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
    "Integration/test_p0_combined_selection.c",
)


class P0CombinedTargetBridgeTests(unittest.TestCase):
    def compile_run(self, compiler, sanitized):
        with tempfile.TemporaryDirectory(prefix="p0-combined-c-") as tmp:
            binary = Path(tmp) / "test_combined"
            flags = ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic"]
            if sanitized:
                flags += ["-g", "-fno-omit-frame-pointer",
                          "-fsanitize=address,undefined",
                          "-fno-sanitize-recover=all"]
            else:
                # Existing GCC-only warning in pinned PR4 C code.
                flags += ["-Wno-error=misleading-indentation"]
            command = [compiler, *flags,
                       *[str(RP / path) for path in SOURCES],
                       "-lm", "-o", str(binary)]
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=60, check=False)
            self.assertEqual(result.returncode, 0,
                             "Combined C compile failed:\n" +
                             result.stdout + result.stderr)
            run = subprocess.run(
                [str(binary)], capture_output=True, text=True,
                timeout=30, check=False)
            self.assertEqual(run.returncode, 0,
                             "Combined C regression failed:\n" +
                             run.stdout + run.stderr)
            self.assertIn(
                "combined target-to-bridge consent and restriction simulation passed",
                run.stdout)
            self.assertIn("device_tested=false", run.stdout)

    def test_combined_target_bridge_gcc_or_cc(self):
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not cc:
            self.skipTest("C compiler unavailable")
        self.compile_run(cc, sanitized=False)

    def test_combined_target_bridge_clang_asan_ubsan(self):
        cc = shutil.which("clang")
        if not cc:
            self.skipTest("Clang sanitizers unavailable")
        self.compile_run(cc, sanitized=True)


if __name__ == "__main__":
    unittest.main()
