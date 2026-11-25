"""Install this run's two private RP account profiles in the two GTA Documents folders."""
import argparse
import asyncio
import base64
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import plistlib
import secrets
import sys
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12

PROFILE = 'PoliceRP-Authority-PRIVATE.json'
GUEST_APP = '/Documents/Applications/com.macport.gtav.app'


def read_profiles(kit):
    if any((p / '.git').exists() for p in (kit, *kit.parents)):
        raise ValueError('Use the private laptop kit outside Git.')
    config = json.loads((kit / 'server.json').read_bytes())
    registry = config['principals']
    principals = {str(p['rp_id']): (p['role'], p['certificate_sha256']) for p in registry}
    server = x509.load_pem_x509_certificate((kit / config['certificate']).read_bytes())
    ca = x509.load_pem_x509_certificate((kit / config['trusted_ca']).read_bytes())
    server_pin = server.fingerprint(hashes.SHA256())
    anchor = ca.public_bytes(serialization.Encoding.DER)
    pair, scopes = [], []
    for role, own, peer in [('officer', '11', '22'), ('citizen', '22', '11')]:
        raw = (kit / (role + '-iPhone-PRIVATE.json')).read_bytes()
        p = json.loads(raw)
        desktop = json.loads((kit / (role + '.json')).read_bytes())
        if (p['host'], p['port']) != (desktop['host'], desktop['port']):
            raise ValueError('RP endpoint does not match the server kit.')
        if ((p['schema'], p.get('interface'), p.get('account_ui'), p['rp_id'], p['rp_peer_id']) !=
                ('prp-authority-client-v1', 'rp-panel-v1', 'device-account-v1', own, peer)):
            raise ValueError('Unexpected RP account profile or role assignment.')
        if p['expires'] <= time.time():
            raise ValueError('Start a fresh laptop server run. The profiles have expired.')
        if (base64.b64decode(p['server_pin'], validate=True) != server_pin or
                base64.b64decode(p['anchor'], validate=True) != anchor):
            raise ValueError('Profile trust does not match the server kit.')
        key, cert, _ = pkcs12.load_key_and_certificates(base64.b64decode(p['identity'], validate=True),
                                                      p['passphrase'].encode())
        if (key is None or cert is None or principals.get(own) !=
                (2 if role == 'officer' else 1, cert.fingerprint(hashes.SHA256()).hex())):
            raise ValueError('RP client certificate does not match the server registry.')
        scopes.append(tuple(p[k] for k in ('host', 'port', 'server_pin', 'anchor', 'expires')))
        pair.append(raw)
    if scopes[0] != scopes[1]:
        raise ValueError('The profiles belong to different server runs.')
    return pair


async def guest_documents(afc):
    app = plistlib.loads(await afc.get_file_contents(GUEST_APP + '/Info.plist'))
    if app.get('CFBundleIdentifier') != 'com.macport.gtav':
        raise ValueError('The LiveContainer guest is not GTA.')
    info = plistlib.loads(await afc.get_file_contents(GUEST_APP + '/LCAppInfo.plist'))
    containers = info.get('LCContainers')
    if not isinstance(containers, list) or len(containers) != 1:
        raise ValueError('Cannot select a unique GTA guest data container. Copy the citizen profile manually.')
    folder = containers[0]['folderName']
    if not isinstance(folder, str) or str(uuid.UUID(folder)) != folder.lower():
        raise ValueError('Invalid GTA guest data folder.')
    documents = '/Documents/Data/Application/' + folder + '/Documents'
    await afc.listdir(documents)
    return documents


@dataclass
class ProfileWrite:
    afc: object
    target: str
    role: str
    raw: bytes = field(repr=False)
    previous: bytes | None = field(default=None, repr=False)
    temp: str = field(init=False)

    def __post_init__(self):
        self.temp = self.target + '.' + secrets.token_hex(8) + '.tmp'

    async def current(self):
        if await self.afc.exists(self.target):
            return await self.afc.get_file_contents(self.target)
        return None

    async def stage(self, data):
        await self.afc.set_file_contents(self.temp, data)
        if await self.afc.get_file_contents(self.temp) != data:
            raise IOError(f'{self.role}: profile staging readback failed.')

    async def restore(self):
        current = await self.current()
        if current == self.previous:
            return
        if current != self.raw:
            raise IOError(f'{self.role}: profile changed independently.')
        if self.previous is None:
            await self.afc.rm_single(self.target)
        else:
            await self.stage(self.previous)
            await self.afc.rename(self.temp, self.target)
        if await self.current() != self.previous:
            raise IOError(f'{self.role}: previous profile readback failed.')


async def install_pair(profiles, kit):
    attempted = []
    try:
        for profile in profiles:
            profile.previous = await profile.current()
            if profile.previous == profile.raw:
                continue
            if profile.previous is not None:
                backup = kit / (profile.role + '-previous-' + secrets.token_hex(8) + '.private.json')
                with open(backup, 'xb', opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
                    f.write(profile.previous)
            await profile.stage(profile.raw)

        for profile in profiles:
            if await profile.current() != profile.previous:
                raise IOError(f'{profile.role}: profile changed during staging. Retry.')
            if profile.previous != profile.raw:
                # AFC can apply the rename even if the acknowledgement is lost.
                attempted.append(profile)
                await profile.afc.rename(profile.temp, profile.target)
        for profile in profiles:
            if await profile.current() != profile.raw:
                raise IOError(f'{profile.role}: installed profile readback failed.')
    except Exception as error:
        pending = []
        for profile in reversed(attempted):
            try:
                await profile.restore()
            except Exception:
                pending.append(profile.role)
        if pending:
            raise IOError('Reconnect and rerun to verify these profiles: ' + ', '.join(pending)) from error
        raise
    finally:
        for profile in profiles:
            # Do not hide the device error if the connection is already gone.
            try:
                if await profile.afc.exists(profile.temp):
                    await profile.afc.rm_single(profile.temp)
            except Exception as error:
                print(f'{profile.role}: could not clean up {profile.temp} ({type(error).__name__}).',
                      file=sys.stderr)


async def install(kit, device_id=None):
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    from pymobiledevice3.services.installation_proxy import InstallationProxyService
    from pymobiledevice3.usbmux import list_devices

    officer, citizen = read_profiles(kit)
    attached = await list_devices()
    if device_id is not None:
        attached = [d for d in attached if d.serial == device_id]
    devices = [d for d in attached if d.connection_type == 'USB']
    if not devices and device_id is not None:
        devices = [d for d in attached if d.connection_type == 'Network']
    if len(devices) != 1:
        raise ValueError('Connect and unlock the one iPhone running both GTA apps.')
    async with await create_using_usbmux(serial=devices[0].serial, connection_type=devices[0].connection_type,
                                         autopair=False) as device:
        async with InstallationProxyService(device) as apps:
            installed = await apps.get_apps(application_type='User')
        standalone = [b for b, a in installed.items() if b.split('.')[:3] == ['com', 'macport', 'gtav']
                      and a.get('CFBundleExecutable') == 'GTA5']
        live = [b for b, a in installed.items() if a.get('CFBundleName') == 'LiveContainer'
                or a.get('CFBundleDisplayName') == 'LiveContainer']
        if len(standalone) != 1 or len(live) != 1:
            raise ValueError('Cannot select a unique standalone GTA and LiveContainer.')
        async with await HouseArrestService.create(device, standalone[0], documents_only=True) as gta, \
                await HouseArrestService.create(device, live[0], documents_only=True) as lc:
            folder = await guest_documents(lc)
            await install_pair((ProfileWrite(gta, '/Documents/' + PROFILE, 'officer', officer),
                                ProfileWrite(lc, folder + '/' + PROFILE, 'citizen', citizen)), kit)
            print('Verified both profile readbacks: standalone officer (11), LiveContainer citizen (22).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--device', help='select a previously paired iPhone by its identifier (USB or Wi-Fi)')
    args = parser.parse_args()
    asyncio.run(install(args.kit.resolve(), args.device))
