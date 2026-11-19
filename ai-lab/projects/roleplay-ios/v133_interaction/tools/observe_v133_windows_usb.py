"""Bounded one-site observer for an authorized, development-signed v13.3 iPhone.

Run with Python 3.13 and pymobiledevice3 11.56.0 in a controlled Sandbox
or a private GTA session. This tool uses a loopback Apple debugproxy connection.
It can briefly pause GTA and never falls back to a software breakpoint.
"""
import argparse
import hashlib
import json
import re
import socket
import struct
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[2] / "baselines" / "phase9-v133-engine.json"
QUEUE_BASELINE = BASELINE.with_name("phase19-v133-event-queue.json")
UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
IMAGE_VMADDR = 0x100000000
DEFAULT_SITE = "jobs_update"
OBSERVABLE_SITES = ("jobs_update", "script_event_handler", "script_decide", "on_net_event",
                    "on_net_event_pre_dispatch", "on_connection_peer_verify",
                    "clear_session", "session_swap")
MAX_REPLY = 16384


class DebugProtocolError(RuntimeError):
    pass


class Remote:
    def __init__(self, conn):
        self.conn = conn
        self.buffer = bytearray()

    def _fill(self):
        chunk = self.conn.recv(4096)
        if not chunk:
            raise DebugProtocolError("debugproxy disconnected")
        self.buffer.extend(chunk)

    def send(self, request):
        self.conn.sendall(b"$" + request + b"#" + f"{sum(request) & 255:02x}".encode())

    def receive(self):
        while True:
            while not self.buffer:
                self._fill()
            ack = self.buffer[0]
            if ack == ord("$"):
                break
            del self.buffer[0]
            if ack != ord("+"):
                raise DebugProtocolError("unexpected debugproxy reply prefix")
        while (end := self.buffer.find(b"#", 1)) < 0:
            if len(self.buffer) > MAX_REPLY:
                raise DebugProtocolError("oversized debugproxy reply")
            self._fill()
        if end > MAX_REPLY:
            raise DebugProtocolError("oversized debugproxy reply")
        while len(self.buffer) < end + 3:
            self._fill()
        reply = bytes(self.buffer[1:end])
        try:
            checksum = int(self.buffer[end+1:end+3], 16)
        except ValueError as exc:
            raise DebugProtocolError("invalid debugproxy checksum") from exc
        del self.buffer[:end+3]
        if checksum != sum(reply) & 255:
            raise DebugProtocolError("incorrect debugproxy checksum")
        self.conn.sendall(b"+")
        return reply

    def request(self, request):
        self.send(request)
        return self.receive()

    def memory(self, address, size):
        if address <= 0 or not 1 <= size <= 1024:
            raise ValueError("memory read outside observer bounds")
        data = self.request(f"m{address:x},{size:x}".encode())
        if len(data) != size * 2 or not re.fullmatch(rb"[0-9a-fA-F]+", data):
            raise DebugProtocolError("unexpected memory reply")
        return bytes.fromhex(data.decode())

    def read_register(self, index):
        reply = self.request(f"p{index:x}".encode())
        if not re.fullmatch(rb"[0-9a-fA-F]{16}", reply):
            raise DebugProtocolError("expected a 64-bit ARM64 register")
        return int.from_bytes(bytes.fromhex(reply.decode()), "little")


def main_image(remote):
    info_addr = remote.request(b"qShlibInfoAddr")
    if not re.fullmatch(rb"[0-9a-fA-F]{1,16}", info_addr):
        raise DebugProtocolError("dyld image address unavailable")
    version, count, listing = struct.unpack("<IIQ", remote.memory(int(info_addr, 16), 16))
    if not 1 <= version <= 64 or not 1 <= count <= 4096 or not listing:
        raise DebugProtocolError("unexpected dyld image info")
    entries = remote.memory(listing, 24 * min(4, count))
    for base, _, _ in struct.iter_unpack("<QQQ", entries):
        if not base:
            continue
        header = remote.memory(base, 32)
        magic, cpu, _, kind, ncmds, size, _, _ = struct.unpack("<8I", header)
        if (magic, cpu, kind) != (0xfeedfacf, 0x0100000c, 2):
            continue
        if not 1 <= ncmds <= 256 or not 8 <= size <= 16384:
            raise DebugProtocolError("unexpected Mach-O command bounds")
        commands = b"".join(remote.memory(base+32+offset, min(1024, size-offset))
                            for offset in range(0, size, 1024))
        offset = 0
        for _ in range(ncmds):
            if offset + 8 > size:
                break
            command, length = struct.unpack_from("<II", commands, offset)
            if length < 8 or offset + length > size:
                break
            if command == 0x1b and length == 24:
                live_uuid = uuid.UUID(bytes=commands[offset+8:offset+24])
                if str(live_uuid).upper() != UUID:
                    raise DebugProtocolError("live UUID mismatch")
                return base
            offset += length
        raise DebugProtocolError("main image UUID unavailable")
    raise DebugProtocolError("ARM64 executable not found")


def require_ok(remote, request, action):
    if remote.request(request) != b"OK":
        raise DebugProtocolError("device did not confirm " + action)


def stop_thread(reply):
    if not re.match(rb"^T[0-9a-fA-F]{2}", reply):
        return None
    match = re.search(rb"(?:^T[0-9a-fA-F]{2}|;)thread:([0-9a-fA-F]+);", reply)
    return match[1] if match else None


def read_stock_job(remote, base, sample):
    def read(field, size):
        return remote.memory(base + int(sample[field], 16) - IMAGE_VMADDR, size)
    raw_id = read("id_va", 40)
    job_id, sep, _ = raw_id.partition(b"\0")
    return {
        "job_id_known": bool(sep) and job_id in (b"", b"cop_ls"),
        "job_id_is_cop_ls": bool(sep) and job_id == b"cop_ls",
        "stock_job_kind": struct.unpack("<i", read("kind_va", 4))[0],
        "stock_job_state": struct.unpack("<i", read("state_va", 4))[0],
        "police_role_authorized": False,
    }


def read_local_work(remote, base, profile):
    index, = struct.unpack('<i', remote.memory(base + int(profile['job_index_va'], 16) - IMAGE_VMADDR, 4))
    shift, = remote.memory(base + int(profile['on_shift_va'], 16) - IMAGE_VMADDR, 1)
    labels = profile['police_labels']
    police = 0 <= index < len(labels)
    return {'job': labels[index] if police else ('none' if index == -1 else 'other'),
            'shift_field_valid': shift in (0, 1), 'on_shift': shift == 1,
            'local_police_duty_candidate': police and shift == 1,
            'police_role_authorized': False}


def verify_context_code(remote, base, profile, label='receive-context'):
    """Guard full functions, including every prologue and tail-call path."""
    if not profile['code_guards']:
        raise DebugProtocolError('missing ' + label + ' code guards')
    for guard in profile['code_guards']:
        size = guard['size']
        if not 4 <= size <= 4096 or size % 4:
            raise DebugProtocolError('invalid ' + label + ' code bounds')
        address = base + int(guard['va'], 16) - IMAGE_VMADDR
        code = b''.join(remote.memory(address + start, min(1024, size - start))
                        for start in range(0, size, 1024))
        if hashlib.sha256(code).hexdigest() != guard['sha256']:
            raise DebugProtocolError(label + ' live code mismatch')


def read_session_context(remote, base, profile):
    """Copy only the two native progress bits while stopped. Never call a getter.

    The global is established by both native wrappers and an exact data symbol.
    A non-null pointer or progress bit does not attest membership/authentication.
    No session ID, player identity, pointer or arbitrary memory is emitted.
    """
    result = {'session_context_status': 'incomplete',
              'session_identity_verified': False, 'session_generation_verified': False}
    address = base + int(profile['global_pointer_va'], 16) - IMAGE_VMADDR
    pointer, = struct.unpack('<Q', remote.memory(address, 8))
    if pointer == 0:
        result['session_context_status'] = 'no_session_object'
        return result
    offsets = (profile['main_in_progress_offset'], profile['transition_in_progress_offset'])
    # These are exact getter offsets, not arbitrary offsets supplied by a caller.
    if offsets != (0x180d6, 0x1821e):
        raise DebugProtocolError('session-context offset profile mismatch')
    if pointer % 8 or not 0 < pointer < (1 << 48) - max(offsets):
        result['session_context_status'] = 'invalid_session_pointer'
        return result
    main = remote.memory(pointer + offsets[0], 1)[0]
    transition = remote.memory(pointer + offsets[1], 1)[0]
    result.update(session_context_status='observed',
                  native_main_session_in_progress=bool(main & 1),
                  native_transition_session_in_progress=bool(transition & 1))
    return result


def read_session_slots(remote, base, profile):
    """Read both established predicates. The selected pointer is local to this stop."""
    status = {'status': 'unobserved'}

    def pointer_ok(value):
        return 0 < value < (1 << 48) - 0xba38 and value % 8 == 0

    at = base + int(profile['global_pointer_va'], 16) - IMAGE_VMADDR
    try:
        manager, = struct.unpack('<Q', remote.memory(at, 8))
        if not pointer_ok(manager):
            return {'status': 'session_manager_unavailable'}, None
        main, transition = struct.unpack('<QQ', remote.memory(manager + 0x20, 16))
        slots = {'main': main, 'transition': transition}
        if (main and main == transition) or any(ptr and not pointer_ok(ptr) for ptr in slots.values()):
            return {'status': 'invalid_or_aliased_session_slots'}, None
        established = {
            name: bool(ptr and (struct.unpack('<I', remote.memory(ptr + 0xb0, 4))[0] & ~1) == 2)
            for name, ptr in slots.items()
        }
    except (DebugProtocolError, OSError):
        return status, None
    status = {'status': 'observed', 'main_slot_established': established['main'],
              'transition_slot_established': established['transition']}
    names = [name for name, active in established.items() if active]
    status['candidate_slot'] = names[0] if len(names) == 1 else ('ambiguous' if names else 'none')
    return status, slots[names[0]] if len(names) == 1 else None


def read_same_event_session_candidate(remote, base, metadata, source, event):
    status, candidate = read_session_slots(remote, base, metadata['session_slots'])
    if candidate is not None:
        path = Path(__file__).with_name('check_v133_peer_session_map.py')
        spec = spec_from_file_location('usb_scripted_peer_map', path)
        checker = module_from_spec(spec)
        spec.loader.exec_module(checker)

        def read_word(addr, width):
            if not 0 < addr <= (1 << 48) - width or addr % width:
                raise DebugProtocolError('peer table address outside observer bounds')
            return int.from_bytes(remote.memory(addr, width), 'little')

        try:
            connection = read_word(event + metadata['receive_context']['event_connection_offset'], 4)
            getter = base + int(metadata['peer_info_static']['getter_va'], 16) - IMAGE_VMADDR
            status['peer_table'] = checker.check_peer_session_map(
                lambda addr: read_word(addr, 4), lambda addr: read_word(addr, 8),
                source, candidate, connection, getter, check_transport_domain=True)
        except (DebugProtocolError, OSError):
            status['peer_table'] = {'status': 'bounded_read_failed'}
    return status


def read_receive_context(remote, base, profile, expected_receive=None):
    """Follow only the disassembled chain at handler ENTRY, before its prologue.

    No general unwinding, stack scanning, PAC stripping, packet/key/name dumps,
    function calls, writes or retained pointers. All values die before resume.
    Even a consistent engine association cannot attest cryptographic identity.
    """
    result = {'observed_path': 'undetermined', 'network_receive_call_chain_observed': False,
              'network_receive_stack_confirmed': False,
              'engine_source_association_observed': False, 'context_status': 'incomplete',
              'matched_frames': []}

    def pointer(value, alignment=8):
        return 0 < value < (1 << 48) and value % alignment == 0

    def live(va):
        return base + int(va, 16) - IMAGE_VMADDR

    # Preserve raw PC/LR/FP and peer pointers only within this one stopped sample.
    sp = remote.read_register(31)
    fp = remote.read_register(29)
    lr = remote.read_register(30)
    if not pointer(sp, 16):
        result['context_status'] = 'unsupported_stack_pointer'
        return result

    def frame_ok(value):
        return pointer(value, 16) and sp <= value <= sp + 65536 - 16

    dispatch_fp = None
    for frame in profile['frames']:
        if not frame_ok(fp) or lr != live(frame['return_va']):
            result['context_status'] = 'frame_or_callsite_mismatch'
            return result
        result['matched_frames'].append(frame['function'])
        if frame['function'] == 'dispatch':
            dispatch_fp = fp
        parent, saved_lr = struct.unpack('<QQ', remote.memory(fp, 16))
        if not frame_ok(parent) or parent < fp + 16:
            result['context_status'] = 'invalid_frame_chain'
            return result
        fp, lr = parent, saved_lr

    origin = next((name for name, spec in profile['origins'].items()
                   if lr == live(spec['return_va'])), None)
    if origin is None or dispatch_fp is None:
        result['context_status'] = 'unrecognized_dispatch_origin'
        return result
    result['observed_path'] = origin
    # A validated return-frame path is a *candidate receive call chain*, not
    # yet an event/source association. Never mark the combined receive gate
    # until references and connection IDs of this SAME stopped event agree.
    result['network_receive_call_chain_observed'] = origin == 'engine_receive_dispatch'
    if expected_receive is not None and (origin != 'engine_receive_dispatch' or fp != expected_receive[0]):
        result['context_status'] = 'different_receive_frame'
        return result

    message = fp + profile['origins'][origin]['message_fp_offset']
    if message < sp or message + 0x20 > fp:
        result['context_status'] = 'message_outside_frame'
        return result
    source, = struct.unpack('<Q', remote.memory(message + profile['message_source_offset'], 8))
    destination, = struct.unpack('<Q', remote.memory(message + profile['message_destination_offset'], 8))
    result['handler_source_matches_message'] = pointer(source) and source == remote.read_register(1)
    result['handler_destination_matches_message'] = pointer(destination) and destination == remote.read_register(2)
    result['source_destination_distinct'] = source != destination
    refs_match = (result['handler_source_matches_message'] and
                  result['handler_destination_matches_message'] and
                  result['source_destination_distinct'])
    if not refs_match:
        result['context_status'] = 'handler_reference_mismatch'
        return result
    if origin == 'engine_receive_dispatch':
        event, = struct.unpack('<Q', remote.memory(
            dispatch_fp + profile['dispatch_saved_event_fp_offset'], 8))
        if not pointer(event):
            result['context_status'] = 'invalid_event_pointer'
            return result
        if expected_receive is not None and (fp, event, source, destination) != expected_receive:
            result['context_status'] = 'queued_event_or_players_mismatch'
            return result
        event_connection, = struct.unpack('<i', remote.memory(
            event + profile['event_connection_offset'], 4))
        player_connection, = struct.unpack('<i', remote.memory(
            source + profile['player_connection_offset'], 4))
        result['connection_id_matches_source'] = event_connection >= 0 and event_connection == player_connection
        result['engine_source_association_observed'] = result['connection_id_matches_source']
        if not result['connection_id_matches_source']:
            result['context_status'] = 'connection_mismatch'
            return result
        # This proves only pointer/connection equality at the stopped PC.
        # It is NOT cryptographic authentication or durable session membership.
        result['network_receive_stack_confirmed'] = True
    result['context_status'] = 'observed'
    return result



def internal_site_va(metadata, site):
    """Internal breakpoint VA only from fingerprinted baseline, never guessed."""
    if site in metadata.get("internal_sites", {}):
        return int(metadata["internal_sites"][site],16)
    return int(metadata["symbols"][site]["va"],16)


def read_internal_candidate(remote, base, metadata, site):
    """Pure bounded stopped-process reads; no RAGE API invocation or writes."""
    report={"schema":"v133-usb-internal-candidate-v1",
            "status":"unsupported_site","authenticated_rp_sender_verified":False,
            "session_membership_verified":False,
            "session_generation_verified":False}
    def read32(addr):
        return struct.unpack("<I",remote.memory(addr,4))[0]
    def read64(addr):
        return struct.unpack("<Q",remote.memory(addr,8))[0]
    if site not in ("on_net_event_pre_dispatch","on_connection_peer_verify"):
        return report
    try:
        if site=="on_net_event_pre_dispatch":
            name="usb_pre_dispatch"
            path=Path(__file__).with_name("observe_v133_lldb.py")
            spec=spec_from_file_location(name,path)
            mod=module_from_spec(spec);spec.loader.exec_module(mod)
            report=mod.scan_pre_dispatch(
                read32,read64,remote.read_register(19),remote.read_register(20),
                remote.read_register(9),remote.read_register(10))
        else:
            # Exact OnConnectionEvent+0x654: x21=event, x22=current
            # snSession, x24=selected netPlayer, x1=peerID from native getter.
            session=remote.read_register(22)
            manager=remote.read_register(19)
            event=remote.read_register(21)
            if (not session or not manager or not event or
                read64(manager+0x20)!=session or read32(event+0x40)!=7):
                report["status"]="session_or_event_frame_mismatch"
                return report
            static=metadata["peer_info_static"]
            for va,word in (("getter_va","getter_instruction"),
                             ("getter_next_va","getter_next_instruction"),
                             ("peer_getter_va","peer_getter_instruction")):
                at=base+int(static[va],16)-IMAGE_VMADDR
                if remote.memory(at,4)!=struct.pack("<I",int(static[word],16)):
                    report["status"]="unknown_gamer_getter_build"
                    return report
            path=Path(__file__).with_name("check_v133_peer_session_map.py")
            spec=spec_from_file_location("usb_peer_map",path)
            checker=module_from_spec(spec);spec.loader.exec_module(checker)
            connection=read32(event+0x3c)
            getter=base+int(static["getter_va"],16)-IMAGE_VMADDR
            report=checker.check_peer_session_map(
                read32,read64,remote.read_register(24),session,
                connection,getter,remote.read_register(1))
    except (DebugProtocolError,KeyError,ValueError,TypeError,RuntimeError,
            OverflowError,IndexError,OSError):
        report["status"]="bounded_read_failed"
    return report


def wait_for_stop(remote, seconds):
    """Continue the game. Interrupt and read its stop reply on a timeout."""
    remote.send(b"c")
    remote.conn.settimeout(seconds)
    try:
        reply = remote.receive()
    except TimeoutError:
        remote.conn.settimeout(3)
        remote.conn.sendall(b"\x03")
        return remote.receive(), True
    return reply, False


def queue_stage_stop(remote, addresses, deadline):
    """Stop at the first allowed site and remove all of this stage's hardware BPs."""
    if time.monotonic() >= deadline:
        return None, None, 'timeout'
    with ExitStack() as armed:
        for address in addresses:
            hardware = f"{address:x},4".encode()
            require_ok(remote, b"Z1," + hardware, "hardware breakpoint installation")
            armed.callback(require_ok, remote, b"z1," + hardware, "hardware breakpoint removal")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, None, 'timeout'
        reply, timed_out = wait_for_stop(remote, remaining)
        remote.conn.settimeout(3)
        if timed_out:
            return None, None, 'timeout'
        thread = stop_thread(reply)
        if not thread or not reply.startswith(b'T05'):
            return None, None, 'unexpected_stop'
        require_ok(remote, b"Hg" + thread, "stopped thread selection")
        pc = remote.read_register(32)
        if pc not in addresses:
            return None, None, 'unexpected_pc'
        return pc, thread, 'hit'


def capture_session_swap(remote, base, metadata, wait_seconds):
    """Check slot order across one native store without retaining addresses."""
    if not 1 <= wait_seconds <= 60:
        raise ValueError("wait_seconds outside bounded range")
    profile = metadata['session_swap']
    verify_context_code(remote, base, profile, label='session-swap')
    for number, names in ((19, (b'x19',)), (29, (b'fp', b'x29')), (32, (b'pc',))):
        name = remote.request(f'qRegisterInfo{number:x}'.encode()).partition(b';')[0]
        if name not in tuple(b'name:' + n for n in names):
            raise DebugProtocolError('session-swap register layout mismatch')

    pre = base + internal_site_va(metadata, 'session_swap') - IMAGE_VMADDR
    post = base + int(profile['post_store_va'], 16) - IMAGE_VMADDR
    if post != pre + 4:
        raise DebugProtocolError('session-swap store and successor are not adjacent')
    deadline = time.monotonic() + wait_seconds
    sample = {'site': 'session_swap', 'status': 'incomplete',
              'same_session_slots_swapped': False, 'session_generation_verified': False}
    pc, thread, status = queue_stage_stop(remote, (pre,), deadline)
    if pc is None:
        sample['status'] = status
        return sample

    manager = remote.read_register(19)
    frame = remote.read_register(29)
    global_pointer = base + int(profile['global_pointer_va'], 16) - IMAGE_VMADDR
    current_manager = int.from_bytes(remote.memory(global_pointer, 8), 'little')
    if not 0 < manager < (1 << 48) - 0x30 or manager % 8 or manager != current_manager or not frame or frame % 16:
        sample['status'] = 'invalid_session_swap_context'
        return sample
    before = struct.unpack('<QQ', remote.memory(manager + 0x20, 16))
    if before[0] == before[1] or any(not 0 < ptr < 1 << 48 or ptr % 8 for ptr in before):
        sample['status'] = 'ambiguous_slot_values'
        return sample

    pc, next_thread, status = queue_stage_stop(remote, (post,), deadline)
    if pc is None:
        sample['status'] = status
    elif (next_thread != thread or remote.read_register(19) != manager
          or remote.read_register(29) != frame):
        sample['status'] = 'different_swap_invocation'
    else:
        after = struct.unpack('<QQ', remote.memory(manager + 0x20, 16))
        sample['same_session_slots_swapped'] = after == before[::-1]
        sample['status'] = 'slot_swap_observed' if sample['same_session_slots_swapped'] else 'unexpected_slot_order'
    return sample


def read_enqueue_transport(remote, base, profile, queue, queue_offset, producer):
    """A buffered event must never inherit the current packet's decrypt indicator."""
    result = {'caller_observed': False, 'endpoint_connection_observed': False,
              'decrypt_indicator': 'unobserved', 'integrity_path_inferred': 'unobserved'}
    if producer != 'immediate_frame':
        return result
    fp = remote.read_register(29)
    sp = remote.read_register(31)
    if not 0 < sp < fp < (1 << 48) - 0x800 or sp % 16 or fp - sp != 0x60:
        return result
    expected_return = base + int(profile['unpack_caller_return_va'], 16) - IMAGE_VMADDR
    try:
        connection_fp, frame_return = struct.unpack('<QQ', remote.memory(fp, 16))
        frame_expected, connection_expected = (
            base + int(va, 16) - IMAGE_VMADDR for va in profile['immediate_parent_returns'])
        if connection_fp != fp + 0x150 or frame_return != frame_expected:
            return result
        manager_fp, connection_return = struct.unpack('<QQ', remote.memory(connection_fp, 16))
        if manager_fp != connection_fp + 0x5b0 or connection_return != connection_expected:
            return result
        # Both callers must retain the same connection, not just a known LR.
        connection = remote.read_register(20)
        for saved in (fp - 0x10, connection_fp - 0x20):
            saved_connection, = struct.unpack('<Q', remote.memory(saved, 8))
            if saved_connection != connection:
                return result
        caller_fp, caller_lr = struct.unpack('<QQ', remote.memory(manager_fp, 16))
        if caller_fp != manager_fp + 0x60 or caller_lr != expected_return:
            return result
        caller_manager, = struct.unpack('<Q', remote.memory(manager_fp - 0x18, 8))
        if not caller_manager or caller_manager + queue_offset != queue:
            return result
        result['caller_observed'] = True
        # Manager Unpack selects x22 from endpoint[x25] into connection Unpack.
        # That callee saves caller x23 (endpoint) and x25 (channel) before
        # reusing them. This is a same-stop table association, not peer auth.
        endpoint, = struct.unpack('<Q', remote.memory(connection_fp - 0x28, 8))
        channel, = struct.unpack('<Q', remote.memory(connection_fp - 0x38, 8))
        if not 0 < endpoint < (1 << 48) - 0x80 or endpoint % 8 or channel >= 16:
            return result
        selected_connection, = struct.unpack('<Q', remote.memory(endpoint + channel * 8, 8))
        if selected_connection != connection:
            return result
        result['endpoint_connection_observed'] = True
        indicator = remote.memory(caller_fp - 0x35, 1)[0]
    except (DebugProtocolError, OSError):
        return result
    if indicator in (0, 1):
        result['decrypt_indicator'] = 'set' if indicator else 'clear'
        # Only the guarded normal P2pDecrypt path sets 1 after the HMAC/AES
        # routine succeeds. This infers a path; it cannot bind its key to a
        # game player or prove key-exchange authenticity/replay protection.
        result['integrity_path_inferred'] = (
            'address_key_hmac_candidate' if indicator else 'tunnel_or_bypass_unresolved')
    return result


def capture_queue_context(remote, base, metadata, profile, wait_seconds, follow_scripted=False):
    """Trace one queued event within a single attach, as a candidate association."""
    if not 1 <= wait_seconds <= 60:
        raise ValueError("wait_seconds outside bounded range")
    spec = spec_from_file_location("usb_queue_correlation", Path(__file__).with_name("queue_correlation.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    correlation = module.QueueCorrelation(limit=1)

    def live(va):
        return base + int(va, 16) - IMAGE_VMADDR

    if profile.get('version') != 3:
        raise DebugProtocolError('obsolete queue profile lacks received-frame or integrity guards')
    integrity_guards = {
        ('p2p_decrypt', '0x101cd5ea4', 0x38c),
        ('p2p_crypt_decrypt', '0x101cdfee4', 0x428),
        ('generate_hmac', '0x101ce8810', 0xf8),
        ('get_p2p_key', '0x101cfbe9c', 0x130),
    }
    supplied_guards = {(g['function'], g['va'], g['size']) for g in profile['code_guards']}
    if not integrity_guards <= supplied_guards:
        raise DebugProtocolError('missing exact integrity code guards')
    enqueue = {live(va): name for name, va in profile['enqueue_sites'].items()}
    dispatch = live(profile['dispatch_event_va'])
    returns = {live(va) for va in profile['dispatch_caller_returns']}
    pre_dispatch = live(profile['on_net_event_pre_dispatch_va'])
    if pre_dispatch != base + internal_site_va(metadata, 'on_net_event_pre_dispatch') - IMAGE_VMADDR:
        raise DebugProtocolError('queue profile disagrees with pre-dispatch baseline')
    for reg, names in ((0, (b'x0',)), (1, (b'x1',)), (9, (b'x9',)), (10, (b'x10',)),
                       (19, (b'x19',)), (20, (b'x20',)), (21, (b'x21',)), (27, (b'x27',)),
                       (28, (b'x28',)), (29, (b'fp', b'x29')), (30, (b'lr', b'x30')),
                       (31, (b'sp',)), (32, (b'pc',))):
        register = remote.request(f'qRegisterInfo{reg:x}'.encode()).partition(b';')[0]
        if register not in tuple(b'name:' + name for name in names):
            raise DebugProtocolError('queue-context register layout mismatch')
    verify_context_code(remote, base, profile, label='queue-context')
    if follow_scripted:
        receive_profile = metadata['receive_context']
        peer_guards = {
            ('peer_info_init', '0x101d64ae4', 0xb8),
            ('local_net_peer_address', '0x101ce0a3c', 0x358),
            ('peer_address_getter', '0x101d64ba4', 0x4),
        }
        supplied = {(g['function'], g['va'], g['size']) for g in metadata['session_slots']['code_guards']}
        if not peer_guards <= supplied:
            raise DebugProtocolError('missing exact peer-domain code guards')
        verify_context_code(remote, base, receive_profile)
        verify_context_code(remote, base, metadata['session_slots'], label='session-slots')
        handler = live(metadata['symbols']['script_event_handler']['va'])
        delegate_return = live(receive_profile['origins']['engine_receive_dispatch']['return_va'])

    sample = {
        'site': 'phase19_queue_context',
        'queue_context_status': 'incomplete',
        'last_stage': 'enqueue',
        'queue_object_link_observed': False,
        'dispatch_and_predispatch_same_thread': False,
        'authenticated_rp_sender_verified': False,
        'session_generation_verified': False,
        'game_thread_affinity_verified': False,
        'custom_rp_event_received': False,
    }
    deadline = time.monotonic() + wait_seconds
    pc, _, status = queue_stage_stop(remote, tuple(enqueue), deadline)
    if pc is None:
        sample['queue_context_status'] = status
        return sample
    queue = remote.read_register(0)
    event = remote.read_register(1)
    if correlation.observe_unpacked(queue, event) != 'QUEUED_CANDIDATE':
        sample['queue_context_status'] = 'invalid_enqueue_registers'
        return sample
    producer = enqueue[pc]
    sample['enqueue_origin'] = producer
    connection = remote.read_register(20)
    if not 0 < connection < (1 << 48) - 0x140 or connection % 8:
        sample['queue_context_status'] = 'invalid_enqueue_connection'
        return sample
    # InFrame's constructor inherits FrameReceived::GetId, then installs its
    # derived vtable. Verify this exact event class and the live type expected
    # by OnNetEvent before attempting to correlate the object across the queue.
    vtable, = struct.unpack('<Q', remote.memory(event, 8))
    expected_vtable = live(profile['frame_vtable_va'])
    if (vtable != expected_vtable or
            struct.unpack('<Q', remote.memory(expected_vtable + 0x18, 8))[0] != live(profile['frame_get_id_va']) or
            struct.unpack('<I', remote.memory(live(profile['frame_type_id_va']), 4))[0] != 4):
        sample['queue_context_status'] = 'enqueue_event_type_mismatch'
        return sample
    connection_queue, = struct.unpack('<Q', remote.memory(connection + 0xb8, 8))
    connection_id, = struct.unpack('<I', remote.memory(connection + 0x10, 4))
    event_connection, = struct.unpack('<I', remote.memory(event + 0x3c, 4))
    if connection_queue != queue or connection_id >= 0x80000000 or connection_id != event_connection:
        sample['queue_context_status'] = 'enqueue_connection_mismatch'
        return sample
    sample['enqueue_frame_connection_observed'] = True
    sample['enqueue_transport'] = read_enqueue_transport(
        remote, base, profile, queue, module.MANAGER_QUEUE_OFFSET, producer)

    sample['last_stage'] = 'dispatch_event'
    pc, dispatch_thread, status = queue_stage_stop(remote, (dispatch,), deadline)
    if pc is None:
        sample['queue_context_status'] = status
        return sample
    manager = remote.read_register(0)
    consumer = remote.read_register(21)
    caller = remote.read_register(30)
    # At the two guarded DispatchEvent calls, x28 is the result of NextEvent,
    # x27 holds the manager and x21 points to that manager's event consumer.
    if (caller not in returns or not 0 < manager < (1 << 48) - 0x2c8
            or manager % 8 or remote.read_register(27) != manager
            or consumer != manager + 0x2c0 or queue != manager + module.MANAGER_QUEUE_OFFSET
            or remote.read_register(1) != event or remote.read_register(28) != event):
        sample['queue_context_status'] = 'dispatch_event_mismatch'
        return sample
    current_queue, = struct.unpack('<Q', remote.memory(consumer, 8))
    if correlation.observe_next(current_queue, event) != 'NEXT_CANDIDATE':
        sample['queue_context_status'] = 'consumer_queue_mismatch'
        return sample

    sample['last_stage'] = 'on_net_event_pre_dispatch'
    # Arm a stop at the caller's return too. A later event must never satisfy
    # the final comparison after the selected DispatchEvent call has returned.
    pc, thread, status = queue_stage_stop(remote, (pre_dispatch, caller), deadline)
    if pc == caller:
        sample['queue_context_status'] = 'returned_before_predispatch'
        return sample
    if pc is None:
        sample['queue_context_status'] = status
        return sample
    if thread != dispatch_thread or remote.read_register(20) != event:
        sample['queue_context_status'] = 'predispatch_event_or_thread_mismatch'
        return sample
    if correlation.observe_on_event(manager, event) != 'QUEUE_OBJECT_LINK_CANDIDATE_ONLY':
        sample['queue_context_status'] = 'incomplete_queue_chain'
        return sample

    sample['queue_context_status'] = 'queue_object_link_candidate_only'
    sample['queue_object_link_observed'] = True
    sample['dispatch_and_predispatch_same_thread'] = True
    sample['native_candidate'] = read_internal_candidate(
        remote, base, metadata, 'on_net_event_pre_dispatch')
    if follow_scripted:
        receive_frame = (remote.read_register(29), event, remote.read_register(9),
                         remote.read_register(10))
        sample['last_stage'] = 'script_event_handler'
        pc, handler_thread, status = queue_stage_stop(remote, (handler, delegate_return), deadline)
        if pc is None:
            sample['scripted_receive_status'] = status
        elif pc == delegate_return:
            sample['scripted_receive_status'] = 'returned_before_scripted_handler'
        elif handler_thread != dispatch_thread:
            sample['scripted_receive_status'] = 'scripted_thread_mismatch'
        else:
            context = read_receive_context(remote, base, receive_profile, expected_receive=receive_frame)
            sample['scripted_receive'] = context
            sample['scripted_receive_status'] = context['context_status']
            sample['same_queued_event_at_scripted_handler'] = context['network_receive_stack_confirmed']
            if sample['same_queued_event_at_scripted_handler']:
                sample['scripted_session_candidate'] = read_same_event_session_candidate(
                    remote, base, metadata, receive_frame[2], event)
    return sample


def capture(remote, base, metadata, stock_job=False, site=DEFAULT_SITE, wait_seconds=3,
            receive_context=False, session_context=False):
    """Capture exactly one guarded PC stop. A breakpoint hit is NOT sender proof."""
    if site not in OBSERVABLE_SITES:
        raise ValueError("unsupported observation site")
    if stock_job and site != "jobs_update":
        raise ValueError("--stock-job is only valid at jobs_update")
    if receive_context and site != 'script_event_handler':
        raise ValueError('--receive-context is only valid at script_event_handler')
    if session_context and site != 'jobs_update':
        raise ValueError('--session-context is only valid at jobs_update')
    if not 1 <= wait_seconds <= 60:
        raise ValueError("wait_seconds outside bounded range")
    va = internal_site_va(metadata, site)
    address = base + va - IMAGE_VMADDR
    if remote.request(b"qRegisterInfo20").partition(b";")[0] != b"name:pc":
        raise DebugProtocolError("ARM64 PC register layout mismatch")
    if remote.request(b"qRegisterInfo1e").partition(b";")[0] not in (b"name:lr", b"name:x30"):
        raise DebugProtocolError("ARM64 LR register layout mismatch")
    if receive_context:
        for number, names in ((29, (b'fp', b'x29')), (31, (b'sp',)),
                              (1, (b'x1',)), (2, (b'x2',))):
            name = remote.request(f'qRegisterInfo{number:x}'.encode()).partition(b';')[0]
            if name not in tuple(b'name:' + n for n in names):
                raise DebugProtocolError('receive-context register layout mismatch')
        verify_context_code(remote, base, metadata['receive_context'])
    if session_context:
        verify_context_code(remote, base, metadata['session_context'], label='session-context')
        if 'session_slots' in metadata:
            verify_context_code(remote, base, metadata['session_slots'], label='session-slots')
    hardware = f"{address:x},4".encode()
    require_ok(remote, b"Z1," + hardware, "hardware breakpoint installation")
    try:
        reply, timed_out = wait_for_stop(remote, wait_seconds)
        tid = stop_thread(reply)
        if tid is None:
            raise DebugProtocolError("no selected thread in stop reply")
        require_ok(remote, b"Hg" + tid, "stopped thread selection")
        hit = remote.read_register(32) == address and reply.startswith(b'T05')
        callsite_matches = False
        if site == "jobs_update" and hit and not timed_out:
            caller = next(b for b in metadata["branches"]
                          if b["source"] == "online_update" and b["target"] == site)
            return_address = base + int(caller["at"], 16) - IMAGE_VMADDR + 4
            callsite_matches = remote.read_register(30) == return_address
        sample = {
            "site": site,
            "timed_out": timed_out,
            "hardware_stop_at_expected_pc": hit and not timed_out,
            "macport_online_update_callsite_matches": callsite_matches,
            "thread_label": "T1",
            "thread_label_scope": "anonymous_single_capture_only",
            "game_thread_affinity_verified": False,
            # A single PC/LR observation cannot prove inbound network provenance.
            "observed_path": "undetermined",
            "network_receive_call_chain_observed": False,
            "network_receive_stack_confirmed": False,
            "authenticated_rp_sender_verified": False,
            "session_generation_verified": False,
            "custom_rp_event_received": False,
        }
        if stock_job and callsite_matches:
            sample["stock_job_candidate"] = read_stock_job(remote, base, metadata["stock_job_sample"])
            if 'local_work_sample' in metadata:
                sample['local_work_candidate'] = read_local_work(remote, base, metadata['local_work_sample'])
        if session_context and callsite_matches:
            remote.conn.settimeout(3)
            sample.update(read_session_context(remote, base, metadata['session_context']))
            if 'session_slots' in metadata:
                sample['session_slots'], _ = read_session_slots(remote, base, metadata['session_slots'])
        if receive_context and hit and not timed_out:
            remote.conn.settimeout(3)
            sample.update(read_receive_context(remote, base, metadata['receive_context']))
        if site in ("on_net_event_pre_dispatch","on_connection_peer_verify") and (
            hit and not timed_out):
            # All reads happen only when the verified one-shot PC actually hit.
            remote.conn.settimeout(3)
            sample["native_candidate"]=read_internal_candidate(remote,base,metadata,site)
        return sample
    finally:
        require_ok(remote, b"z1," + hardware, "hardware breakpoint removal")


def run_capture(conn, pid, stock_job=False, site=DEFAULT_SITE, wait_seconds=3,
                receive_context=False, session_context=False, queue_context=False):
    metadata = json.loads(BASELINE.read_text(encoding="utf-8"))
    if metadata["uuid"] != UUID:
        raise DebugProtocolError("static baseline UUID mismatch")
    remote = Remote(conn)
    remote.request(b"qSupported")
    remote.request(b"QEnableErrorStrings")
    reply = remote.request(f"vAttach;{pid:x}".encode())
    if not re.match(rb"^[ST][0-9a-fA-F]{2}", reply):
        error = reply[:3].decode("ascii", "replace") if reply.startswith(b"E") else "no stop reply"
        raise DebugProtocolError("iOS declined GTA attach (" + error + ")")
    try:
        info = remote.request(b"qProcessInfo")
        reported = re.search(rb"(?:^|;)pid:([0-9a-fA-F]+);", info)
        if not reported or int(reported[1], 16) != pid:
            raise DebugProtocolError("attached PID mismatch")
        base = main_image(remote)
        for guarded_site in OBSERVABLE_SITES:
            va = internal_site_va(metadata, guarded_site)
            expected = struct.pack("<I", int(metadata["trace_sites"][guarded_site], 16))
            if remote.memory(base + va - IMAGE_VMADDR, 4) != expected:
                raise DebugProtocolError("live instruction mismatch at " + guarded_site)
        if queue_context:
            queue = json.loads(QUEUE_BASELINE.read_text(encoding="utf-8"))
            if queue['uuid'] != UUID or queue['executable_sha256'] != metadata['executable_sha256']:
                raise DebugProtocolError("queue baseline fingerprint mismatch")
            return capture_queue_context(remote, base, metadata, queue['usb_profile'], wait_seconds,
                                         follow_scripted=receive_context)
        if site == 'session_swap':
            return capture_session_swap(remote, base, metadata, wait_seconds)
        if stock_job:
            for guard in metadata["stock_job_sample"]["guard_sites"]:
                address = base + int(guard["va"], 16) - IMAGE_VMADDR
                if remote.memory(address, 4) != struct.pack("<I", int(guard["word"], 16)):
                    raise DebugProtocolError("local job metadata instruction guard mismatch")
            if 'local_work_sample' in metadata:
                verify_context_code(remote, base, metadata['local_work_sample'], label='local-work')
        return capture(remote, base, metadata, stock_job=stock_job, site=site,
                       wait_seconds=wait_seconds, receive_context=receive_context,
                       session_context=session_context)
    finally:
        require_ok(remote, b"D", "detach")


def select_usb_device(devices, requested=None):
    if not isinstance(devices, list) or any(not isinstance(row, dict) for row in devices):
        raise DebugProtocolError("unexpected usbmux inventory")
    candidates = {
        identifier.lower(): identifier
        for row in devices
        if row.get("ConnectionType") == "USB"
        and isinstance(identifier := row.get("UniqueDeviceID"), str)
        and re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{8}-[0-9a-fA-F]{16})", identifier)
    }
    if requested is not None:
        if requested.lower() not in candidates:
            raise DebugProtocolError("requested device is not connected over USB")
        return candidates[requested.lower()]
    if len(candidates) > 1:
        raise DebugProtocolError("multiple USB devices connected; select one with --udid")
    if not candidates:
        raise DebugProtocolError("no USB device connected")
    return next(iter(candidates.values()))


def collect(bundle, stock_job=False, site=DEFAULT_SITE, wait_seconds=3,
            receive_context=False, session_context=False, queue_context=False, udid=None):
    pmd = [sys.executable, "-m", "pymobiledevice3"]
    inventory = subprocess.run(pmd + ["usbmux", "list"], capture_output=True, text=True, timeout=20)
    if inventory.returncode:
        raise DebugProtocolError("could not list USB devices")
    selected = select_usb_device(json.loads(inventory.stdout), udid)
    device_args = ["--userspace", "--udid", selected]
    try:
        result = subprocess.run(
            pmd + ["developer", "dvt", "process-id-for-bundle-id", *device_args, bundle],
            capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        raise DebugProtocolError("GTA process lookup timed out") from None
    if result.returncode or not re.fullmatch(r"[0-9]+", result.stdout.strip()):
        raise DebugProtocolError("could not look up the GTA process on the selected iPhone")
    pid = int(result.stdout.strip())
    if pid <= 1:
        raise ValueError("GTA is not running. Open stock Sandbox first.")
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    proxy = subprocess.Popen(pmd + ["developer", "debugserver", "start-server", *device_args,
                                    "--host", "127.0.0.1", "--local-port", str(port)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            if proxy.poll() is not None:
                raise DebugProtocolError("debugproxy exited before binding")
            try:
                conn = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            except OSError:
                time.sleep(0.25)
            else:
                with conn:
                    conn.settimeout(5)
                    return run_capture(conn, pid, stock_job=stock_job, site=site,
                                       wait_seconds=wait_seconds, receive_context=receive_context,
                                       session_context=session_context, queue_context=queue_context)
        raise DebugProtocolError("loopback debugproxy connect deadline elapsed")
    finally:
        if proxy.poll() is None:
            proxy.terminate()
            try:
                proxy.wait(timeout=6)
            except subprocess.TimeoutExpired:
                raise DebugProtocolError("debugproxy did not terminate") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Installed GTA bundle identifier, including its signing suffix if any.")
    parser.add_argument("--udid", help="Local USB device identifier. Required when multiple devices are connected.")
    parser.add_argument("--stock-job", action="store_true",
                        help="Also sample exact-build local stock job fields at jobs_update only.")
    parser.add_argument("--site", choices=OBSERVABLE_SITES, default=DEFAULT_SITE,
                        help="Read-only observation site. session_swap checks before and after one store.")
    parser.add_argument("--wait-seconds", type=int, default=3,
                        help="Bounded time (1-60 seconds) to observe one stop; no polling loop.")
    parser.add_argument('--receive-context', action='store_true',
                        help='At script_event_handler entry, compare exact guarded receive/local frame chains and sender references. Does not authenticate a peer.')
    parser.add_argument('--session-context', action='store_true',
                        help='At the verified jobs_update caller, read guarded native main/transition progress bits only. No session identity or authority.')
    parser.add_argument('--queue-context', action='store_true',
                        help='Trace one queue event through the guarded dispatcher. Add --receive-context to follow its scripted handler.')
    args = parser.parse_args()
    if not re.fullmatch(r"com\.macport\.gtav(?:\.[A-Za-z0-9]{5,24})?", args.bundle):
        parser.error("expected GTA v13.3 bundle identifier")
    if args.stock_job and args.site != "jobs_update":
        parser.error("--stock-job is valid only with --site jobs_update")
    if not 1 <= args.wait_seconds <= 60:
        parser.error("--wait-seconds must be between 1 and 60")
    if args.receive_context and not args.queue_context and args.site != 'script_event_handler':
        parser.error('--receive-context requires --site script_event_handler')
    if args.session_context and args.site != 'jobs_update':
        parser.error('--session-context requires --site jobs_update')
    if args.queue_context and (args.site != DEFAULT_SITE or args.stock_job
                               or args.session_context):
        parser.error('--queue-context supports only --receive-context as a second observation mode')
    try:
        sample = collect(args.bundle, args.stock_job, args.site, args.wait_seconds,
                         args.receive_context, args.session_context, args.queue_context, args.udid)
    except (OSError, ValueError, subprocess.SubprocessError, DebugProtocolError) as exc:
        parser.exit(1, f"Observer failed: {exc}\n")
    print(json.dumps(sample, sort_keys=True))
    if args.site == 'session_swap':
        return 0 if sample['same_session_slots_swapped'] else 1
    if args.queue_context:
        matched = (sample.get('same_queued_event_at_scripted_handler') if args.receive_context
                   else sample['queue_object_link_observed'])
        return 0 if matched else 1
    complete = not args.receive_context or sample.get('context_status') == 'observed'
    complete = complete and (not args.session_context or sample.get('session_context_status') == 'observed')
    return 0 if sample["hardware_stop_at_expected_pc"] and complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
