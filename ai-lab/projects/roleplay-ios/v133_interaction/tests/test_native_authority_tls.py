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
import rp_social_relay as social
from rp_private_client import SocialClient
import test_rp_private_server as hosttests
from run_private_rp_iphone_check import STEPS, watch

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
            'consent_step': (C.c_int, [ptr, C.POINTER(C.c_uint32), C.POINTER(u8), size]),
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

    async def test_native_social_greet_and_documents_via_private_server(self):
        async with self.running() as (_, address):
            phone = await self.connect(address, 'cop', COP)
            host = await hosttests.PrivateServerTests.connect(self, address, 'citizen')
            civilian = SocialClient(host)
            await civilian.open()
            self.assertEqual(await phone.request(1), 2)
            await hosttests.PrivateServerTests.apply(self, host, hosttests.OPT_IN)
            ptr, u8_ptr, size = C.c_void_p, C.POINTER(C.c_uint8), C.c_size_t
            lib = phone.lib
            for name, result, args in (
                ('open', ptr, [ptr, u8_ptr, size]), ('destroy', None, [ptr]),
                ('request', C.c_int, [ptr, C.c_uint32, C.c_uint64, u8_ptr, size]),
                ('receive', C.c_int, [ptr, C.c_uint8, u8_ptr, size, u8_ptr, size]),
            ):
                method = getattr(lib, 'test_social_' + name)
                method.restype, method.argtypes = result, args
            opening = (C.c_uint8 * 5)()
            handle = lib.test_social_open(phone.handle, opening, len(opening))
            self.assertTrue(handle)
            self.addCleanup(lib.test_social_destroy, handle)

            async def send_native(frame):
                phone.writer.write(bytes(frame))
                await phone.writer.drain()

            async def receive_native(expected):
                async with asyncio.timeout(3):
                    while True:
                        kind, payload = await rp.read_record(phone.reader, 3)
                        if kind == expected:
                            body = (C.c_uint8 * len(payload)).from_buffer_copy(payload)
                            receipt = (C.c_uint8 * 21)()
                            self.assertTrue(lib.test_social_receive(handle, kind, body, len(payload), receipt, 21))
                            return body, receipt
                        self.assertEqual(kind, rp.SNAPSHOT)

            receive_host = hosttests.PrivateServerTests.receive_kind
            await send_native(opening)
            await receive_native(social.SOCIAL_STATE)
            await civilian.request(1, COP)
            _, receipt = await receive_native(social.SOCIAL_EVENT)
            await send_native(receipt)
            result = await receive_host(self, host, social.SOCIAL_RESULT)
            self.assertEqual((await civilian.consume(social.SOCIAL_RESULT, result))['interaction_result'], 'recipient_received')

            documents = (C.c_uint8 * 45)()
            self.assertTrue(lib.test_social_request(handle, 2, CITIZEN, documents, len(documents)))
            await send_native(documents)
            event = await receive_host(self, host, social.SOCIAL_EVENT)
            self.assertEqual(await civilian.consume(social.SOCIAL_EVENT, event),
                             {'interaction': 'documents', 'rp_sender': COP})
            result, _ = await receive_native(social.SOCIAL_RESULT)
            self.assertEqual(result[8], social.RECEIVED)

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

    async def test_phone_consent_probe_round_trip_with_host_witness(self):
        async with self.running() as (_, address):
            host = await self.connect(address, 'citizen', CITIZEN)
            phone_codec = await self.connect(address, 'cop', COP)
            phase = C.c_uint32()
            observed_consents = []
            async with asyncio.timeout(3):
                while True:
                    await phone_codec.receive()
                    wire = (C.c_uint8 * 45)()
                    outcome = phone_codec.lib.test_client_consent_step(phone_codec.handle, C.byref(phase), wire, 45)
                    self.assertIn(outcome, (0, 1, 2))
                    if outcome == 2:
                        break
                    if outcome == 1:
                        expected = int(phase.value == 2)
                        await self.wait_row(host, COP, lambda row: row is not None and row[2] == expected)
                        observed_consents.append(host.row(COP)[2])
                        phone_codec.writer.write(bytes(wire))
                        await phone_codec.writer.drain()
            await self.wait_row(host, COP, lambda row: row is not None and row[2] == 0)
            self.assertEqual(observed_consents + [host.row(COP)[2]], [0, 1, 0])
            self.assertEqual(phone_codec.row(COP), host.row(COP))
            await phone_codec.close()
            await self.wait_row(host, COP, lambda row: row is None)

    async def test_lan_witness_requires_full_sequence_before_reporting_pass(self):
        async with self.running() as (_, address):
            witness = await hosttests.PrivateServerTests.connect(self, address, 'citizen')
            stages = []
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(asyncio.wait_for(watch(witness, COP, stages.append), 5))
                phone = await self.connect(address, 'cop', COP)
                self.assertEqual(await phone.request(1), 2)
                self.assertEqual(await phone.request(2), 2)
                await phone.close()
            self.assertEqual(stages, list(STEPS))

    async def test_lan_witness_rejects_disconnect_after_only_opt_in(self):
        async with self.running() as (_, address):
            witness = await hosttests.PrivateServerTests.connect(self, address, 'citizen')
            stages = []
            observation = asyncio.create_task(watch(witness, COP, stages.append))
            try:
                phone = await self.connect(address, 'cop', COP)
                self.assertEqual(await phone.request(1), 2)
                await phone.close()
                with self.assertRaisesRegex(rp.ProtocolError, 'disconnected before completing'):
                    await asyncio.wait_for(observation, 5)
            finally:
                observation.cancel()
                await asyncio.gather(observation, return_exceptions=True)
            self.assertEqual(stages, list(STEPS[:2]))


if __name__ == '__main__':
    unittest.main()
