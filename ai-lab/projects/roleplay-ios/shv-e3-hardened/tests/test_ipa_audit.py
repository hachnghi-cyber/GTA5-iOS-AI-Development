import unittest
from tools.audit_ipa_for_probe import macho_info
class MachoAuditTest(unittest.TestCase):
    def test_short_file(self):
        with self.assertRaises(ValueError):macho_info(b'\0'*8)
    def test_wrong_magic(self):
        with self.assertRaises(ValueError):macho_info(b'\0'*32)
