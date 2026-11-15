"""Synthetic-only tests: no game executable or proprietary content."""
import importlib.util
import plistlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "winstom_rp_audit.py"
SPEC = importlib.util.spec_from_file_location("winstom_rp_audit", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def macho(uuid_bytes, cryptid, lib="librp.dylib", appendix=b"police cuff"):
    uuid_cmd = struct.pack("<II", 0x1B, 24) + uuid_bytes
    enc_cmd = struct.pack("<IIIIII", 0x2C, 24, 0, 0, cryptid, 0)
    name = lib.encode() + b"\x00"
    size = 24 + ((len(name) + 7) // 8) * 8
    dylib_cmd = struct.pack("<IIIIII", 0xC, size, 24, 0, 0, 0)
    dylib_cmd += name.ljust(size - 24, b"\x00")
    commands = uuid_cmd + enc_cmd + dylib_cmd
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, 2,
                         3, len(commands), 0, 0)
    return header + commands + appendix


def ipa(path, app, binary, add_unsafe=False):
    bundle = f"Payload/{app}.app/"
    info = {"CFBundleExecutable": "GTA5",
            "CFBundleIdentifier": "org.example.synthetic",
            "CFBundleVersion": "1",
            "CFBundleShortVersionString": "0.7.171",
            "MinimumOSVersion": "16.0"}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(bundle + "Info.plist", plistlib.dumps(info))
        z.writestr(bundle + "GTA5", binary)
        z.writestr(bundle + "Frameworks/librp.dylib", binary)
        if add_unsafe:
            z.writestr("../outside", b"do-not-extract")


class WinstomAuditTests(unittest.TestCase):
    def test_arm64_uuid_dependency_and_cryptid(self):
        raw = macho(bytes(range(16)), 1)
        m = mod.macho_metadata(raw)
        self.assertTrue(m["is_arm64"])
        self.assertEqual(m["cryptid"], 1)
        self.assertIn("librp.dylib", m["linked_libraries"])
        self.assertEqual(m["uuid"], "00010203-0405-0607-0809-0A0B0C0D0E0F")

    def test_detects_unsafe_zip_entry_without_extracting(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "one.ipa"
            ipa(p, "GTA", macho(bytes(range(16)), 0), add_unsafe=True)
            result = mod.audit_ipa(p)
            self.assertIn("unsafe-zip-entry", result["warnings"])
            self.assertEqual(len(result["apps"]), 1)
            self.assertEqual(len(result["binaries"]), 2)
            self.assertEqual(result["apps"][0]["version"], "0.7.171")
            self.assertIn("police", result["binaries"][0]["markers_in_first_1mib"])

    def test_hash_delta_normalizes_bundle_and_dylib_change(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.ipa", Path(d) / "b.ipa"
            ipa(a, "GTA", macho(bytes(range(16)), 0, "librp.dylib"))
            ipa(b, "Winstom", macho(bytes(reversed(range(16))), 1,
                                   "libnetworkrp.dylib"))
            delta = mod.compare_reports(mod.audit_ipa(a), mod.audit_ipa(b))
            self.assertEqual(len(delta["added_binaries"]), 0)
            self.assertEqual(len(delta["removed_binaries"]), 0)
            self.assertEqual(len(delta["changed_binaries"]), 2)
            self.assertIn("libnetworkrp.dylib",
                          delta["changed_binaries"][0]["added_linked_libraries"])
            self.assertEqual(delta["identical_binary_count"], 0)

    def test_non_macho_binary_is_not_misclassified(self):
        self.assertIsNone(mod.macho_metadata(b"This is not a MachO"))
        self.assertTrue(mod.unsafe_path("../key"))
        self.assertTrue(mod.unsafe_path("/private/file"))
        self.assertFalse(mod.unsafe_path("Payload/Test.app/GTA5"))


if __name__ == "__main__":
    unittest.main()
