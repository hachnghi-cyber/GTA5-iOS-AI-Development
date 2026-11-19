"""Create a 30-minute local development CA/server/officer/citizen kit.

Reuses the audited diagnostic certificate issuer. No existing certificates,
keys, game files or iPhone credentials are accessed. Never overwrite a kit.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from run_ios_tls_probe import issue


def prepare(folder, address, port):
    folder = folder.resolve()
    if any((parent / '.git').exists() for parent in (folder, *folder.parents)):
        raise ValueError('private kit must be outside every Git working tree')
    if not address.is_loopback and not address.is_private:
        raise ValueError('development kit accepts loopback or private IP only')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('invalid development port')
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)

    def emit(name, value):
        data = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
        with open(folder / name, 'xb', opener=lambda path, flags: os.open(path, flags, 0o600)) as out:
            out.write(data)

    now = datetime.now(timezone.utc)
    key = ec.generate_private_key(ec.SECP256R1())
    ca = issue('Private RP development CA', now, key)
    emit('ca.pem', ca.public_bytes(serialization.Encoding.PEM))
    pins = {}
    for name in ('server', 'officer', 'citizen'):
        peer_key = ec.generate_private_key(ec.SECP256R1())
        cert = issue('Private RP ' + name, now, peer_key, ca, key,
                     address if name == 'server' else None)
        pins[name] = cert.fingerprint(hashes.SHA256()).hex()
        emit(name + '.pem', cert.public_bytes(serialization.Encoding.PEM))
        emit(name + '.key', peer_key.private_bytes(serialization.Encoding.PEM,
             serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    emit('server.json', {'certificate': 'server.pem', 'private_key': 'server.key',
         'trusted_ca': 'ca.pem', 'principals': [
             {'certificate_sha256': pins['officer'], 'rp_id': 11, 'role': 2},
             {'certificate_sha256': pins['citizen'], 'rp_id': 22, 'role': 1}]})
    for name, identity in (('officer', 11), ('citizen', 22)):
        emit(name + '.json', {'certificate': name + '.pem', 'private_key': name + '.key',
             'trusted_ca': 'ca.pem', 'server_sha256': pins['server'], 'rp_id': identity,
             'host': str(address), 'port': port})
    # CA private key is deliberately not persisted. Renew by creating a new kit.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--ip', type=ipaddress.ip_address, default=ipaddress.ip_address('127.0.0.1'))
    parser.add_argument('--port', type=int, default=30133)
    args = parser.parse_args()
    prepare(args.folder, args.ip, args.port)
    print('Created local development kit (30 minutes); private keys are not printed.')


if __name__ == '__main__':
    main()
