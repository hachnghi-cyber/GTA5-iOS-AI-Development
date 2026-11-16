"""RBP1 test-only roleplay transport envelope. No GTA/RAGE calls.

Wire big-endian, 96 bytes: header 80 + HMAC-SHA256[:16].
Authenticated identities are scoped to a configured key per trusted peer.  
The game session label is a binding input, NOT proof of RAGE membership.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import hmac
import secrets
import struct
import time

MAGIC = b'RBP1'
VERSION = 1
ACTION = 1
ACK = 2
PING = 1      # NO GAMEPLAY ACTION: a diagnostic event code
FORMAT = struct.Struct('!4sBBHQQ16s16s16s8s')
FRAME_BYTES = FORMAT.size + 16
assert FORMAT.size == 80 and FRAME_BYTES == 96

class InvalidFrame(ValueError):
    pass

@dataclass(frozen=True)
class Frame:
    kind: int
    action: int
    sequence: int
    timestamp_ms: int
    sender: bytes
    target: bytes
    session: bytes
    nonce: bytes

    def __post_init__(self):
        for field in ('sender','target','session'):
            if not isinstance(getattr(self, field), bytes) or len(getattr(self, field)) != 16:
                raise ValueError(field + ' must be exactly 16 bytes')
        if not isinstance(self.nonce, bytes) or len(self.nonce) != 8:
            raise ValueError('nonce must be 8 bytes')
        if not (0 <= self.sequence < 2**64 and 0 <= self.timestamp_ms < 2**64):
            raise ValueError('invalid sequence/timestamp')
        if self.kind not in (ACTION, ACK) or self.action not in (0, PING):
            raise ValueError('unsupported event')
        if self.kind == ACTION and self.action != PING:
            raise ValueError('only diagnostic PING allowed in this version')
        if self.kind == ACK and self.action != 0:
            raise ValueError('ACK must not specify an action')

    def encode(self, key: bytes) -> bytes:
        if len(key) < 32:
            raise ValueError('per-peer key must be >=32 random bytes')
        header = FORMAT.pack(MAGIC, VERSION, self.kind, self.action,
                             self.sequence, self.timestamp_ms,
                             self.sender, self.target, self.session, self.nonce)
        return header + hmac.new(key, header, hashlib.sha256).digest()[:16]

    @classmethod
    def decode(cls, packet: bytes, key: bytes) -> 'Frame':
        if len(key) < 32 or len(packet) != FRAME_BYTES:
            raise InvalidFrame('key length / frame length invalid')
        header, mac = packet[:FORMAT.size], packet[FORMAT.size:]
        if not hmac.compare_digest(hmac.new(key, header, hashlib.sha256).digest()[:16], mac):
            raise InvalidFrame('bad MAC')
        magic, v, kind, action, seq, ts, sender, target, sess, nonce = FORMAT.unpack(header)
        if magic != MAGIC or v != VERSION:
            raise InvalidFrame('magic/version mismatch')
        try:
            return cls(kind, action, seq, ts, sender, target, sess, nonce)
        except ValueError as exc:
            raise InvalidFrame(str(exc)) from exc


def id16(label: str) -> bytes:
    """Only for host test fixtures. NOT a cryptographic player identity."""
    return hashlib.sha256(label.encode('utf8')).digest()[:16]


def test_frame(sender: bytes, target: bytes, session: bytes, sequence: int) -> Frame:
    return Frame(ACTION, PING, sequence, int(time.time()*1000), sender, target,
                 session, secrets.token_bytes(8))

class Receiver:
    """Per authenticated peer state; separate from the game entity/ownership state."""
    def __init__(self, *, self_id: bytes, allowed_sender: bytes,
                 session: bytes, per_peer_key: bytes, max_skew_ms: int = 15000):
        self.self_id, self.allowed_sender, self.session = self_id, allowed_sender, session
        self.key = per_peer_key
        self.skew_ms = max_skew_ms
        self.highest = -1
        self.last_nonce = b''

    def accept(self, packet: bytes, *, now_ms: int | None = None):
        f = Frame.decode(packet, self.key)
        if f.target != self.self_id or f.sender != self.allowed_sender or f.session != self.session:
            raise InvalidFrame('peer / destination / session binding invalid')
        if f.kind != ACTION or f.action != PING:
            raise InvalidFrame('unsupported request')
        if now_ms is None:
            now_ms = int(time.time()*1000)
        if abs(now_ms-f.timestamp_ms) > self.skew_ms:
            raise InvalidFrame('expired or clock skew')
        if f.sequence == self.highest and f.nonce == self.last_nonce:
            return 'DUPLICATE', f  # ACK again but do not dispatch twice
        if f.sequence <= self.highest:
            raise InvalidFrame('replayed or out-of-order')
        self.highest = f.sequence
        self.last_nonce = f.nonce
        return 'ACCEPTED_DIAGNOSTIC_EVENT_ONLY', f


def make_ack(frame: Frame, receiver_id: bytes, *, now_ms: int | None = None) -> Frame:
    return Frame(ACK, 0, frame.sequence,
                 now_ms if now_ms is not None else int(time.time()*1000),
                 receiver_id, frame.sender, frame.session, frame.nonce)


def ack_matches(ack_packet: bytes, sent: Frame, key: bytes, receiver_id: bytes, now_ms: int | None = None) -> bool:
    ack = Frame.decode(ack_packet, key)
    if now_ms is None:
        now_ms = int(time.time()*1000)
    return bool(ack.kind == ACK and ack.action == 0 and
                ack.sequence == sent.sequence and ack.nonce == sent.nonce and
                ack.sender == receiver_id and ack.target == sent.sender and
                ack.session == sent.session and abs(now_ms - ack.timestamp_ms) <= 15000)
