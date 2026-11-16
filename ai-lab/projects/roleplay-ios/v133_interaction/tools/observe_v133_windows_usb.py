"""Bounded one-site observer for an authorized, development-signed v13.3 iPhone.

Run with Python 3.13 and pymobiledevice3 11.56.0. GTA must already be
running in Sandbox. This tool uses a loopback Apple debugproxy connection.
It can briefly pause GTA and never falls back to a software breakpoint.
"""
import argparse
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
OBSERVABLE_SITES = ("jobs_update", "script_event_handler", "script_decide", "on_net_event")
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


def capture(remote, base, metadata, stock_job=False, site=DEFAULT_SITE, wait_seconds=3):
    """Capture exactly one guarded PC stop. A breakpoint hit is NOT sender proof."""
    if site not in OBSERVABLE_SITES:
        raise ValueError("unsupported observation site")
    if stock_job and site != "jobs_update":
        raise ValueError("--stock-job is only valid at jobs_update")
    if not 1 <= wait_seconds <= 60:
        raise ValueError("wait_seconds outside bounded range")
    va = int(metadata["symbols"][site]["va"], 16)
    address = base + va - IMAGE_VMADDR
    if remote.request(b"qRegisterInfo20").partition(b";")[0] != b"name:pc":
        raise DebugProtocolError("ARM64 PC register layout mismatch")
    if remote.request(b"qRegisterInfo1e").partition(b";")[0] not in (b"name:lr", b"name:x30"):
        raise DebugProtocolError("ARM64 LR register layout mismatch")
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
        hit = remote.read_register(32) == address
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
            # A single PC/LR observation cannot prove inbound network provenance.
            "observed_path": "undetermined",
            "network_receive_stack_confirmed": False,
            "authenticated_rp_sender_verified": False,
            "session_generation_verified": False,
            "custom_rp_event_received": False,
        }
        if stock_job and callsite_matches:
            sample["stock_job_candidate"] = read_stock_job(remote, base, metadata["stock_job_sample"])
        return sample
    finally:
        require_ok(remote, b"z1," + hardware, "hardware breakpoint removal")


def run_capture(conn, pid, stock_job=False, site=DEFAULT_SITE, wait_seconds=3):
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
            va = int(metadata["symbols"][guarded_site]["va"], 16)
            expected = struct.pack("<I", int(metadata["trace_sites"][guarded_site], 16))
            if remote.memory(base + va - IMAGE_VMADDR, 4) != expected:
                raise DebugProtocolError("live instruction mismatch at " + guarded_site)
        if stock_job:
            for guard in metadata["stock_job_sample"]["guard_sites"]:
                address = base + int(guard["va"], 16) - IMAGE_VMADDR
                if remote.memory(address, 4) != struct.pack("<I", int(guard["word"], 16)):
                    raise DebugProtocolError("local job metadata instruction guard mismatch")
        return capture(remote, base, metadata, stock_job=stock_job, site=site, wait_seconds=wait_seconds)
    finally:
        require_ok(remote, b"D", "detach")


def collect(bundle, stock_job=False, site=DEFAULT_SITE, wait_seconds=3):
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
                    return run_capture(conn, pid, stock_job=stock_job, site=site, wait_seconds=wait_seconds)
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
    args = parser.parse_args()
    if not re.fullmatch(r"com\.macport\.gtav(?:\.[A-Za-z0-9]{5,24})?", args.bundle):
        parser.error("expected GTA v13.3 bundle identifier")
    if args.stock_job and args.site != "jobs_update":
        parser.error("--stock-job is valid only with --site jobs_update")
    if not 1 <= args.wait_seconds <= 60:
        parser.error("--wait-seconds must be between 1 and 60")
    try:
        sample = collect(args.bundle, args.stock_job, args.site, args.wait_seconds)
    except (OSError, ValueError, subprocess.SubprocessError, DebugProtocolError) as exc:
        parser.exit(1, f"Observer failed: {exc}\n")
    print(json.dumps(sample, sort_keys=True))
    return 0 if sample["hardware_stop_at_expected_pc"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
