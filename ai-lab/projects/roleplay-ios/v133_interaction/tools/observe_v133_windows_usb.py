"""Bounded one-site observer for an authorized, development-signed v13.3 iPhone.

Run with Python 3.13 and pymobiledevice3 11.56.0. GTA must already be
running in Sandbox. This tool uses a loopback Apple debugproxy connection.
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
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[2] / "baselines" / "phase9-v133-engine.json"
UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
IMAGE_VMADDR = 0x100000000
DEFAULT_SITE = "jobs_update"
OBSERVABLE_SITES = ("jobs_update", "script_event_handler", "script_decide", "on_net_event",
                    "on_net_event_pre_dispatch", "on_connection_peer_verify")
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


def verify_context_code(remote, base, profile, label='receive-context'):
    """Guard full functions, including every prologue and tail-call path."""
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


def read_receive_context(remote, base, profile):
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
        from importlib.util import spec_from_file_location,module_from_spec
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
    hardware = f"{address:x},4".encode()
    require_ok(remote, b"Z1," + hardware, "hardware breakpoint installation")
    try:
        remote.send(b"c")
        remote.conn.settimeout(wait_seconds)
        timed_out = False
        try:
            reply = remote.receive()
        except TimeoutError:
            timed_out = True
            remote.conn.sendall(b"\x03")
            reply = remote.receive()
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
        if session_context and callsite_matches:
            remote.conn.settimeout(3)
            sample.update(read_session_context(remote, base, metadata['session_context']))
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
                receive_context=False, session_context=False):
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
        if stock_job:
            for guard in metadata["stock_job_sample"]["guard_sites"]:
                address = base + int(guard["va"], 16) - IMAGE_VMADDR
                if remote.memory(address, 4) != struct.pack("<I", int(guard["word"], 16)):
                    raise DebugProtocolError("local job metadata instruction guard mismatch")
        return capture(remote, base, metadata, stock_job=stock_job, site=site,
                       wait_seconds=wait_seconds, receive_context=receive_context,
                       session_context=session_context)
    finally:
        require_ok(remote, b"D", "detach")


def collect(bundle, stock_job=False, site=DEFAULT_SITE, wait_seconds=3,
            receive_context=False, session_context=False):
    pmd = [sys.executable, "-m", "pymobiledevice3"]
    result = subprocess.run(pmd + ["developer", "dvt", "process-id-for-bundle-id", bundle],
                            capture_output=True, text=True, timeout=20, check=True)
    pid = int(result.stdout.strip())
    if pid <= 1:
        raise ValueError("GTA is not running. Open stock Sandbox first.")
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    proxy = subprocess.Popen(pmd + ["developer", "debugserver", "start-server", "--userspace",
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
                                       session_context=session_context)
        raise DebugProtocolError("loopback debugproxy connect deadline elapsed")
    finally:
        if proxy.poll() is None:
            proxy.terminate()
            proxy.wait(timeout=6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Installed GTA bundle identifier, including its signing suffix if any.")
    parser.add_argument("--stock-job", action="store_true",
                        help="Also sample exact-build local stock job fields at jobs_update only.")
    parser.add_argument("--site", choices=OBSERVABLE_SITES, default=DEFAULT_SITE,
                        help="Read-only single hardware breakpoint site; does not authenticate an event.")
    parser.add_argument("--wait-seconds", type=int, default=3,
                        help="Bounded time (1-60 seconds) to observe one stop; no polling loop.")
    parser.add_argument('--receive-context', action='store_true',
                        help='At script_event_handler entry, compare exact guarded receive/local frame chains and sender references. Does not authenticate a peer.')
    parser.add_argument('--session-context', action='store_true',
                        help='At the verified jobs_update caller, read guarded native main/transition progress bits only. No session identity or authority.')
    args = parser.parse_args()
    if not re.fullmatch(r"com\.macport\.gtav(?:\.[A-Za-z0-9]{5,24})?", args.bundle):
        parser.error("expected GTA v13.3 bundle identifier")
    if args.stock_job and args.site != "jobs_update":
        parser.error("--stock-job is valid only with --site jobs_update")
    if not 1 <= args.wait_seconds <= 60:
        parser.error("--wait-seconds must be between 1 and 60")
    if args.receive_context and args.site != 'script_event_handler':
        parser.error('--receive-context requires --site script_event_handler')
    if args.session_context and args.site != 'jobs_update':
        parser.error('--session-context requires --site jobs_update')
    try:
        sample = collect(args.bundle, args.stock_job, args.site, args.wait_seconds,
                         args.receive_context, args.session_context)
    except (OSError, ValueError, subprocess.SubprocessError, DebugProtocolError) as exc:
        parser.exit(1, f"Observer failed: {exc}\n")
    print(json.dumps(sample, sort_keys=True))
    complete = not args.receive_context or sample.get('context_status') == 'observed'
    complete = complete and (not args.session_context or sample.get('session_context_status') == 'observed')
    return 0 if sample["hardware_stop_at_expected_pc"] and complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
