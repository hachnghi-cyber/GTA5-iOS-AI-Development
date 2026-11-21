"""Create local, short-lived identities and serve one iPhone PRP3 test."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from prp3_direct_tls import Credentials, Pairing, PeerSession, ProtocolError, WIRE

CONFIG_NAME = "PRP3TLS-Probe-PRIVATE.json"
HOST_NAME = "host-private.json"
LAN = tuple(ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def private_address(value):
    ip = ipaddress.IPv4Address(value)
    if not any(ip in subnet for subnet in LAN):
        raise ValueError("use the Windows IPv4 address on the private test LAN")
    return ip


def issue(name, now, key, ca=None, ca_key=None, ip=None):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject)
            .issuer_name(ca.subject if ca else subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=30))
            .add_extension(x509.BasicConstraints(ca=ca is None, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(x509.KeyUsage(
                digital_signature=ca is not None, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=ca is None,
                crl_sign=ca is None, encipher_only=False, decipher_only=False), True))
    if ca is not None:
        cert = cert.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
        purpose = ExtendedKeyUsageOID.SERVER_AUTH if ip is not None else ExtendedKeyUsageOID.CLIENT_AUTH
        cert = cert.add_extension(x509.ExtendedKeyUsage([purpose]), False)
        if ip is not None:
            cert = cert.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip)]), False)
    return cert.sign(ca_key if ca else key, hashes.SHA256())


def prepare(folder, address, port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("port must be 1024..65535")
    folder.mkdir(mode=0o700, parents=True)
    now = datetime.now(timezone.utc)
    ca_key, host_key, phone_key = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
    ca = issue("PRP3 ephemeral CA", now, ca_key)
    host = issue("PRP3 Windows responder", now, host_key, ca, ca_key, address)
    phone = issue("PRP3 iPhone probe", now, phone_key, ca, ca_key)
    password = secrets.token_urlsafe(32)
    phone_p12 = pkcs12.serialize_key_and_certificates(
        b"PRP3 temporary diagnostic", phone_key, phone, [ca],
        serialization.BestAvailableEncryption(password.encode()))
    local_id, peer_id = 11, 22
    common = {"host": str(address), "port": port, "session": str(secrets.randbits(64) or 1),
              "epoch": str(secrets.randbits(64) or 1), "expires": int(now.timestamp()) + 1200}

    def emit(path, data):
        with open(folder / path, "xb", opener=lambda name, flags: os.open(name, flags, 0o600)) as f:
            f.write(data)

    def b64(data):
        return base64.b64encode(data).decode("ascii")

    emit("ca.pem", ca.public_bytes(serialization.Encoding.PEM))
    emit("host.pem", host.public_bytes(serialization.Encoding.PEM))
    emit("host.key", host_key.private_bytes(serialization.Encoding.PEM,
         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    emit(HOST_NAME, json.dumps({
        **common, "local_id": str(local_id), "peer_id": str(peer_id),
        "client_pin": phone.fingerprint(hashes.SHA256()).hex()}).encode())
    emit(CONFIG_NAME, json.dumps({
        **common, "schema": "prp3-tls-probe-v1", "local_id": str(peer_id), "peer_id": str(local_id),
        "anchor": b64(ca.public_bytes(serialization.Encoding.DER)),
        "server_pin": b64(host.fingerprint(hashes.SHA256())), "identity": b64(phone_p12),
        "passphrase": password}).encode())


def respond(channel, pairing):
    request = WIRE.pack(b"PRP3", 1, 1, 0, pairing.session_id, pairing.local_id, pairing.epoch, 1)
    response = WIRE.pack(b"PRP3", 1, 2, 0, pairing.session_id, pairing.peer_id, pairing.epoch, 1)
    received = channel.receive()
    if received.wire != request or received.rp_sender != pairing.peer_id:
        raise ProtocolError("unexpected iPhone diagnostic request")
    channel.send(response)


def serve(folder):
    config = json.loads((folder / HOST_NAME).read_text(encoding="utf-8"))
    if not time.time() < config["expires"] <= time.time() + 1200:
        raise ValueError("test credentials expired; prepare a fresh pairing")
    pairing = Pairing(*(int(config[key]) for key in ("local_id", "peer_id", "session", "epoch")),
                      bytes.fromhex(config["client_pin"]))
    session = PeerSession(pairing, Credentials(folder/"host.pem", folder/"host.key", folder/"ca.pem"))
    with socket.socket() as listener:
        listener.bind((str(private_address(config["host"])), int(config["port"])))
        listener.listen(1)
        listener.settimeout(min(120, config["expires"] - time.time()))
        print("Ready for one iPhone diagnostic connection.", flush=True)
        client, _ = listener.accept()
        with session.open(client, server_side=True) as channel:
            respond(channel, pairing)
    print(json.dumps({"paired_client_greet_received": True, "documents_sent": True,
                      "iphone_receive_requires_device_log": True, "gameplay_rp_enabled": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("folder", type=Path)
    create.add_argument("--ip", required=True, type=private_address)
    create.add_argument("--port", type=int, default=44533)
    listen = commands.add_parser("serve")
    listen.add_argument("folder", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.folder, args.ip, args.port)
            print("Local pairing created. Transfer only the private iPhone config over USB.")
        else:
            serve(args.folder)
    except (OSError, EOFError, ValueError, ssl.SSLError) as error:
        parser.exit(1, f"TLS diagnostic stopped: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
