"""Independent two-peer PRP3 transport reference. No GTA runtime integration."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path
import socket
import ssl
import struct
import threading
import time

ALPN = "prp3-pair/1"
HELLO = struct.Struct(">8sQQQQ")
HELLO_MAGIC = b"PRP3TLS1"
WIRE = struct.Struct("<4sBBHQQQQ")
TIMEOUT = 5.0


class ProtocolError(ValueError):
    """Rejects a frame or a peer that does not match local pairing."""


def u64(value):
    return type(value) is int and 0 < value < 1 << 64


@dataclass(frozen=True)
class Pairing:
    local_id: int
    peer_id: int
    session_id: int
    epoch: int
    peer_cert_sha256: bytes

    def __post_init__(self):
        if not all(u64(value) for value in
                   (self.local_id, self.peer_id, self.session_id, self.epoch)):
            raise ValueError("pairing IDs and generation must be nonzero uint64 values")
        if self.local_id == self.peer_id:
            raise ValueError("self pairing is invalid")
        if type(self.peer_cert_sha256) is not bytes or len(self.peer_cert_sha256) != 32:
            raise ValueError("peer certificate pin must be a 32-byte SHA-256 digest")

    def hello(self, local_id, peer_id):
        return HELLO.pack(HELLO_MAGIC, local_id, peer_id, self.session_id, self.epoch)


@dataclass(frozen=True)
class Credentials:
    certificate: Path
    private_key: Path
    trusted_ca: Path

    def context(self, server_side):
        purpose = ssl.PROTOCOL_TLS_SERVER if server_side else ssl.PROTOCOL_TLS_CLIENT
        ctx = ssl.SSLContext(purpose)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=self.trusted_ca)
        ctx.load_cert_chain(self.certificate, self.private_key)
        ctx.set_alpn_protocols([ALPN])
        if server_side:
            ctx.num_tickets = 0
        return ctx


@dataclass(frozen=True)
class Received:
    # This identity is scoped to the dedicated RP pairing, not an engine player ID.
    rp_sender: int
    rp_session: int
    rp_epoch: int
    wire: bytes


def read_exact(channel, size):
    chunks = bytearray()
    deadline = time.monotonic() + TIMEOUT
    while len(chunks) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("receive deadline elapsed")
        channel.settimeout(remaining)
        chunk = channel.recv(size - len(chunks))
        if not chunk:
            raise EOFError("peer closed before the fixed-size record arrived")
        chunks.extend(chunk)
    return bytes(chunks)


def validate_frame(wire, pairing, receiver, last_nonce):
    if type(wire) is not bytes or len(wire) != WIRE.size:
        raise ProtocolError("expected one 40-byte PRP3 frame")
    magic, version, kind, reserved, session, target, epoch, nonce = WIRE.unpack(wire)
    if (magic, version, reserved) != (b"PRP3", 1, 0) or kind not in (1, 2):
        raise ProtocolError("unsupported PRP3 frame")
    if (session, target, epoch) != (pairing.session_id, receiver, pairing.epoch):
        raise ProtocolError("wrong RP session, target or generation")
    if nonce <= last_nonce:
        raise ProtocolError("duplicate or out-of-order nonce")
    return nonce


class PeerChannel:
    """Synchronous, single-owner TLS channel. Use only within PeerSession.open."""

    def __init__(self, session, sock):
        self._session = session
        self._sock = sock

    def send(self, wire):
        if self._sock.fileno() < 0:
            raise ProtocolError("channel is closed")
        session = self._session
        pairing = session.pairing
        nonce = validate_frame(wire, pairing, pairing.peer_id, session._sent_nonce)
        self._sock.settimeout(TIMEOUT)
        # A partial send may have reached the receiver. A retry needs a new nonce.
        session._sent_nonce = nonce
        try:
            self._sock.sendall(wire)
        except OSError:
            self._sock.close()
            raise

    def receive(self):
        session = self._session
        pairing = session.pairing
        try:
            wire = read_exact(self._sock, WIRE.size)
            session._received_nonce = validate_frame(
                wire, pairing, pairing.local_id, session._received_nonce)
        except (OSError, EOFError, ProtocolError):
            self._sock.close()
            raise
        return Received(pairing.peer_id, pairing.session_id, pairing.epoch, wire)


class PeerSession:
    """One configured pairing/generation with replay state across reconnects.

    Keep this object alive for the lifetime of the generation. Rotate session
    or generation on process restart before accepting traffic again.
    """

    def __init__(self, pairing, credentials):
        self._pairing = pairing
        self._credentials = credentials
        self._sent_nonce = 0
        self._received_nonce = 0
        self._open_lock = threading.Lock()

    @property
    def pairing(self):
        return self._pairing

    @contextmanager
    def open(self, raw, *, server_side, peer_hostname=None):
        """Take ownership of a connected TCP socket and authenticate the peer."""
        with raw:
            if not server_side and not peer_hostname:
                raise ValueError("client requires the configured TLS DNS name")
            if not self._open_lock.acquire(blocking=False):
                raise ProtocolError("another channel is open in this generation")
            try:
                raw.settimeout(TIMEOUT)
                ctx = self._credentials.context(server_side)
                with ctx.wrap_socket(raw, server_side=server_side,
                                     server_hostname=peer_hostname) as channel:
                    certificate = channel.getpeercert(binary_form=True)
                    pairing = self.pairing
                    if (channel.version() != "TLSv1.3" or
                            channel.selected_alpn_protocol() != ALPN or
                            not certificate or not hmac.compare_digest(
                                hashlib.sha256(certificate).digest(), pairing.peer_cert_sha256)):
                        raise ProtocolError("peer certificate or TLS protocol does not match pairing")
                    channel.settimeout(TIMEOUT)
                    channel.sendall(pairing.hello(pairing.local_id, pairing.peer_id))
                    if read_exact(channel, HELLO.size) != pairing.hello(pairing.peer_id, pairing.local_id):
                        raise ProtocolError("peer session, generation or identity does not match pairing")
                    yield PeerChannel(self, channel)
            finally:
                self._open_lock.release()
