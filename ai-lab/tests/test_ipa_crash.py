import importlib.util
import plistlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

audit = load("audit_ipa")
diff = load("compare_ipa")
crash = load("crash_triage")

class IPAAndCrashTests(unittest.TestCase):
    def test_macho_arm64(self):
        data = struct.pack("<IIIIIIII", 0xfeedfacf, 0x0100000c, 0, 2, 0, 0, 0, 0)
        self.assertTrue(audit.parse_macho(data)["is_arm64"])
    def test_reject_path(self):
        self.assertTrue(audit.is_unsafe_path("../bad"))
        self.assertFalse(audit.is_unsafe_path("Payload/Test.app/Test"))
    def test_crash_signals(self):
        x = crash.triage_text("SIGSEGV pc=0x1234\nDevice iPhone15,2")
        self.assertIn("SIGSEGV", x["signals"])
        self.assertIn("iPhone15,2", x["devices"])
    def test_ipa_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, second = base / "first.ipa", base / "second.ipa"
            executable = struct.pack("<IIIIIIII", 0xfeedfacf, 0x0100000c, 0, 2, 0, 0, 0, 0)
            info = plistlib.dumps({"CFBundleIdentifier": "org.example.test",
                                    "CFBundleExecutable": "Test"})
            for path, binary in ((first, executable), (second, executable + b"x")):
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("Payload/Test.app/Info.plist", info)
                    z.writestr("Payload/Test.app/Test", binary)
            x = audit.audit(first)
            self.assertEqual(x["app_bundles"][0]["bundle_id"], "org.example.test")
            self.assertTrue(x["macho"][0]["is_arm64"])
            self.assertIn("Payload/Test.app/Test", diff.compare(first, second)["modified_files"])

if __name__ == "__main__":
    unittest.main()
