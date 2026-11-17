"""Debugger and memory fixtures only. Hardware behavior needs an iPhone."""
import importlib.util
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch


path = Path(__file__).resolve().parents[1] / 'tools' / 'observe_v133_windows_usb.py'
spec = importlib.util.spec_from_file_location('queue_usb', path)
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)

BASE = 0x100000000
ENQUEUE = 0x101cd70bc
DISPATCH = 0x101cdbe50
RETURN = 0x101cd9ec4
PREDISPATCH = 0x1020249a8


class Remote:
    def __init__(self, stages, memory, refuse=None):
        self.stages = iter(stages)
        self.memory_values = memory
        self.refuse = refuse
        self.breakpoints = set()
        self.commands = []
        self.reads = []
        self.conn = self

    def settimeout(self, seconds):
        if not 0 < seconds <= 60:
            raise AssertionError('invalid socket timeout')

    def sendall(self, wire):
        self.commands.append(wire)

    def send(self, wire):
        self.commands.append(wire)
        if wire != b'c':
            raise AssertionError('unexpected resume operation')

    def request(self, wire):
        self.commands.append(wire)
        if wire.startswith(b'qRegisterInfo'):
            reg = int(wire.removeprefix(b'qRegisterInfo'), 16)
            name = {29: 'fp', 30: 'lr', 31: 'sp', 32: 'pc'}.get(reg, f'x{reg}')
            return f'name:{name};bitsize:64;'.encode()
        if wire.startswith((b'Z1,', b'z1,')):
            address = int(wire.split(b',')[1], 16)
            if wire.startswith(b'z'):
                self.breakpoints.remove(address)
            elif address == self.refuse:
                return b'E01'
            else:
                self.breakpoints.add(address)
            return b'OK'
        if wire.startswith(b'Hg'):
            return b'OK'
        raise AssertionError('unexpected debugger operation')

    def receive(self):
        value = next(self.stages)
        if isinstance(value, Exception):
            raise value
        self.snapshot, thread = value
        return b'T05thread:' + thread + b';'

    def read_register(self, number):
        return self.snapshot[number]

    def memory(self, address, size):
        self.reads.append((address, size))
        value = self.memory_values[address]
        return value.to_bytes(size, 'little') if isinstance(value, int) else value


class QueueUSBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = json.loads(usb.BASELINE.read_text(encoding='utf-8'))
        cls.profile = json.loads(usb.QUEUE_BASELINE.read_text(encoding='utf-8'))['usb_profile']

    def fixture(self, caller=RETURN):
        manager, event = 0x160120000, 0x170340000
        player_manager, chosen, local = 0x180004000, 0x188800000, 0x190000000
        fp, parent = 0x150000000, 0x150000060
        memory = {manager+0x2c0: manager+0x238, player_manager+0x128: chosen,
                  chosen+0x18: 71, chosen+0x38: 0, event+0x3c: 71,
                  fp: struct.pack('<QQ', parent, 0x101cd77ac),
                  fp-0x18: manager, parent-0x35: 1}
        stages = [
            ({32: ENQUEUE, 0: manager+0x238, 1: event, 29: fp, 31: fp-0x5a0}, b'aaaa'),
            ({32: DISPATCH, 30: caller, 0: manager, 1: event, 21: manager+0x2c0,
              27: manager, 28: event}, b'bbbb'),
            ({32: PREDISPATCH, 19: player_manager, 20: event, 9: chosen, 10: local}, b'bbbb'),
        ]
        return stages, memory

    def capture(self, remote):
        with patch.object(usb, 'verify_context_code') as verify:
            report = usb.capture_queue_context(remote, BASE, self.meta, self.profile, 30)
            verify.assert_called_once_with(remote, BASE, self.profile, label='queue-context')
        self.assertEqual(remote.breakpoints, set())
        self.assertFalse(any(cmd.startswith((b'Z0,', b'M', b'P')) for cmd in remote.commands))
        return report

    def test_both_dispatch_returns_link_event_and_observe_engine_association(self):
        for caller in (RETURN, 0x101cd9fa0):
            with self.subTest(caller=caller):
                stages, memory = self.fixture(caller)
                remote = Remote(stages, memory)
                report = self.capture(remote)
                self.assertTrue(report['queue_object_link_observed'])
                self.assertTrue(report['dispatch_and_predispatch_same_thread'])
                self.assertEqual(report['enqueue_transport'],
                                 {'caller_observed': True, 'decrypt_indicator': 'set'})
                self.assertEqual(report['native_candidate']['status'], 'connection_candidate_only')
                for flag in ('authenticated_rp_sender_verified', 'session_generation_verified',
                             'game_thread_affinity_verified', 'custom_rp_event_received'):
                    self.assertFalse(report[flag])
                serialized = json.dumps(report)
                for regs, thread in stages:
                    self.assertNotIn(thread.decode(), serialized)
                    for value in regs.values():
                        self.assertNotIn(str(value), serialized)
                self.assertEqual(
                    [c for c in remote.commands if c.startswith((b'Z1,', b'z1,'))],
                    [f'{op}1,{addr:x},4'.encode() for op, addr in (
                        ('Z', ENQUEUE), ('z', ENQUEUE), ('Z', DISPATCH), ('z', DISPATCH),
                        ('Z', PREDISPATCH), ('Z', caller), ('z', caller), ('z', PREDISPATCH))])

    def test_unrelated_dispatch_or_consumer_never_arms_predispatch(self):
        for wrong in ('event', 'return', 'consumer_queue'):
            with self.subTest(wrong=wrong):
                stages, memory = self.fixture()
                if wrong == 'event':
                    stages[1][0][1] += 8
                elif wrong == 'return':
                    stages[1][0][30] += 4
                else:
                    memory[stages[1][0][21]] += 8
                remote = Remote(stages[:2], memory)
                report = self.capture(remote)
                self.assertFalse(report['queue_object_link_observed'])
                self.assertEqual(report['queue_context_status'],
                                 'consumer_queue_mismatch' if wrong == 'consumer_queue'
                                 else 'dispatch_event_mismatch')
                self.assertNotIn(f'Z1,{PREDISPATCH:x},4'.encode(), remote.commands)

    def test_scripted_followup_requires_same_frame_event_and_players(self):
        for mismatch in ('none', 'frame', 'event', 'source', 'destination', 'return'):
            with self.subTest(mismatch=mismatch):
                stages, memory = self.fixture()
                event = stages[0][0][1]
                source, destination = stages[2][0][9], stages[2][0][10]
                handler = int(self.meta['symbols']['script_event_handler']['va'], 16)
                delegate_return = 0x1020249bc
                fp = 0x150001000
                origin_fp = fp + 0x400
                stages[2][0][29] = origin_fp + (16 if mismatch == 'frame' else 0)
                refs = [0x10200c23c, 0x10200bf44, 0x10200a808, 0x102026194, delegate_return]
                for i, return_pc in enumerate(refs[1:]):
                    memory[fp + i*0x100] = struct.pack('<QQ', fp + (i+1)*0x100, return_pc)
                message = origin_fp - 0x60
                memory[message+0x10] = source + (8 if mismatch == 'source' else 0)
                memory[message+0x18] = destination + (8 if mismatch == 'destination' else 0)
                memory[fp+0x300-0x10] = event + (8 if mismatch == 'event' else 0)
                stages.append(({32: delegate_return if mismatch == 'return' else handler,
                                29: fp, 30: refs[0], 31: fp-0x180,
                                1: memory[message+0x10], 2: memory[message+0x18]}, b'bbbb'))
                remote = Remote(stages, memory)
                with patch.object(usb, 'verify_context_code'):
                    report = usb.capture_queue_context(remote, BASE, self.meta,
                                                       self.profile, 30, follow_scripted=True)
                self.assertEqual(remote.breakpoints, set())
                self.assertTrue(report['queue_object_link_observed'])
                self.assertFalse(report['authenticated_rp_sender_verified'])
                self.assertEqual(report.get('same_queued_event_at_scripted_handler', False),
                                 mismatch == 'none')
                if mismatch == 'return':
                    self.assertEqual(report['scripted_receive_status'], 'returned_before_scripted_handler')
                elif mismatch != 'none':
                    self.assertFalse(report['scripted_receive']['network_receive_stack_confirmed'])

    def test_dispatch_return_other_event_and_other_thread_do_not_link(self):
        for reason in ('returned_before_predispatch', 'event', 'thread'):
            with self.subTest(reason=reason):
                stages, memory = self.fixture()
                if reason.startswith('returned'):
                    stages[2][0][32] = RETURN
                elif reason == 'event':
                    stages[2][0][20] += 8
                else:
                    stages[2] = (stages[2][0], b'cccc')
                remote = Remote(stages, memory)
                report = self.capture(remote)
                self.assertFalse(report['queue_object_link_observed'])
                self.assertEqual(report['queue_context_status'],
                                 reason if reason.startswith('returned')
                                 else 'predispatch_event_or_thread_mismatch')
                self.assertNotIn('native_candidate', report)
                self.assertEqual(remote.reads[-1], (stages[1][0][21], 8))

    def test_indicator_is_never_read_from_an_unrelated_caller_or_manager(self):
        for reason in ('frame_offset', 'return_address', 'manager'):
            with self.subTest(reason=reason):
                stages, memory = self.fixture()
                fp = stages[0][0][29]
                if reason == 'frame_offset':
                    stages[0][0][31] -= 16
                elif reason == 'return_address':
                    memory[fp] = struct.pack('<QQ', fp+0x60, 0x101cd77b0)
                else:
                    memory[fp-0x18] += 8
                remote = Remote(stages, memory)
                report = self.capture(remote)
                self.assertTrue(report['queue_object_link_observed'])
                self.assertEqual(report['enqueue_transport'],
                                 {'caller_observed': False, 'decrypt_indicator': 'unobserved'})
                self.assertNotIn((fp+0x2b, 1), remote.reads)

    def test_timeout_interrupt_clears_both_final_breakpoints(self):
        stages, memory = self.fixture()
        stages.insert(2, TimeoutError())
        remote = Remote(stages, memory)
        report = self.capture(remote)
        self.assertEqual(report['queue_context_status'], 'timeout')
        self.assertFalse(report['queue_object_link_observed'])
        self.assertIn(bytes([3]), remote.commands)

    def test_refused_second_hardware_breakpoint_cleans_the_first(self):
        stages, memory = self.fixture()
        remote = Remote(stages[:2], memory, refuse=RETURN)
        with patch.object(usb, 'verify_context_code'), self.assertRaisesRegex(
                usb.DebugProtocolError, 'hardware breakpoint installation'):
            usb.capture_queue_context(remote, BASE, self.meta, self.profile, 30)
        self.assertEqual(remote.breakpoints, set())
        self.assertEqual(remote.commands[-1], f'z1,{PREDISPATCH:x},4'.encode())

    def test_modified_guard_refuses_before_any_breakpoint(self):
        guard = self.profile['code_guards'][0]
        start = int(guard['va'], 16)
        memory = {start+offset: bytes(min(1024, guard['size']-offset))
                  for offset in range(0, guard['size'], 1024)}
        remote = Remote([], memory)
        with self.assertRaisesRegex(usb.DebugProtocolError, 'queue-context live code mismatch'):
            usb.capture_queue_context(remote, BASE, self.meta, self.profile, 30)
        self.assertFalse(any(cmd.startswith(b'Z1,') for cmd in remote.commands))


if __name__ == '__main__':
    unittest.main()
