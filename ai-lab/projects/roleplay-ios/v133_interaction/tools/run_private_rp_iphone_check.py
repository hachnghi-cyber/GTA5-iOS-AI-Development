"""Run a bounded private RP LAN test with a Windows/host snapshot witness."""
import argparse
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import secrets

from prepare_private_rp import prepare
from prp3_direct_tls import Credentials, ProtocolError
from rp_private_authority import NativeAuthority
from rp_private_server import PING, PONG, SNAPSHOT, PrivateClient, PrivateServer, registry_from_json

LAN = tuple(ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
STEPS = ('joined_without_consent', 'opted_in', 'opted_out', 'disconnected')


def private_address(value):
    address = ipaddress.IPv4Address(value)
    if not address.is_loopback and not any(address in net for net in LAN):
        raise argparse.ArgumentTypeError('use a private IPv4 address on the PC LAN')
    return address


def report(status, **details):
    print(json.dumps({'time_utc': datetime.now(timezone.utc).isoformat(), 'status': status, **details}), flush=True)


async def watch(witness, tested_id, report_stage):
    """Require the four ordered snapshots for one admission and two nonces."""
    async def keepalive():
        while True:
            await witness.send(PING)
            await asyncio.sleep(2)

    ping_task = asyncio.create_task(keepalive())
    step, nonce = 0, None
    try:
        while step < len(STEPS):
            pending_read = asyncio.create_task(witness.receive())
            try:
                done, _ = await asyncio.wait((pending_read, ping_task), return_when=asyncio.FIRST_COMPLETED)
                if ping_task in done:
                    ping_task.result()
                kind, _ = pending_read.result()
            finally:
                if not pending_read.done():
                    pending_read.cancel()
                    with suppress(asyncio.CancelledError):
                        await pending_read
            if kind == PONG:
                continue
            if kind != SNAPSHOT:
                raise ProtocolError('unexpected frame for read-only witness')
            tested = witness.members.get(tested_id)
            if tested is None:
                if step == 0:
                    continue
                if step != 3:
                    raise ProtocolError('peer disconnected before completing the consent probe')
            else:
                consent, duty, custody, current_nonce = tested[2], tested[3], tested[4], tested[9]
                if duty or custody:
                    raise ProtocolError('unexpected gameplay state during transport test')
                if current_nonce == nonce:
                    if consent != int(step == 2):
                        raise ProtocolError('consent changed without advancing the nonce')
                    continue
                if step >= 3 or consent != int(step == 1) or (nonce is not None and current_nonce != nonce + 1):
                    raise ProtocolError('consent probe snapshot was out of order')
                nonce = current_nonce
            report_stage(STEPS[step])
            step += 1
    finally:
        ping_task.cancel()
        with suppress(asyncio.CancelledError):
            await ping_task


async def run(args):
    folder = args.folder.resolve()
    prepare(folder, args.ip, args.port, consent_probe=True)
    phone = folder / 'PoliceRP-Authority-PRIVATE.json'
    (folder / 'officer-iPhone-PRIVATE.json').rename(phone)
    server_config = json.loads((folder / 'server.json').read_text(encoding='utf-8'))
    witness_config = json.loads((folder / 'citizen.json').read_text(encoding='utf-8'))

    def credentials(config):
        return Credentials(*(folder / config[name] for name in ('certificate', 'private_key', 'trusted_ca')))

    registry = registry_from_json(server_config['principals'])
    authority = NativeAuthority(args.library, secrets.randbits(64) or 1, secrets.randbits(64) or 1)
    server = PrivateServer(credentials(server_config), registry, authority)
    witness = None
    try:
        endpoint = await server.start(str(args.ip), args.port)
        witness = await PrivateClient.connect(endpoint, credentials(witness_config),
            bytes.fromhex(witness_config['server_sha256']), witness_config['rp_id'], hostname=str(args.ip))
        report('ready', iphone_config=str(phone), window_seconds=args.wait_seconds)
        async with asyncio.timeout(args.wait_seconds):
            tested_id, = {entry.rp_id for entry in registry.values()} - {witness.identity}
            await watch(witness, tested_id, report)
        report('host_witness_passed', requires_matching_iphone_log=True)
    finally:
        if witness is not None:
            await witness.close()
        await server.close()
        authority.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True, type=Path, help='new private kit folder outside Git')
    parser.add_argument('--library', required=True, type=Path, help='compiled server authority library')
    parser.add_argument('--ip', required=True, type=private_address, help='PC private Wi-Fi IPv4')
    parser.add_argument('--port', type=int, default=30133)
    parser.add_argument('--wait-seconds', type=int, default=900)
    args = parser.parse_args()
    if not 5 <= args.wait_seconds <= 1080:
        parser.error('--wait-seconds must be between 5 and 1080')
    try:
        asyncio.run(run(args))
    except TimeoutError:
        report('timed_out')
        return 2
    except ProtocolError as error:
        report('rejected', reason=str(error))
        return 3
    except KeyboardInterrupt:
        report('cancelled')
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
