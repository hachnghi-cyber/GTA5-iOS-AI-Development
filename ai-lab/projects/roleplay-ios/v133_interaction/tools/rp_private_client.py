"""Interactive host client for the private RP server. No GTA integration."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import threading

from prp3_direct_tls import Credentials
from rp_private_server import PrivateClient, ACK, PING, REQUEST, SNAPSHOT
from rp_private_authority import FIELDS

OPERATIONS = dict(zip(('opt-in', 'opt-out', 'duty', 'end-duty', 'cuff', 'uncuff',
                      'escort', 'end-escort', 'seat', 'exit-seat', 'jail', 'release'), range(1, 13)))


async def run(config_path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    root = config_path.resolve().parent
    credentials = Credentials(*(root / config[key] for key in ('certificate', 'private_key', 'trusted_ca')))
    client = await PrivateClient.connect((config['host'], config['port']), credentials,
                   bytes.fromhex(config['server_sha256']), config['rp_id'], hostname=config['host'])

    async def receive():
        while True:
            kind, payload = await client.receive()
            if kind == ACK:
                print(json.dumps({'decision': 'applied' if payload[6] == 2 else 'denied',
                      'operation': payload[5], 'nonce': int.from_bytes(payload[32:40], 'little')}), flush=True)
            elif kind == SNAPSHOT:
                print(json.dumps({'revision': client.revision, 'members':
                     [dict(zip(FIELDS, row)) for row in client.members.values()]}), flush=True)

    async def heartbeat():
        while True:
            await client.send(PING)
            await asyncio.sleep(3)

    receiver = asyncio.create_task(receive())
    keep_alive = asyncio.create_task(heartbeat())
    inputs = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def read_console():
        try:
            for text in sys.stdin:
                loop.call_soon_threadsafe(inputs.put_nowait, text)
            loop.call_soon_threadsafe(inputs.put_nowait, None)
        except RuntimeError:
            pass  # Loop closed after remote disconnect; daemon exits with process.

    threading.Thread(target=read_console, daemon=True).start()
    line = None
    try:
        print('Commands: ' + ', '.join(OPERATIONS) + '; optional target ID; quit', flush=True)
        while True:
            line = asyncio.create_task(inputs.get())
            done, _ = await asyncio.wait((line, receiver, keep_alive), return_when=asyncio.FIRST_COMPLETED)
            if line not in done:
                line.cancel()
                for task in done:
                    task.result()
                break
            if line.result() is None:
                break
            words = line.result().split()
            if words == ['quit']:
                break
            if not words:
                continue
            try:
                if len(words) > 2:
                    raise ValueError('too many arguments')
                operation = OPERATIONS[words[0]]
                target = int(words[1]) if len(words) == 2 else client.identity
                if not 0 < target < 2**64:
                    raise ValueError('invalid target')
            except (ValueError, KeyError):
                print('Use: operation [target_id]', flush=True)
                continue
            await client.send(REQUEST, client.command(operation, target))
    finally:
        if line:
            line.cancel()
        receiver.cancel()
        keep_alive.cancel()
        await asyncio.gather(receiver, keep_alive, return_exceptions=True)
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    try:
        asyncio.run(run(parser.parse_args().config))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == '__main__':
    main()
