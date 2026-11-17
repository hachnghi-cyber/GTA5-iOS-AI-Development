"""Synthetic control-flow mutations; no game code, keys or runtime claims."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_v133_event_queue import AuditError, require_dominating_gate

NOP, RET = 0xd503201f, 0xd65f03c0


class IntegrityFlowTests(unittest.TestCase):
    def test_conditional_failure_exit_cannot_bypass_gate_to_success(self):
        # Each conditional may fail directly to RET or continue through gate.
        for opcode in (0x54000060, 0x34000060, 0xb5000060, 0x36000060, 0xb7000060):
            with self.subTest(opcode=hex(opcode)):
                words = {0x1000: NOP, 0x1004: opcode, 0x1008: NOP,
                         0x100c: NOP, 0x1010: RET}
                require_dominating_gate(words, 0x1000, 0x1008, (0x100c,))
                # Change only the branch destination: failure now reaches the
                # success block without traversing the required integrity gate.
                words[0x1004] -= 1 << 5
                with self.assertRaisesRegex(AuditError, 'does not dominate'):
                    require_dominating_gate(words, 0x1000, 0x1008, (0x100c,))

    def test_direct_branch_bypass_is_rejected(self):
        words = {0x1000: 0x14000003, 0x1004: NOP, 0x1008: NOP, 0x100c: RET}
        with self.assertRaisesRegex(AuditError, 'does not dominate'):
            require_dominating_gate(words, 0x1000, 0x1008, (0x100c,))

    def test_backward_loop_terminates_and_calls_only_model_return(self):
        words = {0x1000: 0x94004000, 0x1004: NOP, 0x1008: 0x35ffffe0, 0x100c: RET}
        require_dominating_gate(words, 0x1000, 0x1004, (0x100c,))

    def test_unreachable_success_is_not_a_vacuous_proof(self):
        words = {0x1000: RET, 0x1004: NOP, 0x1008: RET}
        with self.assertRaisesRegex(AuditError, 'does not dominate'):
            require_dominating_gate(words, 0x1000, 0x1004, (0x1008,))

    def test_unknown_indirect_and_external_branch_fail_closed(self):
        for opcode in (0xd61f0000, 0xd63f0000, 0x140000ff):
            with self.subTest(opcode=hex(opcode)), self.assertRaises(AuditError):
                require_dominating_gate({0x1000: opcode, 0x1004: NOP, 0x1008: RET},
                                        0x1000, 0x1004, (0x1008,))


if __name__ == '__main__':
    unittest.main()
