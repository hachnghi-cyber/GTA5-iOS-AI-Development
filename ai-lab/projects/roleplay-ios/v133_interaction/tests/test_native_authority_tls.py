"""Compile-owned C client codec talking to the private server over real TLS.

The Network.framework wrapper still requires macOS/iPhone verification.
"""
import asyncio
import ctypes as C
import hashlib
import hmac
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import rp_private_server as rp
import test_rp_private_server as hosttests

COP, CITIZEN = hosttests.COP, hosttests.CITIZEN


class NativeClient:
    def __init__(self, library, reader, writer, identity):
        self.lib = C.CDLL(library)
        ptr, size, u64, u8 = C.c_void_p, C.c_size_t, C.c_uint64, C.c_uint8
        signatures = {
            'create': (ptr, [u64]), 'destroy': (None, [ptr]),
            'receive': (C.c_int, [ptr, C.POINTER(u8), size, C.POINTER(u8), size]),
            'request': (C.c_int, [ptr, C.c_uint32, u64, C.POINTER(u8), size]),
            'row': (C.c_int, [ptr, u64, C.POINTER(u64), size]),
            'revision': (u64, [ptr]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.lib, 'test_client_' + name)
            function.restype, function.argtypes = result, args
        self.handle = self.lib.test_client_create(identity)
        if not self.handle:
            raise ValueError('C client initialization failed')
        self.reader, self.writer, self.identity = reader, writer, identity

    async def receive(self):
        kind, payload = await rp.read_record(self.reader, 3)
        header = (C.c_uint8 * 5).from_buffer_copy(rp.HEADER.pack(kind, len(payload)))
        body = (C.c_uint8 * len(payload)).from_buffer_copy(payload)
        if not self.lib.test_client_receive(self.handle, header, 5, body, len(payload)):
            raise ValueError('native codec rejected actual server record')
        return kind, payload

    async def request(self, operation, target=None):
        wire = (C.c_uint8 * 45)()
        if not self.lib.test_client_request(self.handle, operation,
                                            self.identity if target is None else target, wire, 45):
            raise ValueError('native client rejected local request')
        self.writer.write(bytes(wire))
        await self.writer.drain()
        async with asyncio.timeout(3):
            while True:
                kind, payload = await self.receive()
                if kind == rp.ACK:
                    return payload[6]

    def row(self, identity):
        row = (C.c_uint64 * 10)()
        return tuple(row) if self.lib.test_client_row(self.handle, identity, row, 10) else None

    async def close(self):
        self.writer.transport.abort()
        if self.handle:
            self.lib.test_client_destroy(self.handle)
            self.handle = None
        try:
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        except (OSError, TimeoutError):
            pass


class NativeAuthorityTLSTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(hosttests.PrivateServerTests.setUpClass.__func__)
    running = hosttests.PrivateServerTests.running

    async def connect(self, address, label, identity):
        reader, writer = await asyncio.open_connection(*address,
                         ssl=rp.context(self.credentials[label], False), server_hostname='127.0.0.1')
        secure = writer.get_extra_info('ssl_object')
        self.assertEqual(secure.version(), 'TLSv1.3')
        self.assertEqual(secure.selected_alpn_protocol(), rp.ALPN)
        self.assertTrue(hmac.compare_digest(hashlib.sha256(secure.getpeercert(binary_form=True)).digest(), self.pins['server']))
        try:
            client = NativeClient(self.library, reader, writer, identity)
        except BaseException:
            writer.transport.abort()
            await asyncio.wait_for(writer.wait_closed(), 1)
            raise
        self.addAsyncCleanup(client.close)
        self.assertEqual((await client.receive())[0], rp.WELCOME)
        return client

    async def wait_row(self, client, identity, check):
        async with asyncio.timeout(3):
            while not check(client.row(identity)):
                await client.receive()

    async def test_native_codec_two_clients_full_cycle(self):
        async with self.running(hosttests.SyntheticScene()) as (_, address):
            cop = await self.connect(address, 'cop', COP)
            citizen = await self.connect(address, 'citizen', CITIZEN)
            self.assertEqual(await cop.request(1), 2)
            self.assertEqual(await citizen.request(1), 2)
            self.assertEqual(await cop.request(3), 2)
            for operation, custody in ((5, 1), (7, 2), (9, 3), (10, 1), (11, 4), (12, 0)):
                self.assertEqual(await cop.request(operation, CITIZEN), 2)
                for client in (cop, citizen):
                    await self.wait_row(client, CITIZEN, lambda row: row is not None and row[4] == custody)
                self.assertEqual(cop.row(CITIZEN), citizen.row(CITIZEN))
                self.assertEqual(cop.lib.test_client_revision(cop.handle), citizen.lib.test_client_revision(citizen.handle))
            self.assertEqual(await citizen.request(2), 2)
            self.assertEqual(await cop.request(5, CITIZEN), 1)

    async def test_native_codec_default_fails_closed_and_reconnect_resumes_nonce(self):
        async with self.running() as (_, address):
            cop = await self.connect(address, 'cop', COP)
            citizen = await self.connect(address, 'citizen', CITIZEN)
            self.assertEqual(await cop.request(1), 2)
            self.assertEqual(await cop.request(3), 1)
            await cop.close()
            await self.wait_row(citizen, COP, lambda row: row is None)
            # Make sure the authority has processed the disconnect, rather than
            # accepting the client's initially-empty snapshot as evidence.
            await citizen.request(1)
            await self.wait_row(citizen, COP, lambda row: row is None)
            replacement = await self.connect(address, 'cop', COP)
            self.assertEqual(await replacement.request(1), 2)
            await self.wait_row(replacement, COP, lambda row: row is not None and row[9] == 3)


if __name__ == '__main__':
    unittest.main()
