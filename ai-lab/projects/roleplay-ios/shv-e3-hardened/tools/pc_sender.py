#!/usr/bin/env python3
"""RBP1 E3: Python desktop sender for ONE iPhone receiver on the same LAN.

Diagnostic PING only. This does not use or authenticate RAGE multiplayer.
Never print HMAC secrets, raw player IDs, or complete packet bytes.
Compatible with GTA v13.3 Phase12 E3 RBP1 HMAC-SHA256/16, 96 byte frame.
"""
import argparse
import hashlib
import hmac
import ipaddress
import secrets
import socket
import struct
import sys
import time
from pathlib import Path

FRAME = struct.Struct('!4sBBHQQ')
WIRE_SIZE = 96
HEADER_SIZE = 80
KIND_ACTION = 1
KIND_ACK = 2
KIND_NATIVE = 3
MAX_SKEW_MS = 15000


def now_ms():
    return time.time_ns() // 1000000


def parse_config(path, required_mode='sender'):
    config = {}
    for raw in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('Invalid configuration line')
        key, value = line.split('=', 1)
        if key in config:
            raise ValueError('Duplicate configuration key')
        config[key] = value
    expected = {'mode', 'listen_port', 'peer_port', 'peer_ipv4',
                'self_id_hex', 'peer_id_hex', 'session_hex', 'key_hex'}
    if set(config) != expected or config['mode'] != required_mode:
        raise ValueError('Require exactly eight '+required_mode+'-mode fields')
    for name, count in [('self_id_hex', 16), ('peer_id_hex', 16),
                        ('session_hex', 16), ('key_hex', 32)]:
        text = config[name]
        if len(text) != count * 2 or any(c not in '0123456789abcdefABCDEF' for c in text):
            raise ValueError('Invalid hexadecimal field: ' + name)
        raw = bytes.fromhex(text)
        if len(raw) != count or not any(raw):
            raise ValueError('Invalid or zero key/ID/session')
        config[name] = raw
    if config['self_id_hex'] == config['peer_id_hex']:
        raise ValueError('Sender/receiver IDs must differ')
    for key in ('listen_port', 'peer_port'):
        number = int(config[key], 10)
        if not 1024 <= number <= 65535:
            raise ValueError('Invalid UDP port')
        config[key] = number
    config['peer_ipv4'] = str(ipaddress.IPv4Address(config['peer_ipv4']))
    return config


def verify_pair(sender, receiver):
    """Cross-check the exact secrets and endpoint pairing WITHOUT revealing keys."""
    if sender['mode'] != 'sender' or receiver['mode'] != 'receiver':
        raise ValueError('Pair requires PC sender mode and iPhone receiver mode')
    checks = (
        sender['listen_port'] == receiver['peer_port'],
        sender['peer_port'] == receiver['listen_port'],
        hmac.compare_digest(sender['self_id_hex'], receiver['peer_id_hex']),
        hmac.compare_digest(sender['peer_id_hex'], receiver['self_id_hex']),
        hmac.compare_digest(sender['session_hex'], receiver['session_hex']),
        hmac.compare_digest(sender['key_hex'], receiver['key_hex']),
    )
    if not all(checks):
        raise ValueError('Configurations do NOT match: ports, identities, session or key')
    return True

def make_frame(kind, action, sequence, timestamp_ms, sender, target, session, nonce, key):
    if kind not in (KIND_ACTION, KIND_ACK, KIND_NATIVE) or not 0 < sequence < 2**64:
        raise ValueError('Invalid kind/sequence')
    if action != (1 if kind == KIND_ACTION else 0):
        raise ValueError('Only diagnostic PING supported')
    if not (len(sender) == len(target) == len(session) == 16
            and len(nonce) == 8 and len(key) == 32):
        raise ValueError('Invalid field lengths')
    head = (FRAME.pack(b'RBP1', 1, kind, action, sequence, timestamp_ms)
            + sender + target + session + nonce)
    assert len(head) == HEADER_SIZE
    return head + hmac.new(key, head, hashlib.sha256).digest()[:16]


def validate_response(data, address, peer, original, expected_kind, key):
    if address != peer or len(data) != WIRE_SIZE or not hmac.compare_digest(
            hmac.new(key, data[:80], hashlib.sha256).digest()[:16], data[80:]):
        return False
    magic, version, kind, action, seq, timestamp = FRAME.unpack(data[:24])
    if (magic != b'RBP1' or version != 1 or kind != expected_kind or action != 0
            or seq != original['seq'] or abs(now_ms() - timestamp) > MAX_SKEW_MS):
        return False
    return (hmac.compare_digest(data[24:40], original['target'])
            and hmac.compare_digest(data[40:56], original['sender'])
            and hmac.compare_digest(data[56:72], original['session'])
            and hmac.compare_digest(data[72:80], original['nonce']))


def exchange(config, delay=0.0, listen_seconds=12.0, quiet=False, ready=False):
    """Send exactly one signed action; retransmits reuse the IDENTICAL frame.

    ACK is only a queue receipt. NATIVE means remote game adapter invoked;
    neither proves visual gameplay, GTA ownership or RAGE replication.
    """
    peer = (config['peer_ipv4'], config['peer_port'])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', config['listen_port']))
        sock.settimeout(0.20)
        original = {'seq': 1, 'sender': config['self_id_hex'],
                    'target': config['peer_id_hex'], 'session': config['session_hex'],
                    'nonce': secrets.token_bytes(8)}
        if not quiet:
            print('PC bound UDP port', config['listen_port'], '-> iPhone', peer)
        if ready:
            if not quiet:
                print('Launch GTA E3 first. Press Enter immediately when the game is visible.')
            input('Press Enter to send the diagnostic PING: ')
        elif delay:
            if not quiet:
                print('Start GTA E3 now. Transmitting in', delay, 'seconds.')
            time.sleep(delay)
        # Generate timestamp AFTER startup wait. Reuse EXACT bytes for every
        # retry to avoid making a second action on the receiver game thread.
        frame = make_frame(KIND_ACTION, 1, original['seq'], now_ms(),
                           original['sender'], original['target'], original['session'],
                           original['nonce'], config['key_hex'])
        ack = native = False
        deadline = time.monotonic() + listen_seconds
        next_send = 0.0
        count = 0
        while time.monotonic() < deadline and not (ack and native):
            if time.monotonic() >= next_send:
                sock.sendto(frame, peer)
                count += 1
                next_send = time.monotonic() + 0.50
            try:
                packet, source = sock.recvfrom(512)
            except socket.timeout:
                continue
            if validate_response(packet, source, peer, original, KIND_ACK, config['key_hex']):
                if not ack and not quiet:
                    print('[PC_E3] ACK_VERIFIED seq=1 (queue only; NOT game display)')
                ack = True
            elif validate_response(packet, source, peer, original, KIND_NATIVE, config['key_hex']):
                if not native and not quiet:
                    print('[PC_E3] NATIVE_INVOCATION_REPORT_VERIFIED seq=1 (native API invoked, NOT RAGE sync)')
                native = True
            elif not quiet:
                print('[PC_E3] Ignored unauthenticated or unrelated packet')
        if not quiet:
            print(f'[PC_E3] Result: ACK={int(ack)} NATIVE_RECEIPT={int(native)} sends={count}')
            print('Diagnostic UDP only: NO RAGE multiplayer sender/session authentication proven.')
        return ack, native
    finally:
        sock.close()


def get_outbound_ipv4(destination):
    """Detect OS route selection without sending network packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((destination, 47881))  # UDP connect does not send a packet
        return s.getsockname()[0]

def main(argv=None):
    p = argparse.ArgumentParser(description='Desktop sender -> one iPhone E3; diagnostic PING only')
    p.add_argument('--config', type=Path, required=True, help='PC sender config generated by make_two_phone_configs.py')
    p.add_argument('--delay', type=float, default=None, help='Delay from PC startup before sending (default 10 unless --ready)')
    p.add_argument('--ready', action='store_true', help='Wait for Enter after opening GTA on iPhone; avoids 15s receive window race')
    p.add_argument('--iphone-config', type=Path, help='Optional paired receiver cfg for local validation (not sent to network)')
    p.add_argument('--listen-seconds', type=float, default=12.0)
    args = p.parse_args(argv)
    delay = (0.0 if args.ready else 10.0) if args.delay is None else args.delay
    if args.ready and delay:
        p.error('Use --ready OR --delay, not both')
    if not 0 <= delay <= 120 or not 1 <= args.listen_seconds <= 12:
        p.error('delay must be 0..120, listen-seconds 1..12 (15s timestamp skew)')
    try:
        config = parse_config(args.config)
        if args.iphone_config:
            phone = parse_config(args.iphone_config, required_mode='receiver')
            verify_pair(config, phone)
            routed_ip = get_outbound_ipv4(config['peer_ipv4'])
            if routed_ip != phone['peer_ipv4']:
                raise ValueError('PC would send from IPv4 ' + routed_ip +
                                 ', but iPhone allows ' + phone['peer_ipv4'] +
                                 '; check Wi-Fi vs VPN and regenerate paired configs')
            print('[PC_E3] Ports, IDs, key, session and outbound PC IPv4 match; no secrets printed.')
        success = exchange(config, delay=delay,
                           listen_seconds=args.listen_seconds, ready=args.ready)
    except (OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        print('E3 sender cannot start:', str(exc), file=sys.stderr)
        return 2
    return 0 if all(success) else 1


if __name__ == '__main__':
    raise SystemExit(main())
