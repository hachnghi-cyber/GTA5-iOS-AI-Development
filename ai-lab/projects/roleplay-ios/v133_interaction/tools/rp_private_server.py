"""Private mTLS RP authority. It does not replace GTA session networking.

One asyncio event loop owns the C world. RP IDs come only from certificate
pins in the operator registry. The default server has no trusted game facts,
so duty/custody actions fail closed; opt-in/out and replication remain usable.
"""
import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import struct
import time

from prp3_direct_tls import Credentials, ProtocolError, u64
from rp_private_authority import COMMAND, NativeAuthority
from rp_social_relay import SOCIAL_OPEN, SOCIAL_RECEIPT, SOCIAL_REQUEST, SocialRelay

ALPN = 'police-rp-authority/1'
HEADER = struct.Struct('!BI')
HELLO = struct.Struct('!8sQQQQ')
SCOPE = struct.Struct('!QQQ')
ROW = struct.Struct('!10Q')
WELCOME, REQUEST, ACK, SNAPSHOT, PING, PONG = range(1, 7)
MAX_RECORD = 4096
CAPACITY = 32


@dataclass(frozen=True)
class Principal:
    rp_id: int
    role: int


def registry_from_json(entries):
    result = {}
    for entry in entries:
        if set(entry) != {'certificate_sha256', 'rp_id', 'role'}:
            raise ValueError('registry entry has unknown or missing fields')
        pin = bytes.fromhex(entry['certificate_sha256'])
        if pin in result:
            raise ValueError('duplicate certificate')
        result[pin] = Principal(entry['rp_id'], entry['role'])
    validate_registry(result)
    return result


def validate_registry(registry):
    ids = set()
    if not 0 < len(registry) <= CAPACITY:
        raise ValueError('registry must contain 1..32 principals')
    for pin, principal in registry.items():
        if (type(pin) is not bytes or len(pin) != 32 or
                not u64(principal.rp_id) or type(principal.role) is not int or
                principal.role not in (1, 2) or principal.rp_id in ids):
            raise ValueError('invalid pin, role or duplicate RP identity')
        ids.add(principal.rp_id)


def context(credentials, server_side):
    result = credentials.context(server_side)
    result.set_alpn_protocols([ALPN])
    return result


def record(kind, payload=b''):
    if len(payload) > MAX_RECORD:
        raise ProtocolError('oversized record')
    return HEADER.pack(kind, len(payload)) + payload


async def read_record(reader, timeout):
    # One deadline covers both header and body, including trickled bytes.
    async with asyncio.timeout(timeout):
        kind, size = HEADER.unpack(await reader.readexactly(HEADER.size))
        if size > MAX_RECORD:
            raise ProtocolError('oversized record')
        return kind, await reader.readexactly(size)


class PrivateServer:
    def __init__(self, credentials, registry, authority, *, lease_seconds=15.0):
        validate_registry(registry)
        if not 0.1 <= lease_seconds <= 60:
            raise ValueError('lease must be between 0.1 and 60 seconds')
        self.credentials, self.registry, self.authority = credentials, dict(registry), authority
        self.lease = lease_seconds
        self.peers, self.tasks = {}, set()
        self.social = SocialRelay(authority, self.peers, self._enqueue)
        self.revision, self._rows = 0, None
        self.listener = self.timer = None
        self.stopping = False

    @staticmethod
    def now():
        return time.monotonic_ns() // 1_000_000

    async def start(self, host='127.0.0.1', port=0):
        if self.listener or self.stopping:
            raise RuntimeError('server cannot be restarted with old replay state')
        self.listener = await asyncio.start_server(
            self._handle, host, port, ssl=context(self.credentials, True),
            ssl_handshake_timeout=3, ssl_shutdown_timeout=1, limit=8192, backlog=32)
        self.timer = asyncio.create_task(self._timer())
        return self.listener.sockets[0].getsockname()[:2]

    def _enqueue(self, peer, kind, payload=b''):
        try:
            peer['out'].put_nowait(record(kind, payload))
            return True
        except asyncio.QueueFull:
            return False

    def _publish(self, *, force=None):
        rows = b''.join(ROW.pack(*row) for identity in sorted(self.peers)
                        if (row := self.authority.snapshot(identity)) is not None)
        if rows != self._rows:
            self._rows = rows
            self.revision += 1
            targets = list(self.peers.values())
        else:
            targets = [force] if force is not None else []
        payload = SCOPE.pack(self.authority.session, self.authority.epoch, self.revision) + rows
        failed = []
        for peer in targets:
            if self.peers.get(peer['id']) is peer:
                if not self._enqueue(peer, SNAPSHOT, payload):
                    failed.append(peer)
        # Finish enqueueing this revision before a drop publishes a newer one.
        for peer in failed:
            self._drop(peer)

    def _drop(self, peer):
        if self.peers.get(peer['id']) is peer:
            del self.peers[peer['id']]
            self.authority.leave(peer['id'])
            # Abort promptly: a silent/slow peer cannot retain consent or custody.
            peer['writer'].transport.abort()
            self.social.tick(self.now())
            self._publish()

    async def _sender(self, peer):
        try:
            while True:
                peer['writer'].write(await peer['out'].get())
                await asyncio.wait_for(peer['writer'].drain(), self.lease)
        except (OSError, TimeoutError, ConnectionError):
            self._drop(peer)

    async def _handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        peer = sender = None
        try:
            secure = writer.get_extra_info('ssl_object')
            if self.stopping or not secure or secure.version() != 'TLSv1.3' or secure.selected_alpn_protocol() != ALPN:
                raise ProtocolError('unsupported TLS protocol')
            certificate = secure.getpeercert(binary_form=True)
            principal = self.registry.get(hashlib.sha256(certificate).digest()) if certificate else None
            if principal is None or principal.rp_id in self.peers:
                raise ProtocolError('unregistered certificate or duplicate connection')
            if not self.authority.admit(principal.rp_id, principal.role):
                raise ProtocolError('authority admission failed')
            peer = {'id': principal.rp_id, 'writer': writer, 'out': asyncio.Queue(maxsize=32)}
            self.peers[principal.rp_id] = peer
            sender = asyncio.create_task(self._sender(peer))
            previous_nonce = self.authority.snapshot(principal.rp_id)[9]
            self._enqueue(peer, WELCOME, HELLO.pack(b'PRPSRV01', principal.rp_id,
                          self.authority.session, self.authority.epoch, previous_nonce))
            self._publish(force=peer)
            tokens, replenished = 60.0, time.monotonic()
            while self.peers.get(principal.rp_id) is peer:
                kind, payload = await read_record(reader, self.lease)
                current = time.monotonic()
                tokens = min(60.0, tokens + (current - replenished) * 30) - 1
                replenished = current
                if tokens < 0:
                    raise ProtocolError('rate limit exceeded')
                if kind == PING and not payload:
                    if not self._enqueue(peer, PONG):
                        raise ProtocolError('slow client')
                elif kind == REQUEST and len(payload) == COMMAND.size:
                    now = self.now()
                    ack = self.authority.dispatch(principal.rp_id, now, payload)
                    if ack is None:
                        raise ProtocolError('invalid transaction or replay')
                    if not self._enqueue(peer, ACK, ack):
                        raise ProtocolError('slow client')
                    self.social.tick(now)
                    self._publish()
                elif kind in (SOCIAL_OPEN, SOCIAL_REQUEST, SOCIAL_RECEIPT):
                    self.social.handle(peer, kind, payload, self.now())
                else:
                    raise ProtocolError('unknown record or invalid request size')
        except (OSError, EOFError, asyncio.IncompleteReadError, ProtocolError, TimeoutError):
            pass  # Do not echo credentials, raw requests or peer addresses into logs.
        finally:
            if peer is not None:
                self._drop(peer)
            if sender:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, TimeoutError):
                writer.transport.abort()
            self.tasks.discard(task)

    async def _timer(self):
        while True:
            await asyncio.sleep(0.05)
            if not self.authority.tick(self.now()):
                raise RuntimeError('authority clock failed')
            self.social.tick(self.now())
            self._publish()

    async def close(self):
        self.stopping = True
        if self.listener:
            self.listener.close()
            await self.listener.wait_closed()
        if self.timer:
            self.timer.cancel()
            await asyncio.gather(self.timer, return_exceptions=True)
        for peer in list(self.peers.values()):
            self._drop(peer)
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class PrivateClient:
    """Single reader host reference. Send a PING within each lease when idle."""
    def __init__(self, reader, writer, identity, session, epoch, last_nonce):
        self.reader, self.writer = reader, writer
        self.identity, self.session, self.epoch = identity, session, epoch
        self.nonce = last_nonce
        self.revision, self.members = 0, {}
        self.closed = False

    def _invalidate(self):
        self.closed = True
        self.revision, self.members = 0, {}
        self.writer.transport.abort()

    @classmethod
    async def connect(cls, address, credentials, server_pin, identity, hostname='127.0.0.1'):
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            *address, ssl=context(credentials, False), server_hostname=hostname,
            ssl_handshake_timeout=3, ssl_shutdown_timeout=1, limit=8192), 5)
        try:
            secure = writer.get_extra_info('ssl_object')
            certificate = secure.getpeercert(binary_form=True)
            if (secure.version() != 'TLSv1.3' or secure.selected_alpn_protocol() != ALPN or
                    not certificate or not hmac.compare_digest(hashlib.sha256(certificate).digest(), server_pin)):
                raise ProtocolError('server certificate or ALPN mismatch')
            kind, payload = await read_record(reader, 5)
            if kind != WELCOME or len(payload) != HELLO.size:
                raise ProtocolError('missing welcome')
            magic, actual_id, session, epoch, last_nonce = HELLO.unpack(payload)
            if magic != b'PRPSRV01' or actual_id != identity or not all(map(u64, (actual_id, session, epoch))):
                raise ProtocolError('wrong welcome identity or scope')
            return cls(reader, writer, identity, session, epoch, last_nonce)
        except BaseException:
            writer.transport.abort()
            raise

    async def receive(self):
        try:
            if self.closed:
                raise ProtocolError('client is disconnected')
            return await self._receive()
        except BaseException:
            self._invalidate()
            raise

    async def _receive(self):
        kind, payload = await read_record(self.reader, 5)
        if kind == SNAPSHOT:
            if len(payload) < SCOPE.size or (len(payload) - SCOPE.size) % ROW.size:
                raise ProtocolError('invalid snapshot size')
            session, epoch, revision = SCOPE.unpack_from(payload)
            if (session, epoch) != (self.session, self.epoch) or not revision or revision < self.revision:
                raise ProtocolError('stale snapshot or wrong scope')
            members = dict((row[0], row) for row in ROW.iter_unpack(payload[SCOPE.size:]))
            if (len(members) > CAPACITY or len(members) != (len(payload) - SCOPE.size) // ROW.size or
                    any(not row[0] or row[1] not in (1, 2) or row[2] not in (0, 1) or
                        row[3] not in (0, 1) or row[4] > 4 for row in members.values())):
                raise ProtocolError('invalid snapshot members')
            self.revision, self.members = revision, members
        return kind, payload

    async def send(self, kind, payload=b''):
        try:
            if self.closed:
                raise ProtocolError('client is disconnected')
            self.writer.write(record(kind, payload))
            await asyncio.wait_for(self.writer.drain(), 5)
        except BaseException:
            self._invalidate()
            raise

    def command(self, operation, target=None, nonce=None):
        if self.closed:
            raise ProtocolError('client is disconnected')
        if nonce is None:
            self.nonce += 1
            nonce = self.nonce
        return COMMAND.pack(b'PRPC', 1, operation, 0, self.session,
                            self.identity if target is None else target, self.epoch, nonce)

    async def transact(self, wire):
        try:
            async with asyncio.timeout(5):
                return await self._transact(wire)
        except BaseException:
            # Partial sends and cancelled ACK waits are ambiguous. Reconnect;
            # never continue on a stream containing an unconsumed old ACK.
            self._invalidate()
            raise

    async def _transact(self, wire):
        await self.send(REQUEST, wire)
        while True:
            kind, payload = await self.receive()
            if kind == ACK:
                if (len(payload) != 40 or payload[:4] != b'PRPA' or
                        payload[4:6] != wire[4:6] or payload[6] not in (1, 2) or
                        payload[7] or payload[8:] != wire[8:]):
                    raise ProtocolError('ACK does not match pending transaction')
                return payload
            if kind not in (SNAPSHOT, PONG):
                raise ProtocolError('unexpected server record')

    async def close(self):
        self._invalidate()
        try:
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        except (OSError, TimeoutError):
            self.writer.transport.abort()


async def serve(args):
    config = json.loads(args.config.read_text(encoding='utf-8'))
    root = args.config.resolve().parent
    credentials = Credentials(*(root / config[name] for name in ('certificate', 'private_key', 'trusted_ca')))
    registry = registry_from_json(config['principals'])
    # Fresh random scope after every restart invalidates old commands without a replay DB.
    authority = NativeAuthority(args.library, secrets.randbits(64) or 1, secrets.randbits(64) or 1)
    server = PrivateServer(credentials, registry, authority)
    try:
        address = await server.start(args.host, args.port)
        print(json.dumps({'listening': list(address), 'principals': len(registry),
                          'game_observations': False, 'protocol': ALPN}), flush=True)
        async with server.listener:
            await server.listener.serve_forever()
    finally:
        await server.close()
        authority.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=30133)
    try:
        asyncio.run(serve(parser.parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
