"""Read-only compatibility tests against user-supplied GTA V iOS v11.3 files."""
import json
import pathlib
import struct
import uuid
import unittest
import zipfile

from build_unsigned_ipa import LC_LOAD_DYLIB, load_commands, patch_executable

ROOT = pathlib.Path(__file__).resolve().parents[2]
IPA = ROOT / "upload" / "GTAV-v11.3(1).ipa"
LAYOUT = ROOT / "upload" / "GTA V touch layout(2).json"


@unittest.skipUnless(IPA.is_file() and LAYOUT.is_file(), "Original IPA and layout must be available")
class OriginalInputs(unittest.TestCase):
    def test_customtouch_load_command_preserves_original_game_code(self):
        executable = ROOT / "inspect_v113/Payload/GTAV.app/GTA5"
        if not executable.is_file():
            self.skipTest("Extract original IPA before Mach-O patch test")
        old = executable.read_bytes()
        patched = patch_executable(old)
        old_type, old_commands, old_end = load_commands(old)
        new_type, new_commands, new_end = load_commands(patched)
        self.assertEqual(old_type, new_type)
        self.assertEqual(len(new_commands), len(old_commands) + 1)
        self.assertEqual(new_commands[-1][0], LC_LOAD_DYLIB)
        self.assertEqual(new_commands[-1][1], old_end)
        self.assertGreater(new_end, old_end)
        self.assertEqual(len(patched), len(old))
        self.assertEqual(patched[new_end:], old[new_end:])

    def test_unknown_executable_fails_closed(self):
        executable = ROOT / "inspect_v113/Payload/GTAV.app/GTA5"
        if not executable.is_file():
            self.skipTest("Extract original IPA before Mach-O patch test")
        modified = bytearray(executable.read_bytes())
        modified[0x4000] ^= 1
        with self.assertRaisesRegex(ValueError, "differs from verified v11.3"):
            patch_executable(modified)

    def test_ipa_is_ios_arm64_with_original_touch_library(self):
        with zipfile.ZipFile(IPA) as zf:
            self.assertIsNone(zf.testzip())
            entries = set(zf.namelist())
            self.assertIn("Payload/GTAV.app/Frameworks/libgtacompat.dylib", entries)
            self.assertIn("Payload/GTAV.app/Frameworks/Menyoo.shv.dylib", entries)
            self.assertIn("Payload/GTAV.app/launcher_vi.json", entries)
            with zf.open("Payload/GTAV.app/GTA5") as executable:
                header = executable.read(32)
        # Little-endian Mach-O 64-bit, CPU_TYPE_ARM64 (0x0100000c).
        self.assertEqual(struct.unpack_from("<I", header, 0)[0], 0xFEEDFACF)
        self.assertEqual(struct.unpack_from("<I", header, 4)[0], 0x0100000C)

    def test_original_layout_and_menyoo_preserved(self):
        original = json.loads(LAYOUT.read_text(encoding="utf-8"))
        self.assertEqual(original["format"], "gtav-ios-touch-layout")
        self.assertEqual(original["version"], 1)
        self.assertIn("1.custom", original["controls"])
        self.assertIn("2.custom", original["controls"])
        self.assertEqual(original["custom"]["0"], "Menyoo")
        self.assertEqual(len(original["custom"]), 14)

    def test_v113_keyboard_bridge_is_correct_private_symbol(self):
        dylib = ROOT / "inspect_v113/Payload/GTAV.app/Frameworks/libgtacompat.dylib"
        if not dylib.is_file():
            self.skipTest("Extract original IPA before Mach-O symbol verification")
        content = dylib.read_bytes()
        self.assertEqual(struct.unpack_from("<I", content)[0], 0xFEEDFACF)
        count = struct.unpack_from("<I", content, 16)[0]
        offset = 32
        symbol_data = None
        image_uuid = None
        for _ in range(count):
            command, size = struct.unpack_from("<II", content, offset)
            if command == 0x1B:
                image_uuid = uuid.UUID(bytes=content[offset + 8:offset + 24])
            elif command == 0x2:
                symbol_data = struct.unpack_from("<4I", content, offset + 8)
            offset += size
        self.assertEqual(str(image_uuid).upper(), "07E7118E-C3A1-380E-9192-58BCF3D30DD7")
        self.assertIsNotNone(symbol_data)
        symoff, nsyms, stroff, strsize = symbol_data
        target = None
        for n in range(nsyms):
            string_offset, _, _, _, value = struct.unpack_from("<IBBHQ", content, symoff + 16 * n)
            if string_offset >= strsize:
                continue
            end = content.index(0, stroff + string_offset)
            symbol = content[stroff + string_offset:end]
            if symbol == b"__ZL7SendKeyhb":
                target = value
                break
        self.assertEqual(target, 0x152E3C)
        self.assertEqual(
            struct.unpack_from("<4I", content, target),
            (0xD10243FF, 0xA9074FF4, 0xA9087BFD, 0x910203FD),
        )


if __name__ == "__main__":
    unittest.main()
