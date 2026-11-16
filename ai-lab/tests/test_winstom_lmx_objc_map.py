"""Synthetic tests only: Winstom proprietary binary is never stored in GitHub."""
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "winstom_lmx_objc_map.py"
spec = importlib.util.spec_from_file_location("winstom_lmx_objc_map", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class WinstomLmxMapperTest(unittest.TestCase):
    def test_version_profiles_do_not_reuse_offsets(self):
        old = m.select_profile(m.EXPECTED_LMX_SHA256)
        new = m.select_profile('206037a1eaeea734e44886e050558421d1df965c8fd4bd3c078c317ca300906a')
        self.assertEqual(old[0], '0.7.171')
        self.assertEqual(new[0], '0.7.177')
        self.assertNotEqual(old[1:], new[1:])
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            m.select_profile('0'*64)

    def test_64_offset_rebase(self):
        self.assertEqual(m.decode_rebase(0x1000000040B208), 0x40B208)
        self.assertEqual(m.decode_rebase(0x100000003CE6A4), 0x3CE6A4)
        self.assertIsNone(m.decode_rebase(0x801000000000021F))
        self.assertIsNone(m.decode_rebase(0))

    def test_truncated_and_non_macho_rejected(self):
        with self.assertRaises(ValueError):
            m.resolve(b"not MachO")

    def test_refuses_unrecognized_large_binary(self):
        invalid = b"\xcf\xfa\xed\xfe" + b"\x00" * 0x410000
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            m.resolve(invalid)


if __name__ == "__main__":
    unittest.main()
