"""Real loopback mTLS + compiled C authority; game observations are synthetic."""
import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import replace
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_prp3_direct_tls import issue
from prp3_direct_tls import Credentials, ProtocolError
from rp_private_authority import DutyObservation, NativeAuthority, PairObservation, ParticipantAdmission
import rp_private_server as rp
from prepare_private_rp import prepare

COP, CITIZEN = 11, 22
OPT_IN, OPT_OUT, DUTY, END_DUTY, CUFF, UNCUFF, ESCORT, END_ESCORT, SEAT, EXIT_SEAT, JAIL, RELEASE = range(1, 13)


class SyntheticScene:
    """Test-owned facts, never obtained from an RP socket or game engine."""
    def __init__(self):
        self.distance, self.age, self.flags = 200, 0, 31
        self.duty = True
        self.duty_age = 0

    def duty_state(self, subject, now):
        return DutyObservation(subject, now - self.duty_age, self.duty)

    def __call__(self, actor, target, now):
        return PairObservation(actor, target, now - self.age, 77, self.distance, 1, self.flags)


class PrivateServerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = os.environ.get('RP_AUTHORITY_LIBRARY')
        if not cls.library or not Path(cls.library).is_file():
            raise RuntimeError('Build tools/build_rp_authority.py and set RP_AUTHORITY_LIBRARY first')
        folder = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca = issue('temporary server test CA', ca_key, None, ca_key)
        ca_path = folder / 'ca.pem'
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cls.credentials, cls.pins = {}, {}
        for label in ('server', 'cop', 'citizen', 'outsider'):
            key = ec.generate_private_key(ec.SECP256R1())
            cert = issue(label, key, ca, ca_key)
            cert_path, key_path = folder / (label + '.pem'), folder / (label + '.key')
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                 serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            cls.credentials[label] = Credentials(cert_path, key_path, ca_path)
            cls.pins[label] = cert.fingerprint(hashes.SHA256())

    @asynccontextmanager
    async def running(self, scene=None, *, lease=3, scope=(123, 7), use_duty_provider=True):
        authority = NativeAuthority(self.library, *scope, observation_provider=scene,
                                    duty_provider=scene.duty_state if scene and use_duty_provider else None)
        registry = {self.pins['cop']: rp.Principal(COP, 2),
                    self.pins['citizen']: rp.Principal(CITIZEN, 1)}
        server = rp.PrivateServer(self.credentials['server'], registry, authority, lease_seconds=lease)
        address = await server.start()
        try:
            yield server, address
        finally:
            await server.close()
            authority.close()

    async def connect(self, address, label, identity=None, pin=None):
        client = await rp.PrivateClient.connect(address, self.credentials[label],
                    self.pins['server'] if pin is None else pin,
                    identity or (COP if label == 'cop' else CITIZEN))
        self.addAsyncCleanup(client.close)
        return client

    async def wait_state(self, client, predicate):
        async with asyncio.timeout(3):
            while not predicate(client.members):
                await client.receive()

    async def apply(self, client, operation, target=None, expected=2):
        wire = client.command(operation, target)
        ack = await client.transact(wire)
        self.assertEqual(ack[6], expected)
        return wire, ack

    async def ready(self, address):
        cop = await self.connect(address, 'cop')
        citizen = await self.connect(address, 'citizen')
        await self.apply(cop, OPT_IN)
        await self.apply(citizen, OPT_IN)
        await self.apply(cop, DUTY)
        return cop, citizen

    async def test_two_clients_full_police_sequence_and_opt_out(self):
        async with self.running(SyntheticScene()) as (_, address):
            cop, citizen = await self.ready(address)
            for operation, custody in ((CUFF, 1), (ESCORT, 2), (SEAT, 3),
                                       (EXIT_SEAT, 1), (JAIL, 4), (RELEASE, 0)):
                await self.apply(cop, operation, CITIZEN)
                for client in (cop, citizen):
                    await self.wait_state(client, lambda m: CITIZEN in m and m[CITIZEN][4] == custody)
                self.assertEqual(cop.members, citizen.members)
                self.assertEqual(cop.revision, citizen.revision)
            await self.apply(cop, CUFF, CITIZEN)
            await self.apply(cop, UNCUFF, CITIZEN)
            await self.apply(cop, CUFF, CITIZEN)
            await self.apply(citizen, OPT_OUT)
            for client in (cop, citizen):
                await self.wait_state(client, lambda m: CITIZEN in m and m[CITIZEN][2:5] == (0, 0, 0))
            await self.apply(cop, CUFF, CITIZEN, expected=1)

    async def test_default_no_game_facts_denies_duty_and_custody(self):
        async with self.running() as (_, address):
            cop = await self.connect(address, 'cop')
            citizen = await self.connect(address, 'citizen')
            await self.apply(cop, OPT_IN)
            await self.apply(citizen, OPT_IN)
            await self.apply(cop, DUTY, expected=1)
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            await self.apply(citizen, DUTY, expected=1)

    async def test_pair_facts_without_separate_duty_source_cannot_start_shift(self):
        async with self.running(SyntheticScene(), use_duty_provider=False) as (_, address):
            cop = await self.connect(address, 'cop')
            await self.apply(cop, OPT_IN)
            await self.apply(cop, DUTY, expected=1)

    async def test_off_shift_and_stale_duty_clear_custody_without_client_request(self):
        for failure in ('off_shift', 'stale', 'unavailable'):
            with self.subTest(failure=failure):
                scene = SyntheticScene()
                async with self.running(scene) as (server, address):
                    cop, citizen = await self.ready(address)
                    await self.apply(cop, CUFF, CITIZEN)
                    await self.wait_state(citizen, lambda m: CITIZEN in m and m[CITIZEN][4] == 1)
                    if failure == 'off_shift':
                        scene.duty = False
                    elif failure == 'stale':
                        scene.duty_age = 251
                    else:
                        def down(_subject, _now):
                            raise TimeoutError('modeled source unavailable')
                        server.authority.duty_provider = down
                    await self.wait_state(citizen, lambda m: COP in m and m[COP][3] == 0 and m[CITIZEN][4] == 0)
                    await self.apply(cop, DUTY, expected=1)

    async def test_stale_admission_cannot_regrant_duty_after_reconnect(self):
        async with self.running(SyntheticScene()) as (server, address):
            captured = None
            def first(subject, now):
                nonlocal captured
                captured = subject
                return DutyObservation(subject, now, True)
            server.authority.duty_provider = first
            officer = await self.connect(address, 'cop')
            citizen = await self.connect(address, 'citizen')
            await self.apply(officer, OPT_IN)
            await self.apply(officer, DUTY)
            self.assertIsInstance(captured, ParticipantAdmission)
            self.assertEqual(captured.principal, COP)
            old_subject = captured
            await officer.close()
            await self.wait_state(citizen, lambda m: m and COP not in m)
            server.authority.duty_provider = lambda _subject, now: DutyObservation(old_subject, now, True)
            replacement = await self.connect(address, 'cop')
            await self.apply(replacement, OPT_IN)
            await self.apply(replacement, DUTY, expected=1)

    async def test_custody_denied_for_old_target_admission_even_with_fresh_timestamp(self):
        scene = SyntheticScene()
        async with self.running(scene) as (server, address):
            cop, citizen = await self.ready(address)
            saved = None
            def capture(actor, target, now):
                nonlocal saved
                saved = scene(actor, target, now)
                return saved
            server.authority.observation_provider = capture
            await self.apply(cop, CUFF, CITIZEN)
            self.assertEqual(saved.target.principal, CITIZEN)
            await citizen.close()
            await self.wait_state(cop, lambda members: members and CITIZEN not in members)
            replacement = await self.connect(address, 'citizen')
            await self.apply(replacement, OPT_IN)
            # A fresh time cannot make evidence from the old admission valid.
            server.authority.observation_provider = lambda _a, _t, now: replace(saved, observed_at_ms=now)
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            self.assertEqual(server.authority.snapshot(CITIZEN)[4], 0)
            server.authority.observation_provider = scene
            await self.apply(cop, CUFF, CITIZEN)
            await self.wait_state(replacement, lambda members: CITIZEN in members and members[CITIZEN][4] == 1)

    async def test_pair_source_cannot_substitute_actor_or_target(self):
        scene = SyntheticScene()
        async with self.running(scene) as (server, address):
            cop, _ = await self.ready(address)
            server.authority.observation_provider = lambda actor, target, now: scene(target, actor, now)
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            self.assertEqual(server.authority.snapshot(CITIZEN)[4], 0)
            server.authority.observation_provider = scene
            await self.apply(cop, CUFF, CITIZEN)

    async def test_generated_development_kit_uses_actual_server_and_client_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'private-kit'
            prepare(folder, ipaddress.ip_address('127.0.0.1'), 30133)
            with self.assertRaises(FileExistsError):
                prepare(folder, ipaddress.ip_address('127.0.0.1'), 30133)
            self.assertFalse((folder / 'ca.key').exists())
            phone = json.loads((folder / 'officer-iPhone-PRIVATE.json').read_text())
            private_key, certificate, chain = pkcs12.load_key_and_certificates(
                base64.b64decode(phone['identity']), phone['passphrase'].encode())
            self.assertIsNotNone(private_key)
            self.assertEqual(len(chain), 1)
            self.assertEqual(phone['rp_id'], '11')
            self.assertEqual(phone['schema'], 'prp-authority-client-v1')
            self.assertEqual(len(base64.b64decode(phone['server_pin'])), 32)
            config = json.loads((folder / 'server.json').read_text())
            self.assertEqual(certificate.fingerprint(hashes.SHA256()).hex(),
                             config['principals'][0]['certificate_sha256'])
            authority = NativeAuthority(self.library, 123, 7)
            def credentials(data):
                return Credentials(*(folder / data[key] for key in ('certificate', 'private_key', 'trusted_ca')))
            server = rp.PrivateServer(credentials(config), rp.registry_from_json(config['principals']), authority)
            address = await server.start()
            clients = []
            try:
                for name in ('officer', 'citizen'):
                    config = json.loads((folder / (name + '.json')).read_text())
                    client = await rp.PrivateClient.connect(address, credentials(config),
                             bytes.fromhex(config['server_sha256']), config['rp_id'])
                    clients.append(client)
                    await self.apply(client, OPT_IN)
                await self.apply(clients[0], DUTY, expected=1)
                await self.wait_state(clients[1], lambda m: len(m) == 2 and all(row[2] for row in m.values()))
            finally:
                for client in clients:
                    await client.close()
                await server.close()
                authority.close()

    async def test_timer_releases_jail_and_broadcasts_without_new_command(self):
        async with self.running(SyntheticScene()) as (server, address):
            clock = [5000]
            server.now = lambda: clock[0]
            cop, citizen = await self.ready(address)
            await self.apply(cop, CUFF, CITIZEN)
            await self.apply(cop, JAIL, CITIZEN)
            for client in (cop, citizen):
                await self.wait_state(client, lambda m: m[CITIZEN][4] == 4)
            revision = citizen.revision
            clock[0] += 60000
            for client in (cop, citizen):
                await self.wait_state(client, lambda m: m[CITIZEN][4] == 0)
                self.assertGreater(client.revision, revision)

    async def test_client_close_and_cancelled_transaction_clear_stale_snapshot(self):
        async with self.running(SyntheticScene()) as (server, address):
            cop, citizen = await self.ready(address)
            await self.apply(cop, CUFF, CITIZEN)
            await self.wait_state(citizen, lambda m: m[CITIZEN][4] == 1)
            await citizen.close()
            self.assertTrue(citizen.closed)
            self.assertEqual(citizen.members, {})
            await self.wait_state(cop, lambda m: CITIZEN not in m)
            # A test-controlled lost ACK after a real TLS send is ambiguous:
            # cancellation must discard this stream, not read its ACK later.
            enqueue = server._enqueue
            server._enqueue = lambda peer, kind, payload=b'': True if kind == rp.ACK else enqueue(peer, kind, payload)
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(cop.transact(cop.command(END_DUTY)), 0.05)
            self.assertTrue(cop.closed)
            self.assertEqual(cop.members, {})
            with self.assertRaises(ProtocolError):
                await cop.send(rp.PING)

    async def test_distance_freshness_and_registry_role(self):
        scene = SyntheticScene()
        async with self.running(scene) as (_, address):
            cop, citizen = await self.ready(address)
            await self.apply(citizen, DUTY, expected=1)
            await self.apply(citizen, CUFF, COP, expected=1)
            scene.distance = 401
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            scene.distance, scene.age = 200, 251
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            scene.age, scene.flags = 0, 30  # same instance is false
            await self.apply(cop, CUFF, CITIZEN, expected=1)
            scene.flags = 31
            await self.apply(cop, CUFF, CITIZEN)

    async def test_exact_retry_is_historical_ack_not_current_state(self):
        async with self.running(SyntheticScene()) as (_, address):
            cop, citizen = await self.ready(address)
            wire, ack = await self.apply(cop, CUFF, CITIZEN)
            self.assertEqual(await cop.transact(wire), ack)
            await self.apply(citizen, OPT_OUT)
            self.assertEqual(await cop.transact(wire), ack)
            await self.wait_state(cop, lambda m: m[CITIZEN][4] == 0 and m[CITIZEN][2] == 0)
            self.assertEqual(cop.members[CITIZEN][4], 0)

    async def test_disconnect_releases_custody_and_reconnect_keeps_nonce(self):
        async with self.running(SyntheticScene()) as (server, address):
            cop, citizen = await self.ready(address)
            old, _ = await self.apply(cop, CUFF, CITIZEN)
            await cop.close()
            await self.wait_state(citizen, lambda m: COP not in m and m[CITIZEN][4] == 0)
            replacement = await self.connect(address, 'cop')
            self.assertEqual(replacement.nonce, 3)
            await self.wait_state(replacement, lambda m: COP in m)
            self.assertEqual(replacement.members[COP][2:4], (0, 0))
            with self.assertRaises((asyncio.IncompleteReadError, ConnectionError)):
                await replacement.transact(old)  # Old ACK invalidated by leave.
            await self.wait_state(citizen, lambda m: COP not in m)
            self.assertNotIn(COP, server.peers)

    async def test_old_scope_and_same_nonce_different_command_disconnect(self):
        for change in ('scope', 'same_nonce', 'old_nonce'):
            async with self.running() as (_, address):
                cop = await self.connect(address, 'cop')
                await self.apply(cop, OPT_IN)
                if change == 'scope':
                    wire = rp.COMMAND.pack(b'PRPC', 1, OPT_OUT, 0, 999, COP, 7, 2)
                elif change == 'same_nonce':
                    wire = cop.command(OPT_OUT, nonce=1)
                else:
                    await self.apply(cop, OPT_OUT)
                    wire = cop.command(OPT_IN, nonce=1)
                with self.assertRaises((asyncio.IncompleteReadError, ConnectionError)):
                    await cop.transact(wire)

    async def test_unregistered_cert_duplicate_connection_and_wrong_server_pin(self):
        async with self.running() as (server, address):
            cop = await self.connect(address, 'cop')
            for label, pin in (('outsider', None), ('cop', None), ('citizen', b'X' * 32)):
                with self.assertRaises((ProtocolError, asyncio.IncompleteReadError, ConnectionError)):
                    await self.connect(address, label, pin=pin)
            await self.apply(cop, OPT_IN)
            self.assertTrue(server.authority.snapshot(COP)[2])

    async def test_payload_cannot_supply_sender_role_or_game_facts(self):
        async with self.running(SyntheticScene()) as (_, address):
            cop, citizen = await self.ready(address)
            # Nonzero reserved byte (attempted identity/role flag) is not accepted.
            forged = bytearray(citizen.command(CUFF, COP))
            forged[7] = 1
            with self.assertRaises((asyncio.IncompleteReadError, ConnectionError)):
                await citizen.transact(bytes(forged))
            await self.wait_state(cop, lambda m: CITIZEN not in m)

    async def test_lease_expiry_revokes_and_replicates_to_live_client(self):
        async with self.running(SyntheticScene(), lease=0.4) as (_, address):
            cop, citizen = await self.ready(address)
            await self.apply(cop, CUFF, CITIZEN)
            async def keep_alive():
                for _ in range(10):
                    await citizen.send(rp.PING)
                    await asyncio.sleep(0.08)
            heartbeat = asyncio.create_task(keep_alive())
            try:
                await self.wait_state(citizen, lambda m: COP not in m and CITIZEN in m and m[CITIZEN][4] == 0)
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)

    async def test_bounded_frame_and_header_body_deadline(self):
        for payload in (rp.HEADER.pack(rp.REQUEST, rp.MAX_RECORD + 1),
                        rp.HEADER.pack(rp.REQUEST, 40) + b'partial'):
            async with self.running(lease=0.2) as (server, address):
                cop = await self.connect(address, 'cop')
                await self.apply(cop, OPT_IN)
                cop.writer.write(payload)
                await cop.writer.drain()
                with self.assertRaises((asyncio.IncompleteReadError, ConnectionError)):
                    while True:
                        await cop.receive()
                self.assertNotIn(COP, server.peers)

    async def test_fresh_server_generation_rejects_prior_frame(self):
        async with self.running(scope=(123, 7)) as (_, address):
            cop = await self.connect(address, 'cop')
            old = cop.command(OPT_IN)
        async with self.running(scope=(123, 8)) as (_, address):
            cop = await self.connect(address, 'cop')
            with self.assertRaises((asyncio.IncompleteReadError, ConnectionError)):
                await cop.transact(old)

    def test_registry_rejects_aliases_and_payload_permissions(self):
        with self.assertRaises(ValueError):
            rp.validate_registry({b'A' * 32: rp.Principal(COP, 2), b'B' * 32: rp.Principal(COP, 1)})
        with self.assertRaises(ValueError):
            rp.registry_from_json([{'certificate_sha256': 'aa' * 32, 'rp_id': COP, 'role': 2, 'authenticated': True}])


if __name__ == '__main__':
    unittest.main()
