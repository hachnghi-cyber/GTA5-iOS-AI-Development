"""Synthetic transport fixtures for the Windows observer. No device evidence."""
import importlib.util
import hashlib
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "tools" / "observe_v133_windows_usb.py"
spec = importlib.util.spec_from_file_location("observer_usb", path)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class USBSelectionTests(unittest.TestCase):
    first = "01234567-0123456789ABCDEF"
    second = "89ABCDEF-0123456789ABCDEF"

    def test_single_cabled_device_even_with_wifi_entries(self):
        devices = [
            {"ConnectionType": "Network", "UniqueDeviceID": self.second},
            {"ConnectionType": "Network", "UniqueDeviceID": self.first},
            {"ConnectionType": "USB", "UniqueDeviceID": self.first},
        ]
        self.assertEqual(observer.select_usb_device(devices), self.first)
        with self.assertRaisesRegex(observer.DebugProtocolError, "not connected over USB"):
            observer.select_usb_device(devices, self.second)

    def test_two_cabled_devices_require_explicit_selection(self):
        devices = [{"ConnectionType": "USB", "UniqueDeviceID": value}
                   for value in (self.first, self.second)]
        with self.assertRaisesRegex(observer.DebugProtocolError, "multiple USB devices"):
            observer.select_usb_device(devices)
        self.assertEqual(observer.select_usb_device(devices, self.second.lower()), self.second)


class Connection:
    def __init__(self, *chunks):
        self.chunks = iter(chunks)
        self.sent = []

    def recv(self, _):
        return next(self.chunks, b"")

    def sendall(self, data):
        self.sent.append(data)


class DebugReplyTests(unittest.TestCase):
    def test_split_reply_preserves_next_frame(self):
        conn = Connection(b"+$O", b"K#9", b"a$#00")
        remote = observer.Remote(conn)
        self.assertEqual(remote.receive(), b"OK")
        self.assertEqual(remote.receive(), b"")
        self.assertEqual(conn.sent, [b"+", b"+"])

    def test_corrupt_or_oversized_reply_is_rejected(self):
        for frame in (b"$OK#00", b"$" + b"A" * (observer.MAX_REPLY + 1) + b"#00"):
            with self.subTest(length=len(frame)):
                conn = Connection(frame)
                with self.assertRaises(observer.DebugProtocolError):
                    observer.Remote(conn).receive()
                self.assertEqual(conn.sent, [])

    def test_non_stop_reply_cannot_supply_a_thread(self):
        self.assertIsNone(observer.stop_thread(b"OK"))
        self.assertIsNone(observer.stop_thread(b"T05name:Game;"))
        self.assertEqual(observer.stop_thread(b"T05thread:abcd;"), b"abcd")


class LocalStockJobTests(unittest.TestCase):
    def test_local_work_reads_only_index_and_shift_and_never_authorizes(self):
        profile = {'job_index_va': '0x1028925ac', 'on_shift_va': '0x10363fdd4',
                   'police_labels': ['cop_ls', 'cop_sandy', 'cop_paleto']}
        base = 0x110000000
        for index, shift, label, duty, valid in (
            (0, 1, 'cop_ls', True, True), (1, 1, 'cop_sandy', True, True),
            (2, 1, 'cop_paleto', True, True), (-1, 0, 'none', False, True),
            (0, 0, 'cop_ls', False, True), (2, 2, 'cop_paleto', False, False),
            (-2, 1, 'other', False, True), (3, 1, 'other', False, True),
        ):
            class Memory:
                def memory(self, address, size):
                    return {(base+0x28925ac, 4): struct.pack('<i', index),
                            (base+0x363fdd4, 1): bytes([shift])}[address, size]

            with self.subTest(index=index, shift=shift):
                result = observer.read_local_work(Memory(), base, profile)
                self.assertEqual(result['job'], label)
                self.assertEqual(result['on_shift'], shift == 1)
                self.assertEqual(result['shift_field_valid'], valid)
                self.assertEqual(result['local_police_duty_candidate'], duty)
                self.assertFalse(result['police_role_authorized'])

    def test_read_only_sample_does_not_report_unknown_job_ids_or_roles(self):
        fields = {"id_va": "0x100000100", "kind_va": "0x100000200", "state_va": "0x100000300"}
        base = 0x101000000

        class Memory:
            def __init__(self, value):
                self.values = {base+0x100: value.ljust(40, b"\0"),
                               base+0x200: (4).to_bytes(4, "little"),
                               base+0x300: (1).to_bytes(4, "little")}

            def memory(self, address, size):
                assert len(self.values[address]) == size
                return self.values[address]

        candidate = observer.read_stock_job(Memory(b"cop_ls"), base, fields)
        self.assertTrue(candidate["job_id_is_cop_ls"])
        self.assertFalse(candidate["police_role_authorized"])
        unknown = observer.read_stock_job(Memory(b"unrelated_job"), base, fields)
        self.assertFalse(unknown["job_id_known"])
        self.assertNotIn("unrelated_job", str(unknown))


class _BreakConn:
    def __init__(self):
        self.timeouts = []
        self.sent = []

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def sendall(self, data):
        self.sent.append(data)


class _BreakRemote:
    def __init__(self, pc, lr=0, time_out=False):
        self.conn = _BreakConn()
        self.pc = pc
        self.lr = lr
        self.time_out = time_out
        self.sent = []
        self.requests = []
        self.register_reads = []

    def request(self, packet):
        self.requests.append(packet)
        if packet == b"qRegisterInfo20":
            return b"name:pc;bitsize:64;"
        if packet == b"qRegisterInfo1e":
            return b"name:lr;bitsize:64;"
        if packet in (b'qRegisterInfo1d', b'qRegisterInfo1f', b'qRegisterInfo1', b'qRegisterInfo2'):
            return {b'qRegisterInfo1d': b'name:fp;', b'qRegisterInfo1f': b'name:sp;',
                    b'qRegisterInfo1': b'name:x1;', b'qRegisterInfo2': b'name:x2;'}[packet]
        if packet.startswith((b"Z1,", b"z1,", b"Hg")):
            return b"OK"
        raise AssertionError("unexpected debugger packet")

    def send(self, packet):
        self.sent.append(packet)

    def receive(self):
        if self.time_out:
            self.time_out = False
            raise TimeoutError()
        return b"T05thread:abcd;"

    def read_register(self, number):
        self.register_reads.append(number)
        return {32: self.pc, 30: self.lr}[number]


class ScriptEventObserverTests(unittest.TestCase):
    def setUp(self):
        self.base = 0x102000000
        self.va = "0x100012340"
        self.pc = self.base + int(self.va, 16) - observer.IMAGE_VMADDR
        self.metadata = {"symbols": {"script_event_handler": {"va": self.va}}, "branches": []}

    def test_read_only_script_handler_hit_never_claims_authenticated_event(self):
        remote = _BreakRemote(self.pc)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler", wait_seconds=30)
        self.assertEqual(sample["site"], "script_event_handler")
        self.assertTrue(sample["hardware_stop_at_expected_pc"])
        for key in ("network_receive_stack_confirmed", "authenticated_rp_sender_verified",
                    "session_generation_verified", "custom_rp_event_received"):
            self.assertIs(sample[key], False)
        self.assertEqual(sample["observed_path"], "undetermined")
        self.assertFalse(sample["macport_online_update_callsite_matches"])
        self.assertFalse(sample['network_receive_call_chain_observed'])
        self.assertFalse(sample['game_thread_affinity_verified'])
        self.assertEqual(sample['thread_label_scope'], 'anonymous_single_capture_only')
        self.assertEqual(remote.sent, [b"c"])
        self.assertEqual(remote.conn.timeouts, [30])
        self.assertEqual(remote.register_reads, [32])
        self.assertEqual(remote.requests[-1], f"z1,{self.pc:x},4".encode())
        self.assertFalse(any(request.startswith(b"Z0,") for request in remote.requests))

    def test_script_site_with_unexpected_pc_does_not_report_hit(self):
        remote = _BreakRemote(self.pc + 4)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler")
        self.assertFalse(sample["hardware_stop_at_expected_pc"])

    def test_clear_session_observes_entry_without_inspecting_arguments(self):
        remote = _BreakRemote(self.pc)
        metadata = {"symbols": {"clear_session": {"va": self.va}}}
        sample = observer.capture(remote, self.base, metadata, site="clear_session")
        self.assertTrue(sample["hardware_stop_at_expected_pc"])
        self.assertFalse(sample["session_generation_verified"])
        self.assertFalse(sample["authenticated_rp_sender_verified"])
        self.assertEqual(remote.register_reads, [32])
        self.assertEqual(remote.requests[-1], f"z1,{self.pc:x},4".encode())

    def test_other_stop_signal_at_same_pc_does_not_report_breakpoint_hit(self):
        remote = _BreakRemote(self.pc)
        with patch.object(remote, 'receive', return_value=b'T0bthread:abcd;'):
            sample = observer.capture(remote, self.base, self.metadata, site='script_event_handler')
        self.assertFalse(sample['hardware_stop_at_expected_pc'])

    def test_timeout_is_not_a_breakpoint_hit_even_if_pc_matches(self):
        remote = _BreakRemote(self.pc, time_out=True)
        sample = observer.capture(remote, self.base, self.metadata,
                                  site="script_event_handler")
        self.assertTrue(sample["timed_out"])
        self.assertFalse(sample["hardware_stop_at_expected_pc"])
        self.assertEqual(remote.conn.sent, [bytes([3])])
        self.assertTrue(remote.requests[-1].startswith(b"z1,"))

    def test_reject_unsupported_site_stock_job_and_unbounded_wait(self):
        for kwargs in ({"site": "unverified_hook"},
                       {'site': 'jobs_update', 'receive_context': True},
                       {"site": "script_event_handler", "stock_job": True},
                       {"site": "script_event_handler", "wait_seconds": 0},
                       {"site": "script_event_handler", "wait_seconds": 61}):
            with self.subTest(kwargs=kwargs):
                remote = _BreakRemote(self.pc)
                with self.assertRaises(ValueError):
                    observer.capture(remote, self.base, self.metadata, **kwargs)
                self.assertEqual(remote.sent, [])
                self.assertEqual(remote.requests, [])

    def test_context_memory_error_still_removes_hardware_breakpoint(self):
        remote = _BreakRemote(self.pc)
        self.metadata['receive_context'] = {}
        with patch.object(observer, 'verify_context_code'), \
                patch.object(observer, 'read_receive_context',
                             side_effect=observer.DebugProtocolError('unreadable memory')):
            with self.assertRaisesRegex(observer.DebugProtocolError, 'unreadable memory'):
                observer.capture(remote, self.base, self.metadata,
                                 site='script_event_handler', receive_context=True)
        self.assertTrue(remote.requests[-1].startswith(b'z1,'))
        self.assertFalse(any(request.startswith((b'M', b'P', b'Z0,')) for request in remote.requests))

    def test_context_is_not_read_after_timeout_or_wrong_pc(self):
        for remote in (_BreakRemote(self.pc, time_out=True), _BreakRemote(self.pc + 4)):
            self.metadata['receive_context'] = {}
            with patch.object(observer, 'verify_context_code'), \
                    patch.object(observer, 'read_receive_context') as read:
                sample = observer.capture(remote, self.base, self.metadata,
                                          site='script_event_handler', receive_context=True)
                read.assert_not_called()
            self.assertFalse(sample['network_receive_stack_confirmed'])


class SessionContextTests(unittest.TestCase):
    def setUp(self):
        self.base = 0x100000000
        self.profile = {'global_pointer_va': '0x1031ef4e0',
                        'main_in_progress_offset': 0x180d6,
                        'transition_in_progress_offset': 0x1821e}

    def memory(self, pointer=0x170000000, main=0x81, transition=0x80):
        class Memory:
            def __init__(inner):
                inner.reads = []

            def memory(inner, address, size):
                inner.reads.append((address, size))
                # Independent fixed layout from disassembly, not generated from profile.
                if (address, size) == (0x1031ef4e0, 8):
                    return struct.pack('<Q', pointer)
                return {(0x1700180d6, 1): bytes([main]),
                        (0x17001821e, 1): bytes([transition])}[(address, size)]
        return Memory()

    def test_observation_masks_native_bit_without_emitting_pointer_or_authority(self):
        remote = self.memory()
        sample = observer.read_session_context(remote, self.base, self.profile)
        self.assertEqual(sample['session_context_status'], 'observed')
        self.assertTrue(sample['native_main_session_in_progress'])
        self.assertFalse(sample['native_transition_session_in_progress'])
        self.assertFalse(sample['session_identity_verified'])
        self.assertFalse(sample['session_generation_verified'])
        self.assertEqual(remote.reads, [(0x1031ef4e0, 8), (0x1700180d6, 1), (0x17001821e, 1)])
        self.assertTrue(all(isinstance(v, bool) for k, v in sample.items() if k != 'session_context_status'))

    def test_transition_and_main_are_distinct(self):
        sample = observer.read_session_context(self.memory(main=2, transition=3), self.base, self.profile)
        self.assertFalse(sample['native_main_session_in_progress'])
        self.assertTrue(sample['native_transition_session_in_progress'])

    def test_null_misaligned_pac_or_overflow_pointer_is_never_dereferenced(self):
        for pointer in (0, 0x170000001, 1 << 60, (1 << 48)-8):
            with self.subTest(pointer=pointer):
                remote = self.memory(pointer=pointer)
                sample = observer.read_session_context(remote, self.base, self.profile)
                self.assertNotEqual(sample['session_context_status'], 'observed')
                self.assertEqual(remote.reads, [(0x1031ef4e0, 8)])
                self.assertNotIn('native_main_session_in_progress', sample)

    def test_unknown_offsets_fail_before_object_read(self):
        self.profile['main_in_progress_offset'] = 8
        remote = self.memory()
        with self.assertRaisesRegex(observer.DebugProtocolError, 'offset profile mismatch'):
            observer.read_session_context(remote, self.base, self.profile)
        self.assertEqual(len(remote.reads), 1)

    def metadata(self):
        return {'symbols': {'jobs_update': {'va': '0x1000eb57c'}},
                'branches': [{'source': 'online_update', 'target': 'jobs_update', 'at': '0x1000e66e0'}],
                'session_context': self.profile}

    def test_session_read_requires_hit_and_exact_game_loop_caller(self):
        for remote in (_BreakRemote(0x1000eb57c, lr=0),
                       _BreakRemote(0x1000eb580, lr=0x1000e66e4),
                       _BreakRemote(0x1000eb57c, lr=0x1000e66e4, time_out=True)):
            with patch.object(observer, 'verify_context_code'), \
                    patch.object(observer, 'read_session_context') as read:
                observer.capture(remote, self.base, self.metadata(), session_context=True)
                read.assert_not_called()
            self.assertTrue(remote.requests[-1].startswith(b'z1,'))

    def test_live_code_mismatch_prevents_breakpoint_and_data_read(self):
        remote = _BreakRemote(0x1000eb57c, lr=0x1000e66e4)
        with patch.object(observer, 'verify_context_code', side_effect=observer.DebugProtocolError('mismatch')), \
                patch.object(observer, 'read_session_context') as read:
            with self.assertRaises(observer.DebugProtocolError):
                observer.capture(remote, self.base, self.metadata(), session_context=True)
            read.assert_not_called()
        self.assertFalse(any(p.startswith((b'Z', b'z')) for p in remote.requests))

    def test_session_memory_failure_still_clears_hardware_breakpoint(self):
        remote = _BreakRemote(0x1000eb57c, lr=0x1000e66e4)
        with patch.object(observer, 'verify_context_code'), \
                patch.object(observer, 'read_session_context', side_effect=observer.DebugProtocolError('read failed')):
            with self.assertRaisesRegex(observer.DebugProtocolError, 'read failed'):
                observer.capture(remote, self.base, self.metadata(), session_context=True)
        self.assertTrue(remote.requests[-1].startswith(b'z1,'))

    def test_non_game_loop_site_rejects_session_mode_before_any_io(self):
        remote = _BreakRemote(0)
        with self.assertRaises(ValueError):
            observer.capture(remote, self.base, {}, site='on_net_event', session_context=True)
        self.assertEqual(remote.requests, [])


class _ContextMemory:
    """Golden synthetic stack from independently disassembled call/frame sites.

    Literal layout here intentionally does not generate a stack from the
    observer's profile. It represents the instant BEFORE handler's prologue.
    """
    base = 0x100000000
    sp = 0x160000000
    source = 0x170001000
    destination = 0x170002000
    event = 0x170003000

    def __init__(self, local=False):
        self.frames = [self.sp + delta for delta in (0x1090, 0x14d0, 0x1530, 0x1580, 0x15f0)]
        self.regs = {31: self.sp, 29: self.frames[0], 30: 0x10200c23c,
                     1: self.source, 2: self.destination}
        self.reads = []
        origin_lr = 0x101ffeed0 if local else 0x1020249bc
        self.data = {self.frames[i]: struct.pack('<QQ', self.frames[i+1], lr)
                     for i, lr in enumerate((0x10200bf44, 0x10200a808, 0x102026194, origin_lr))}
        message = self.frames[4] - (0x68 if local else 0x60)
        self.data[message + 0x10] = struct.pack('<Q', self.source)
        self.data[message + 0x18] = struct.pack('<Q', self.destination)
        self.data[self.frames[3] - 0x10] = struct.pack('<Q', self.event)
        self.data[self.event + 0x3c] = struct.pack('<i', 19)
        self.data[self.source + 0x18] = struct.pack('<i', 19)

    def read_register(self, number):
        return self.regs[number]

    def memory(self, address, size):
        self.reads.append((address, size))
        data = self.data[address]
        assert len(data) == size
        return data


class ReceiveContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads(observer.BASELINE.read_text(encoding='utf-8'))['receive_context']

    def sample(self, memory):
        return observer.read_receive_context(memory, memory.base, self.profile)

    def test_receive_chain_matches_source_but_not_authentication(self):
        memory = _ContextMemory()
        sample = self.sample(memory)
        self.assertEqual(sample['context_status'], 'observed')
        self.assertEqual(sample['observed_path'], 'engine_receive_dispatch')
        self.assertTrue(sample['network_receive_call_chain_observed'])
        self.assertTrue(sample['network_receive_stack_confirmed'])
        self.assertTrue(sample['engine_source_association_observed'])
        self.assertTrue(sample['connection_id_matches_source'])
        self.assertEqual(sample['matched_frames'],
                         ['process_events', 'packed_events', 'on_message', 'dispatch'])
        self.assertFalse(any('authentic' in key or 'session' in key for key in sample))
        for private_value in (memory.source, memory.destination, memory.event, memory.sp):
            self.assertNotIn(str(private_value), json.dumps(sample))
            self.assertNotIn(hex(private_value), json.dumps(sample))

    def test_full_capture_keeps_all_auth_and_gameplay_gates_false(self):
        metadata = json.loads(observer.BASELINE.read_text(encoding='utf-8'))
        memory = _ContextMemory()
        pc = int(metadata['symbols']['script_event_handler']['va'], 16)
        memory.regs[32] = pc
        remote = _BreakRemote(pc)
        remote.memory = memory.memory
        remote.read_register = memory.read_register
        with patch.object(observer, 'verify_context_code'):
            sample = observer.capture(remote, memory.base, metadata,
                                      site='script_event_handler', receive_context=True)
        self.assertTrue(sample['engine_source_association_observed'])
        for field in ('authenticated_rp_sender_verified', 'session_generation_verified',
                      'custom_rp_event_received'):
            self.assertIs(sample[field], False)
        self.assertTrue(remote.requests[-1].startswith(b'z1,'))

    def test_local_dispatch_cannot_claim_network_receive(self):
        memory = _ContextMemory(local=True)
        sample = self.sample(memory)
        self.assertEqual(sample['context_status'], 'observed')
        self.assertEqual(sample['observed_path'], 'local_sendbuffer_dispatch')
        self.assertFalse(sample['network_receive_call_chain_observed'])
        self.assertFalse(sample['network_receive_stack_confirmed'])
        self.assertFalse(sample['engine_source_association_observed'])
        self.assertFalse(any(address >= memory.source for address, _ in memory.reads))

    def test_source_or_destination_mismatch_rejects_association_before_dereference(self):
        for reg in (1, 2):
            memory = _ContextMemory()
            memory.regs[reg] += 8
            sample = self.sample(memory)
            self.assertEqual(sample['context_status'], 'handler_reference_mismatch')
            self.assertTrue(sample['network_receive_call_chain_observed'])
            self.assertFalse(sample['network_receive_stack_confirmed'])
            self.assertFalse(sample['engine_source_association_observed'])
            self.assertFalse(any(address >= memory.source for address, _ in memory.reads))

    def test_negative_or_mismatched_connection_is_not_associated(self):
        for connection in (-1, 20):
            memory = _ContextMemory()
            memory.data[memory.event + 0x3c] = struct.pack('<i', connection)
            sample = self.sample(memory)
            self.assertEqual(sample['context_status'], 'connection_mismatch')
            self.assertTrue(sample['network_receive_call_chain_observed'])
            self.assertFalse(sample['network_receive_stack_confirmed'])
            self.assertFalse(sample['engine_source_association_observed'])

    def test_unknown_callsite_or_pac_bits_are_not_stripped(self):
        for lr in (0x10200c240, 0xdead00010200c23c):
            memory = _ContextMemory()
            memory.regs[30] = lr
            sample = self.sample(memory)
            self.assertEqual(sample['context_status'], 'frame_or_callsite_mismatch')
            self.assertFalse(sample['network_receive_stack_confirmed'])
            self.assertEqual(memory.reads, [])

    def test_cycle_unaligned_and_out_of_bounds_frames_fail_without_scan(self):
        for delta in (0, -16, 1, 65536):
            memory = _ContextMemory()
            memory.data[memory.frames[0]] = struct.pack('<QQ', memory.frames[0] + delta, 0x10200bf44)
            sample = self.sample(memory)
            self.assertEqual(sample['context_status'], 'invalid_frame_chain')
            self.assertFalse(sample['network_receive_stack_confirmed'])
            self.assertEqual(len(memory.reads), 1)

    def test_null_source_and_invalid_event_pointer_are_rejected(self):
        for field in ('source', 'event'):
            memory = _ContextMemory()
            address = memory.frames[4] - 0x50 if field == 'source' else memory.frames[3] - 0x10
            memory.data[address] = bytes(8)
            sample = self.sample(memory)
            self.assertTrue(sample['network_receive_call_chain_observed'])
            self.assertFalse(sample['network_receive_stack_confirmed'])
            self.assertFalse(sample['engine_source_association_observed'])
            self.assertIn(sample['context_status'], ('handler_reference_mismatch', 'invalid_event_pointer'))

    def test_unknown_origin_never_classifies_as_receive(self):
        memory = _ContextMemory()
        memory.data[memory.frames[3]] = struct.pack('<QQ', memory.frames[4], 0x1020249c0)
        sample = self.sample(memory)
        self.assertEqual(sample['context_status'], 'unrecognized_dispatch_origin')
        self.assertFalse(sample['network_receive_call_chain_observed'])
        self.assertFalse(sample['network_receive_stack_confirmed'])

    def test_changed_function_code_is_rejected_before_observation(self):
        code = bytes.fromhex('fd7b04a9fd030191')
        profile = {'code_guards': [{'va': '0x100001000', 'size': len(code),
                                    'sha256': hashlib.sha256(code).hexdigest()}]}

        class Memory:
            def memory(self, address, size):
                self.assertion = (address, size)
                return code

        memory = Memory()
        observer.verify_context_code(memory, 0x100000000, profile)
        self.assertEqual(memory.assertion, (0x100001000, 8))
        code = bytes(8)
        with self.assertRaisesRegex(observer.DebugProtocolError, 'live code mismatch'):
            observer.verify_context_code(memory, 0x100000000, profile)
