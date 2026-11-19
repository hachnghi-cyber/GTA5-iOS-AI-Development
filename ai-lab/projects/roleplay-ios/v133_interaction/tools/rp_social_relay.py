"""Consent-scoped PRP3 notification relay for the private authority server."""
from dataclasses import dataclass
import struct

from prp3_direct_tls import ProtocolError, WIRE, u64

SOCIAL_REQUEST, SOCIAL_RESULT, SOCIAL_EVENT, SOCIAL_RECEIPT, SOCIAL_OPEN, SOCIAL_STATE = range(7, 13)
DENIED, RECEIVED, CANCELLED = range(1, 4)
RESULT = struct.Struct('!QB')
RECEIPT = struct.Struct('!QQ')
WORD = struct.Struct('!Q')
RECEIPT_TIMEOUT_MS = 3000


@dataclass
class Pending:
    sender: dict
    target: dict
    nonce: int
    expires_at: int


def decode_request(wire, session, epoch):
    if len(wire) != WIRE.size:
        raise ProtocolError('invalid PRP3 size')
    magic, version, kind, reserved, advertised_session, target, advertised_epoch, nonce = WIRE.unpack(wire)
    if ((magic, version, reserved, advertised_session, advertised_epoch) != (b'PRP3', 1, 0, session, epoch)
            or kind not in (1, 2) or not u64(target) or not u64(nonce)):
        raise ProtocolError('invalid PRP3 request')
    return kind, target, nonce


def decode_event(payload, session, epoch, recipient):
    if len(payload) != WORD.size + WIRE.size:
        raise ProtocolError('invalid social event size')
    sender, = WORD.unpack_from(payload)
    kind, target, nonce = decode_request(payload[WORD.size:], session, epoch)
    if not sender or sender == recipient or target != recipient:
        raise ProtocolError('invalid social participant')
    return sender, kind, nonce


class SocialRelay:
    """One outstanding request per authenticated sender. No GTA player binding."""
    def __init__(self, authority, peers, send):
        self.authority, self.peers, self.send = authority, peers, send
        self.pending, self.last_nonce = {}, {}

    def _eligible(self, peer):
        identity = peer['id']
        return (self.peers.get(identity) is peer and peer.get('social_open') and
                (row := self.authority.snapshot(identity)) is not None and row[2] == 1)

    def _finish(self, pending, outcome):
        identity = pending.sender['id']
        del self.pending[identity]
        if self.peers.get(identity) is pending.sender:
            self._result(pending.sender, pending.nonce, outcome)

    def _result(self, peer, nonce, outcome):
        if not self.send(peer, SOCIAL_RESULT, RESULT.pack(nonce, outcome)):
            # The normal writer/lease path owns socket disposal. Dropping an
            # output record here cannot turn a request into a confirmed receipt.
            peer['writer'].transport.abort()

    def tick(self, now):
        for pending in list(self.pending.values()):
            if now >= pending.expires_at or not self._eligible(pending.sender) or not self._eligible(pending.target):
                self._finish(pending, CANCELLED)

    def handle(self, peer, kind, payload, now):
        identity = peer['id']
        if kind == SOCIAL_OPEN:
            if payload or peer.get('social_open'):
                raise ProtocolError('invalid social open')
            peer['social_open'] = True
            if not self.send(peer, SOCIAL_STATE, WORD.pack(self.last_nonce.get(identity, 0))):
                raise ProtocolError('slow client')
            return
        if not peer.get('social_open'):
            raise ProtocolError('social channel not open')
        if kind == SOCIAL_RECEIPT:
            if len(payload) != RECEIPT.size:
                raise ProtocolError('invalid social receipt size')
            actor, nonce = RECEIPT.unpack(payload)
            pending = self.pending.get(actor)
            if pending is not None and pending.target is peer and pending.nonce == nonce:
                valid = now < pending.expires_at and self._eligible(pending.sender) and self._eligible(peer)
                self._finish(pending, RECEIVED if valid else CANCELLED)
            return  # Late or unrelated receipts cannot confirm another request.
        if kind != SOCIAL_REQUEST:
            raise ProtocolError('invalid client social record')

        _, target_id, nonce = decode_request(payload, self.authority.session, self.authority.epoch)
        if nonce <= self.last_nonce.get(identity, 0) or identity in self.pending:
            raise ProtocolError('replayed or overlapping social request')
        self.last_nonce[identity] = nonce
        target = self.peers.get(target_id)
        if (not target or target is peer or not self._eligible(peer) or not self._eligible(target) or
                not self.send(target, SOCIAL_EVENT, WORD.pack(identity) + payload)):
            self._result(peer, nonce, DENIED)
            return
        self.pending[identity] = Pending(peer, target, nonce, now + RECEIPT_TIMEOUT_MS)
