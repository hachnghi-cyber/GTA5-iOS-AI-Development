"""Synthetic parser tests; real static assertions run only with private input."""
import importlib.util
import struct
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1]/'tools'/'inspect_v133_engine.py'
spec = importlib.util.spec_from_file_location('engine', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    b = bytearray(1024)
    struct.pack_into('<IiiIIIII', b, 0, 0xfeedfacf, 0x100000c, 0, 2, 3, 200, 0, 0)
    struct.pack_into('<II', b, 32, 0x1b, 24)
    b[40:56] = bytes(range(16))
    struct.pack_into('<II', b, 56, 0x19, 152)
    struct.pack_into('<I', b, 120, 1)
    struct.pack_into('<16s16sQQI', b, 128, b'__text', b'__TEXT', 0x100001000, 16, 512)
    struct.pack_into('<IIIIII', b, 208, 2, 24, 640, 1, 700, 100)
    struct.pack_into('<IBBHQ', b, 640, 1, 0xe, 1, 0, 0x100001000)
    name = m.SYMBOLS['sandbox_program'].encode()+b'\0'
    b[701:701+len(name)] = name
    return bytes(b)


class EngineTests(unittest.TestCase):
    def test_session_data_symbol_must_be_aligned_inside_common_storage(self):
        b = bytearray(2048)
        struct.pack_into('<IiiIIIII', b, 0, 0xfeedfacf, 0x100000c, 0, 2, 3, 280, 0, 0)
        struct.pack_into('<II', b, 32, 0x1b, 24)
        b[40:56] = bytes(range(16))
        struct.pack_into('<II', b, 56, 0x19, 232)
        struct.pack_into('<I', b, 120, 2)
        struct.pack_into('<16s16sQQI', b, 128, b'__text', b'__TEXT', 0x100001000, 16, 512)
        struct.pack_into('<16s16sQQI', b, 208, b'__common', b'__DATA', 0x1031ef4e0, 16, 0)
        struct.pack_into('<IIIIII', b, 288, 2, 24, 640, 1, 740, 200)
        struct.pack_into('<IBBHQ', b, 640, 1, 0xe, 2, 0, 0x1031ef4e0)
        name = m.DATA_SYMBOLS['network_session_global'].encode()+b'\0'
        b[741:741+len(name)] = name
        _, _, symbols = m.parse_image(bytes(b))
        self.assertEqual(symbols[m.DATA_SYMBOLS['network_session_global']], 0x1031ef4e0)
        for value in (0x1031ef4df, 0x1031ef4e4, 0x1031ef4f0):
            changed = bytearray(b)
            struct.pack_into('<Q', changed, 648, value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.parse_image(bytes(changed))
        changed = bytearray(b)
        changed[224:240] = b'__TEXT'.ljust(16, b'\0')
        with self.assertRaisesRegex(ValueError, 'expected storage'):
            m.parse_image(bytes(changed))

    def test_symbol_mapping_uses_section_vmaddr(self):
        u, text, syms = m.parse_image(fixture())
        self.assertEqual(text, (0x100001000,16,512))
        self.assertEqual(syms[m.SYMBOLS['sandbox_program']], 0x100001000)
        self.assertEqual(u, '00010203-0405-0607-0809-0A0B0C0D0E0F')

    def test_truncated_and_bad_command_bounds(self):
        for length in (0,31,60,220,700):
            with self.subTest(length=length), self.assertRaises(ValueError):
                m.parse_image(fixture()[:length])

    def test_bad_symbol_and_text_ranges(self):
        for at,value in ((640,100),(224,9999),(176,1016),(120,800)):
            b=bytearray(fixture()); struct.pack_into('<I',b,at,value)
            with self.subTest(at=at), self.assertRaises(ValueError):
                m.parse_image(bytes(b))

    def test_branch_direction_and_opcode(self):
        self.assertEqual(m.branch_target(0x1000,0x94000002),0x1008)
        self.assertEqual(m.branch_target(0x1000,0x17ffffff),0xffc)
        self.assertIsNone(m.branch_target(0x1000,0xd65f03c0))

    def test_synthetic_and_unknown_build_cannot_attest(self):
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            m.inspect(fixture())


if __name__ == '__main__':
    unittest.main()
