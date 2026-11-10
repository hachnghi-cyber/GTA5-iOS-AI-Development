import hashlib
import os
from pathlib import Path
import struct
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from install_unsigned import (  # noqa: E402
    ALLOWED_GAME_SHA,
    GAME,
    LC_LOAD_DYLIB,
    macho_header,
    patch_game,
)


class MachOPatchTests(unittest.TestCase):
    def test_rejects_random_binary(self):
        with self.assertRaises(ValueError):
            patch_game(b"not a game executable")

    def test_real_user_supplied_v113_if_available(self):
        path = os.environ.get("GTA_V11_3_IPA")
        if not path:
            self.skipTest("Set GTA_V11_3_IPA to locally supplied test IPA")
        with zipfile.ZipFile(path) as zf:
            original = zf.read(GAME)
        self.assertIn(hashlib.sha256(original).hexdigest(), ALLOWED_GAME_SHA)
        patched = patch_game(original)
        original_type, original_cmds, original_end = macho_header(original)
        patched_type, patched_cmds, patched_end = macho_header(patched)
        self.assertEqual(original_type, patched_type)
        self.assertEqual(len(patched_cmds), len(original_cmds) + 1)
        self.assertEqual(patched_cmds[-1][0], LC_LOAD_DYLIB)
        self.assertEqual(original[:16], patched[:16])
        self.assertEqual(original[24:original_end], patched[24:original_end])
        self.assertEqual(original[patched_end:], patched[patched_end:])
        self.assertEqual(len(original), len(patched))
        self.assertEqual(struct.unpack_from("<I", patched, 16)[0], len(patched_cmds))


if __name__ == "__main__":
    unittest.main()
