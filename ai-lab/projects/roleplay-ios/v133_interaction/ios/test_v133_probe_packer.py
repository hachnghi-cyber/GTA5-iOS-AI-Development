"""Synthetic Mach-O tests. No GTA binaries are used in this test."""
import hashlib
import importlib.util
import plistlib
import sys
import tempfile
import zipfile
from unittest import mock
import struct
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("patch_exact_v133_probe.py")
SPEC = importlib.util.spec_from_file_location("v133_exact_packer", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture(filetype=2, section_at=4096):
    # thin ARM64 with 1 x 64-bit segment containing one synthetic section.
    # No code is executed by these tests.
    segment = bytearray(152)
    struct.pack_into("<II", segment, 0, 0x19, 152)
    struct.pack_into("<I", segment, 64, 1)
    struct.pack_into("<I", segment, 72 + 48, section_at)
    uuid = struct.pack("<II", 0x1B, 24) + bytes(range(16))
    cmds = bytes(segment) + uuid
    head = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, filetype,
                       2, len(cmds), 0, 0)
    buf = bytearray(8192)
    buf[:len(head + cmds)] = head + cmds
    buf[section_at:section_at + 8] = b"CODEDATA"
    return bytes(buf)


class PackerTests(unittest.TestCase):
    def test_macho_header_and_slack(self):
        f = fixture()
        report = mod.header_info(f)
        self.assertEqual(report["type"], mod.MH_EXECUTE)
        self.assertEqual(report["first_section"], 4096)
        self.assertEqual(report["ncmds"], 2)
        self.assertGreater(report["slack"], 64)

    def test_patcher_adds_only_a_load_command_and_keeps_code(self):
        original = fixture()
        digest = mod.GTA5_SHA256
        try:
            mod.GTA5_SHA256 = hashlib.sha256(original).hexdigest()
            changed, details = mod.patch_gta5(original)
        finally:
            mod.GTA5_SHA256 = digest
        self.assertEqual(len(changed), len(original))
        self.assertEqual(changed[4096:], original[4096:])
        self.assertNotEqual(changed, original)
        result = mod.header_info(changed)
        self.assertIn(mod.LOAD_PATH, result["dylibs"])
        self.assertEqual(result["ncmds"], 3)
        self.assertTrue(details["remaining_slack"] >= 0)

    def test_refuses_wrong_original_and_wrong_filetype(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            mod.patch_gta5(fixture())
        other = fixture(filetype=6)
        previous = mod.GTA5_SHA256
        try:
            mod.GTA5_SHA256 = hashlib.sha256(other).hexdigest()
            with self.assertRaisesRegex(ValueError, "Target is not an executable"):
                mod.patch_gta5(other)
        finally:
            mod.GTA5_SHA256 = previous

    def test_cannot_overlap_section_padding(self):
        raw = fixture(section_at=256)
        previous = mod.GTA5_SHA256
        try:
            mod.GTA5_SHA256 = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "Insufficient header padding"):
                mod.patch_gta5(raw)
        finally:
            mod.GTA5_SHA256 = previous

    def test_full_unsigned_ipa_repack_and_file_sharing(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "GTAV-v13.3.ipa"
            target = folder / "GTAV-v13.3-Phase8-Probe-UNSIGNED.ipa"
            bridge = folder / "PoliceRPV133Probe.dylib"
            main_bytes = fixture()
            bridge_bytes = fixture(filetype=mod.MH_DYLIB)
            plist = plistlib.dumps({"CFBundleIdentifier": "com.macport.gtav"},
                                   fmt=plistlib.FMT_BINARY)
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(mod.GTA5_PATH, main_bytes)
                archive.writestr(mod.PLIST_PATH, plist)
                archive.writestr("Payload/GTAV.app/unchanged.txt", b"KEEP_THIS_ASSET")
            bridge.write_bytes(bridge_bytes)
            old_game_sha, old_ipa_sha = mod.GTA5_SHA256, mod.IPA_SHA256
            try:
                mod.GTA5_SHA256 = hashlib.sha256(main_bytes).hexdigest()
                mod.IPA_SHA256 = hashlib.sha256(source.read_bytes()).hexdigest()
                with mock.patch.object(sys, "argv", [
                    "patch_exact_v133_probe.py", "--ipa", str(source),
                    "--bridge", str(bridge), "--out", str(target),
                    "--enable-file-sharing",
                ]):
                    mod.main()
            finally:
                mod.GTA5_SHA256, mod.IPA_SHA256 = old_game_sha, old_ipa_sha

            self.assertTrue(target.is_file())
            with zipfile.ZipFile(source) as original, zipfile.ZipFile(target) as out:
                self.assertIsNone(out.testzip())
                self.assertEqual(out.read("Payload/GTAV.app/unchanged.txt"), b"KEEP_THIS_ASSET")
                self.assertEqual(out.read(mod.BRIDGE_PATH), bridge_bytes)
                edited_gta = out.read(mod.GTA5_PATH)
                self.assertEqual(len(edited_gta), len(main_bytes))
                self.assertEqual(edited_gta[4096:], main_bytes[4096:])
                self.assertIn(mod.LOAD_PATH, mod.header_info(edited_gta)["dylibs"])
                self.assertEqual(original.read(mod.GTA5_PATH), main_bytes)
                plist_after = plistlib.loads(out.read(mod.PLIST_PATH))
                self.assertIs(plist_after["UIFileSharingEnabled"], True)
                self.assertIs(plist_after["LSSupportsOpeningDocumentsInPlace"], True)
                self.assertEqual(plist_after["CFBundleIdentifier"], "com.macport.gtav")

    def test_refuses_non_macho(self):
        with self.assertRaises(ValueError):
            mod.header_info(b"THIS IS NOT MACH-O")
        with self.assertRaises(ValueError):
            mod.check_bridge(b"FAKE DYLIB")


if __name__ == "__main__":
    unittest.main()
