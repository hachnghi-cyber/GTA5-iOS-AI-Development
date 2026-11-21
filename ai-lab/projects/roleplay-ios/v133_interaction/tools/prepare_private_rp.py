"""Create a 30-minute local development CA/server/officer/citizen kit.

Reuses the audited diagnostic certificate issuer. No existing certificates,
keys, game files or iPhone credentials are accessed. Never overwrite a kit.
"""
import argparse
import base64
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from run_ios_tls_probe import issue


def prepare(folder, address, port, *, consent_probe=False, social_probe=False, panel=False,
            login_port=None):
    if sum((consent_probe, social_probe, panel)) > 1:
        raise ValueError('choose one iPhone mode')
    folder = folder.resolve()
    if any((parent / '.git').exists() for parent in (folder, *folder.parents)):
        raise ValueError('private kit must be outside every Git working tree')
    if not address.is_loopback and not address.is_private:
        raise ValueError('development kit accepts loopback or private IP only')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('invalid development port')
    if login_port is not None and (type(login_port) is not int or not 1024 <= login_port <= 65535 or login_port == port):
        raise ValueError('login port must be a separate port between 1024 and 65535')
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
        if name != 'server':
            password = secrets.token_urlsafe(32)
            identity = pkcs12.serialize_key_and_certificates(b'Private RP development',
                peer_key, cert, [ca], serialization.BestAvailableEncryption(password.encode()))
            iphone_config = {
                'schema': 'prp-authority-client-v1', 'host': str(address), 'port': port,
                'expires': int(now.timestamp()) + 1200, 'rp_id': '11' if name == 'officer' else '22',
                'server_pin': base64.b64encode(bytes.fromhex(pins['server'])).decode(),
                'anchor': base64.b64encode(ca.public_bytes(serialization.Encoding.DER)).decode(),
                'identity': base64.b64encode(identity).decode(), 'passphrase': password}
            if consent_probe:
                iphone_config['diagnostic'] = 'consent-round-trip-v1'
            if social_probe:
                iphone_config['diagnostic'] = 'social-round-trip-v1'
            if panel:
                iphone_config['interface'] = 'rp-panel-v1'
                if login_port is not None:
                    iphone_config['account_ui'] = 'device-account-v1'
            if social_probe or panel:
                iphone_config['rp_peer_id'] = '22' if name == 'officer' else '11'
            emit(name + '-iPhone-PRIVATE.json', iphone_config)
    origin_host = f'[{address}]' if address.version == 6 else str(address)
    login = {'login': {'database': '../rp-accounts.sqlite3',
                       'origin': f'https://{origin_host}:{login_port}'}} if login_port else {}
    emit('server.json', {**login, 'certificate': 'server.pem', 'private_key': 'server.key',
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
    parser.add_argument('--login-port', type=int, help='require account login and serve its HTTPS portal')
    probes = parser.add_mutually_exclusive_group()
    probes.add_argument('--consent-probe', action='store_true',
                        help='request one iPhone opt-in/opt-out round trip and disconnect')
    probes.add_argument('--social-probe', action='store_true',
                        help='opt in on iPhone, wait for a greet and request documents from the paired RP identity')
    probes.add_argument('--panel', action='store_true',
                        help='enable manual RP controls for the two generated iPhone identities')
    args = parser.parse_args()
    prepare(args.folder, args.ip, args.port, consent_probe=args.consent_probe,
            social_probe=args.social_probe, panel=args.panel, login_port=args.login_port)
    print('Created local development kit (30 minutes); private keys are not printed.')


if __name__ == '__main__':
    main()
