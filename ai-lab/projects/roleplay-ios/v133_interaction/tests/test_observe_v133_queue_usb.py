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
ENQUEUE = 0x101cc684c
BUFFERED = 0x101cc5cec
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
        fp = 0x150000000
        connection_fp, manager_fp, parent = fp+0x150, fp+0x700, fp+0x760
        connection, endpoint, channel = 0x164000000, 0x165000000, 7
        memory = {manager+0x2c0: manager+0x238, player_manager+0x128: chosen,
                  chosen+0x18: 71, chosen+0x38: 0, event+0x3c: 71,
                  event: 0x1028446b8, 0x1028446d0: 0x101d42a24, 0x10332b674: 4,
                  connection+0xb8: manager+0x238, connection+0x10: 71,
                  fp: struct.pack('<QQ', connection_fp, 0x101cc576c),
                  connection_fp: struct.pack('<QQ', manager_fp, 0x101cd6b14),
                  manager_fp: struct.pack('<QQ', parent, 0x101cd77ac),
                  fp-0x10: connection, connection_fp-0x20: connection,
                  connection_fp-0x28: endpoint, connection_fp-0x38: channel,
                  endpoint+8*channel: connection,
                  manager_fp-0x18: manager, parent-0x35: 1}
        stages = [
            ({32: ENQUEUE, 0: manager+0x238, 1: event, 20: connection,
              29: fp, 31: fp-0x60}, b'aaaa'),
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
                                 {'caller_observed': True, 'endpoint_connection_observed': True,
                                  'decrypt_indicator': 'set'})
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
                        ('Z', ENQUEUE), ('Z', BUFFERED), ('z', BUFFERED), ('z', ENQUEUE),
                        ('Z', DISPATCH), ('z', DISPATCH),
                        ('Z', PREDISPATCH), ('Z', caller), ('z', caller), ('z', PREDISPATCH))])

    def test_session_swap_requires_the_adjacent_store_in_the_same_invocation(self):
        for case in ('swap', 'unchanged', 'other_thread', 'aliased'):
            with self.subTest(case=case):
                pre, post = 0x10180443c, 0x101804440
                global_pointer, manager = 0x1031ef4e0, 0x130000000
                first, second, frame = 0x140000000, 0x141000000, 0x150000000
                stages = [
                    ({32: pre, 19: manager, 29: frame}, b'aaaa'),
                    ({32: post, 19: manager, 29: frame}, b'bbbb' if case == 'other_thread' else b'aaaa'),
                ]
                before = (first, first if case == 'aliased' else second)
                after = before if case == 'unchanged' else before[::-1]
                addr = manager+0x20

                class SwapRemote(Remote):
                    def memory(self, address, size):
                        if address == addr:
                            pair = before if self.snapshot[32] == pre else after
                            return struct.pack('<QQ', *pair)
                        return super().memory(address, size)

                remote = SwapRemote(stages, {global_pointer: manager})
                with patch.object(usb, 'verify_context_code'):
                    report = usb.capture_session_swap(remote, BASE, self.meta, 30)
                self.assertEqual(report['same_session_slots_swapped'], case == 'swap')
                self.assertFalse(report['session_generation_verified'])
                self.assertEqual(remote.breakpoints, set())
                self.assertNotIn(str(first), json.dumps(report))
                if case == 'aliased':
                    self.assertNotIn(f'Z1,{post:x},4'.encode(), remote.commands)

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
        for mismatch in ('none', 'frame', 'event', 'source', 'destination', 'return', 'ambiguous_session'):
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
                # Separate from progress bits. Use the two established predicates
                # and a peer table for the transition slot.
                manager, main, transition = 0x130000000, 0x140000000, 0x141000000
                global_pointer = 0x1031ef4e0
                vtable, info, peer = 0x142000000, 0x143000000, 0x144000000
                memory.update({
                    global_pointer: manager, manager+0x20: struct.pack('<QQ', main, transition),
                    main+0xb0: 2 if mismatch == 'ambiguous_session' else 0,
                    transition+0xb0: 3, source: vtable, vtable+0x38: 0x1018d92e8,
                    source+0xa0: info, info+0x1f0: 131, transition+0xba30: 1,
                    transition+0xb930: peer, peer: 71, peer+0x1d8: 131,
                })
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
                same_event = mismatch in ('none', 'ambiguous_session')
                self.assertEqual(report.get('same_queued_event_at_scripted_handler', False), same_event)
                if same_event:
                    candidate = report['scripted_session_candidate']
                    self.assertEqual(candidate['candidate_slot'],
                                     'ambiguous' if mismatch == 'ambiguous_session' else 'transition')
                    if mismatch == 'ambiguous_session':
                        self.assertNotIn('peer_table', candidate)
                        self.assertNotIn((transition+0xba30, 4), remote.reads)
                    else:
                        self.assertTrue(candidate['peer_table']['peer_map_consistent'])
                        self.assertFalse(candidate['peer_table']['authenticated_rage_sender_verified'])
                        self.assertFalse(candidate['peer_table']['session_generation_verified'])
                if mismatch == 'return':
                    self.assertEqual(report['scripted_receive_status'], 'returned_before_scripted_handler')
                elif not same_event:
                    self.assertFalse(report['scripted_receive']['network_receive_stack_confirmed'])
                    self.assertNotIn((global_pointer, 8), remote.reads)

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
        for reason in ('frame_offset', 'return_address', 'manager', 'saved_connection'):
            with self.subTest(reason=reason):
                stages, memory = self.fixture()
                fp = stages[0][0][29]
                if reason == 'frame_offset':
                    stages[0][0][31] -= 16
                elif reason == 'return_address':
                    memory[fp] = struct.pack('<QQ', fp+0x150, 0x101cc5770)
                elif reason == 'saved_connection':
                    memory[fp-0x10] += 8
                else:
                    memory[fp+0x700-0x18] += 8
                remote = Remote(stages, memory)
                report = self.capture(remote)
                self.assertTrue(report['queue_object_link_observed'])
                self.assertEqual(report['enqueue_transport'],
                                 {'caller_observed': False, 'endpoint_connection_observed': False,
                                  'decrypt_indicator': 'unobserved'})
                self.assertNotIn((fp+0x760-0x35, 1), remote.reads)

    def test_buffered_frame_never_inherits_the_current_packet_indicator(self):
        stages, memory = self.fixture()
        stages[0][0][32] = BUFFERED
        # No valid current packet frames are supplied for this buffered event.
        stages[0][0][29] = 0
        remote = Remote(stages, memory)
        report = self.capture(remote)
        self.assertTrue(report['queue_object_link_observed'])
        self.assertEqual(report['enqueue_origin'], 'buffered_frame')
        self.assertEqual(report['enqueue_transport'],
                         {'caller_observed': False, 'endpoint_connection_observed': False,
                          'decrypt_indicator': 'unobserved'})
        self.assertNotIn((0x150000000+0x760-0x35, 1), remote.reads)

    def test_endpoint_channel_bounds_and_missing_connection_do_not_attest_transport(self):
        for reason in ('null', 'unaligned', 'overflow', 'channel_16', 'channel_64bit',
                       'empty_channel', 'wrong_connection', 'read_failed'):
            with self.subTest(reason=reason):
                stages, memory = self.fixture()
                fp = stages[0][0][29]
                connection_fp = fp+0x150
                endpoint = memory[connection_fp-0x28]
                channel = memory[connection_fp-0x38]
                if reason in ('null', 'unaligned', 'overflow'):
                    memory[connection_fp-0x28] = {
                        'null': 0, 'unaligned': endpoint+1, 'overflow': (1 << 48)-8}[reason]
                elif reason.startswith('channel_'):
                    memory[connection_fp-0x38] = 16 if reason == 'channel_16' else (1 << 32)+channel
                elif reason != 'read_failed':
                    memory[endpoint+8*channel] = 0 if reason == 'empty_channel' else 0x166000000

                class FailingRemote(Remote):
                    def memory(self, address, size):
                        if reason == 'read_failed' and address == endpoint+8*channel:
                            raise usb.DebugProtocolError('unreadable endpoint')
                        return super().memory(address, size)

                remote = FailingRemote(stages, memory)
                report = self.capture(remote)
                self.assertEqual(report['enqueue_transport'], {
                    'caller_observed': True, 'endpoint_connection_observed': False,
                    'decrypt_indicator': 'unobserved'})
                self.assertTrue(report['queue_object_link_observed'])
                self.assertFalse(report['authenticated_rp_sender_verified'])
                self.assertNotIn((fp+0x760-0x35, 1), remote.reads)
                if reason in ('null', 'unaligned', 'overflow', 'channel_16', 'channel_64bit'):
                    self.assertNotIn((endpoint+8*channel, 8), remote.reads)

    def test_endpoint_channel_edges_and_aslr_are_read_without_emitting_identifiers(self):
        for channel in (0, 15):
            with self.subTest(channel=channel):
                stages, memory = self.fixture()
                fp = stages[0][0][29]
                endpoint = memory[fp+0x150-0x28]
                memory[fp+0x150-0x38] = channel
                memory[endpoint+8*channel] = stages[0][0][20]
                # Exercise the transport reader's return-PC checks with ASLR.
                slide = 0x12340000
                for frame in (fp, fp+0x150, fp+0x700):
                    parent, lr = struct.unpack('<QQ', memory[frame])
                    memory[frame] = struct.pack('<QQ', parent, lr+slide)
                remote = Remote(stages, memory)
                remote.snapshot = stages[0][0]
                result = usb.read_enqueue_transport(remote, BASE+slide, self.profile,
                                                    stages[0][0][0], 0x238, 'immediate_frame')
                self.assertTrue(result['endpoint_connection_observed'])
                self.assertEqual(result['decrypt_indicator'], 'set')
                for private_value in (endpoint, stages[0][0][20]):
                    self.assertNotIn(str(private_value), json.dumps(result))

    def test_wrong_event_class_type_or_connection_never_arms_dispatch(self):
        for reason in ('connection_error', 'getter', 'type', 'connection', 'queue'):
            with self.subTest(reason=reason):
                stages, memory = self.fixture()
                if reason == 'connection_error':
                    memory[stages[0][0][1]] = 0x1028448d0
                elif reason == 'getter':
                    memory[0x1028446d0] = 0x101d43098
                elif reason == 'type':
                    memory[0x10332b674] = 5
                elif reason == 'connection':
                    memory[stages[0][0][20]+0x10] += 1
                else:
                    memory[stages[0][0][20]+0xb8] += 8
                remote = Remote(stages[:1], memory)
                report = self.capture(remote)
                self.assertFalse(report['queue_object_link_observed'])
                self.assertEqual(report['queue_context_status'],
                                 'enqueue_connection_mismatch' if reason in ('connection', 'queue')
                                 else 'enqueue_event_type_mismatch')
                self.assertNotIn(f'Z1,{DISPATCH:x},4'.encode(), remote.commands)

    def test_obsolete_phase19_profile_is_rejected_before_breakpoints(self):
        old = dict(self.profile, version=1, enqueue_va='0x101cd70bc')
        remote = Remote([], {})
        with self.assertRaisesRegex(usb.DebugProtocolError, 'obsolete queue profile'):
            usb.capture_queue_context(remote, BASE, self.meta, old, 30)
        self.assertEqual(remote.commands, [])

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
