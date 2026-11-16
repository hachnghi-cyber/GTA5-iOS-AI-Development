"""Real loopback TLS1.3 transport, using ephemeral test identities only."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
import ipaddress
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

path = Path(__file__).resolve().parents[1] / "tools" / "prp3_direct_tls.py"
spec = importlib.util.spec_from_file_location("prp3_direct_tls", path)
tls = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tls
spec.loader.exec_module(tls)
runner_spec = importlib.util.spec_from_file_location("ios_tls_kit", path.with_name("run_ios_tls_probe.py"))
kit = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(kit)


def issue(label, key, authority, ca_key):
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, label)])
    builder = (x509.CertificateBuilder().subject_name(name)
               .issuer_name(authority.subject if authority else name)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
               .add_extension(x509.BasicConstraints(ca=authority is None, path_length=None), critical=True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False))
    if authority:
        builder = (builder
                   .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
                   .add_extension(x509.ExtendedKeyUsage([
                       ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]), False)
                   .add_extension(x509.SubjectAlternativeName([
                       x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False))
    else:
        builder = builder.add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
    return builder.sign(ca_key, hashes.SHA256())


@contextmanager
def connection(server, client, hostname="127.0.0.1"):
    with socket.socket() as listener, ThreadPoolExecutor(max_workers=1) as pool:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(6)
        with ExitStack() as server_stack, ExitStack() as client_stack:
            def accept():
                incoming, _ = listener.accept()
                return server_stack.enter_context(server.open(incoming, server_side=True))
            future = pool.submit(accept)
            try:
                raw = socket.create_connection(listener.getsockname(), timeout=3)
                peer = client_stack.enter_context(client.open(raw, server_side=False, peer_hostname=hostname))
            except Exception as client_error:
                # Preserve the real failure on both sides, including a TCP reset on
                # one side when the other has already rejected authentication.
                try:
                    future.result(timeout=8)
                except Exception as server_error:
                    raise ExceptionGroup("pair handshake refused",
                                         [client_error, server_error]) from None
                raise
            backend = future.result(timeout=8)
            yield backend, peer


def frame(target, nonce=1, epoch=7, session=123, kind=1):
    return tls.WIRE.pack(b"PRP3", 1, kind, 0, session, target, epoch, nonce)


class DirectTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca = issue("ephemeral test CA", ca_key, None, ca_key)
        ca_path = folder / "ca.pem"
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cls.credentials, cls.pins = {}, {}
        for label in ("a", "b", "other"):
            key = ec.generate_private_key(ec.SECP256R1())
            cert = issue(label, key, ca, ca_key)
            cert_path, key_path = folder / (label + ".pem"), folder / (label + ".key")
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            cls.credentials[label] = tls.Credentials(cert_path, key_path, ca_path)
            cls.pins[label] = cert.fingerprint(hashes.SHA256())

    def pair(self, client_cert="b", client_epoch=7):
        return (tls.PeerSession(tls.Pairing(11, 22, 123, 7, self.pins["b"]), self.credentials["a"]),
                tls.PeerSession(tls.Pairing(22, 11, 123, client_epoch, self.pins["a"]),
                                self.credentials[client_cert]))

    def test_generated_iphone_kit_interoperates_with_host_responder(self):
        with tempfile.TemporaryDirectory() as sandbox:
            folder = Path(sandbox) / "device-kit"
            kit.prepare(folder, ipaddress.IPv4Address("127.0.0.1"), 44533)
            phone = json.loads((folder / kit.CONFIG_NAME).read_text())
            host = json.loads((folder / kit.HOST_NAME).read_text())
            key, cert, _ = pkcs12.load_key_and_certificates(
                base64.b64decode(phone["identity"], validate=True), phone["passphrase"].encode())
            self.assertEqual(cert.fingerprint(hashes.SHA256()).hex(), host["client_pin"])
            (folder / "test-client.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            (folder / "test-client.key").write_bytes(key.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            anchor = x509.load_der_x509_certificate(base64.b64decode(phone["anchor"], validate=True))
            self.assertEqual(anchor.public_bytes(serialization.Encoding.PEM), (folder / "ca.pem").read_bytes())

            def configured(config, pin, prefix):
                return tls.PeerSession(tls.Pairing(
                    *(int(config[v]) for v in ("local_id", "peer_id", "session", "epoch")), pin),
                    tls.Credentials(folder / (prefix + ".pem"), folder / (prefix + ".key"), folder / "ca.pem"))
            server = configured(host, bytes.fromhex(host["client_pin"]), "host")
            client = configured(phone, base64.b64decode(phone["server_pin"], validate=True), "test-client")
            p = client.pairing
            with connection(server, client) as (a, b):
                b.send(frame(p.peer_id, session=p.session_id, epoch=p.epoch))
                kit.respond(a, server.pairing)
                self.assertEqual(b.receive().wire, frame(p.local_id, kind=2, session=p.session_id, epoch=p.epoch))
            with self.assertRaises(FileExistsError):
                kit.prepare(folder, ipaddress.IPv4Address("127.0.0.1"), 44533)

    def test_real_tls_two_way_preserves_exact_prp3_and_attaches_paired_identity(self):
        with connection(*self.pair()) as (a, b):
            b.send(frame(11))
            self.assertEqual(a.receive(), tls.Received(22, 123, 7, frame(11)))
            a.send(frame(22, kind=2))
            self.assertEqual(b.receive(), tls.Received(11, 123, 7, frame(22, kind=2)))

    def reject_pair(self, server, client, error_type, message, *, hostname="127.0.0.1"):
        with self.assertRaises((ExceptionGroup, OSError, EOFError, tls.ProtocolError)) as result:
            with connection(server, client, hostname):
                self.fail("invalid peer entered channel")
        exc = result.exception
        errors = exc.exceptions if isinstance(exc, ExceptionGroup) else (exc,)
        self.assertTrue(any(isinstance(error, error_type) and message in str(error)
                            for error in errors), errors)

    def test_valid_ca_but_unpaired_certificate_is_denied(self):
        self.reject_pair(*self.pair(client_cert="other"), tls.ProtocolError, "certificate")

    def test_tls_client_verifies_hostname(self):
        self.reject_pair(*self.pair(), ssl.SSLCertVerificationError, "Hostname mismatch",
                         hostname="wrong.example")

    def test_generation_mismatch_denied_before_prp3(self):
        self.reject_pair(*self.pair(client_epoch=8), tls.ProtocolError, "generation")

    def test_replay_rejected_after_reconnecting_same_generation(self):
        server, client = self.pair()
        with connection(server, client) as (a, b):
            b.send(frame(11))
            a.receive()
        with connection(server, client) as (a, b):
            # Exercise the receiver policy even with a misbehaving authenticated peer.
            b._sock.sendall(frame(11))
            with self.assertRaisesRegex(tls.ProtocolError, "nonce"):
                a.receive()
        with connection(server, client) as (a, b):
            b.send(frame(11, nonce=2))
            self.assertEqual(a.receive().wire, frame(11, nonce=2))

    def test_active_generation_has_only_one_live_channel(self):
        server, client = self.pair()
        with connection(server, client) as (a, b):
            with self.assertRaisesRegex(tls.ProtocolError, "another channel"):
                with server.open(socket.socket(), server_side=True):
                    self.fail("second socket was granted access")
            b.send(frame(11))
            self.assertEqual(a.receive().rp_sender, 22)
        with self.assertRaisesRegex(tls.ProtocolError, "closed"):
            b.send(frame(11, nonce=2))
        with connection(server, client) as (a, b):
            b.send(frame(11, nonce=2))
            self.assertEqual(a.receive().wire, frame(11, nonce=2))

    def test_wrong_target_and_truncated_frames_fail_closed(self):
        with connection(*self.pair()) as (a, b):
            b._sock.sendall(frame(22))
            with self.assertRaisesRegex(tls.ProtocolError, "target"):
                a.receive()
        with connection(*self.pair()) as (a, b):
            b._sock.sendall(frame(11)[:20])
            b._sock.close()
            with self.assertRaises(EOFError):
                a.receive()
