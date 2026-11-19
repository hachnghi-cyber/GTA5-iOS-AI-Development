"""Interactive host client for the private RP server. No GTA integration."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import threading

from prp3_direct_tls import Credentials, ProtocolError, WIRE, u64
from rp_private_server import PrivateClient, ACK, PING, PONG, REQUEST, SNAPSHOT
from rp_private_authority import FIELDS
from rp_social_relay import (CANCELLED, DENIED, RECEIPT, RECEIVED, RESULT, SOCIAL_EVENT, SOCIAL_OPEN,
                             SOCIAL_RECEIPT, SOCIAL_REQUEST, SOCIAL_RESULT, SOCIAL_STATE, WORD, decode_event)

OPERATIONS = dict(zip(('opt-in', 'opt-out', 'duty', 'end-duty', 'cuff', 'uncuff',
                      'escort', 'end-escort', 'seat', 'exit-seat', 'jail', 'release'), range(1, 13)))
SOCIAL_COMMANDS = {'greet': 1, 'documents': 2}


class SocialClient:
    def __init__(self, channel):
        self.channel = channel
        self.last_nonce = None
        self.pending = None
        self.received = {}

    async def open(self):
        if self.last_nonce is not None:
            raise ValueError('social channel is already open')
        async with asyncio.timeout(5):
            await self.channel.send(SOCIAL_OPEN)
            while True:
                kind, payload = await self.channel.receive()
                if kind == SOCIAL_STATE and len(payload) == WORD.size:
                    self.last_nonce, = WORD.unpack(payload)
                    return
                if kind not in (SNAPSHOT, PONG):
                    raise ProtocolError('social state was not received')

    async def request(self, kind, target):
        if (kind not in SOCIAL_COMMANDS.values() or not u64(target) or target == self.channel.identity or
                self.pending is not None or self.last_nonce is None or self.last_nonce == (1 << 64) - 1):
            raise ValueError('invalid social request or one is already pending')
        self.last_nonce += 1
        self.pending = self.last_nonce
        payload = WIRE.pack(b'PRP3', 1, kind, 0, self.channel.session, target, self.channel.epoch, self.pending)
        await self.channel.send(SOCIAL_REQUEST, payload)

    async def consume(self, kind, payload):
        if kind == SOCIAL_EVENT:
            sender, interaction, nonce = decode_event(payload, self.channel.session,
                                                       self.channel.epoch, self.channel.identity)
            if nonce <= self.received.get(sender, 0):
                raise ProtocolError('replayed social event')
            self.received[sender] = nonce
            await self.channel.send(SOCIAL_RECEIPT, RECEIPT.pack(sender, nonce))
            return {'interaction': 'greet' if interaction == 1 else 'documents', 'rp_sender': sender}
        if kind == SOCIAL_RESULT:
            if len(payload) != RESULT.size:
                raise ProtocolError('invalid social result size')
            nonce, outcome = RESULT.unpack(payload)
            labels = {DENIED: 'denied', RECEIVED: 'recipient_received', CANCELLED: 'cancelled'}
            if nonce != self.pending or outcome not in labels:
                raise ProtocolError('unexpected social result')
            self.pending = None
            return {'interaction_result': labels[outcome], 'nonce': nonce}
        raise ProtocolError('unexpected social record')


async def run(config_path, enable_social=False):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    root = config_path.resolve().parent
    credentials = Credentials(*(root / config[key] for key in ('certificate', 'private_key', 'trusted_ca')))
    client = await PrivateClient.connect((config['host'], config['port']), credentials,
                   bytes.fromhex(config['server_sha256']), config['rp_id'], hostname=config['host'])

    def print_snapshot():
        print(json.dumps({'revision': client.revision, 'members':
              [dict(zip(FIELDS, row)) for row in client.members.values()]}), flush=True)

    social = SocialClient(client) if enable_social else None
    if social is not None:
        try:
            await social.open()
            if client.revision:
                print_snapshot()
        except BaseException:
            await client.close()
            raise

    async def receive():
        while True:
            kind, payload = await client.receive()
            if kind == ACK:
                print(json.dumps({'decision': 'applied' if payload[6] == 2 else 'denied',
                      'operation': payload[5], 'nonce': int.from_bytes(payload[32:40], 'little')}), flush=True)
            elif kind == SNAPSHOT:
                print_snapshot()
            elif social is not None and kind in (SOCIAL_EVENT, SOCIAL_RESULT):
                print(json.dumps(await social.consume(kind, payload)), flush=True)

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
        if social is not None:
            print('For an opted-in RP peer: greet <id> or documents <id>', flush=True)
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
                target = int(words[1]) if len(words) == 2 else client.identity
                if not 0 < target < 2**64:
                    raise ValueError('invalid target')
                if social is not None and words[0] in SOCIAL_COMMANDS:
                    await social.request(SOCIAL_COMMANDS[words[0]], target)
                    continue
                operation = OPERATIONS[words[0]]
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
    parser.add_argument('--social', action='store_true', help='enable optional PRP3 notifications')
    args = parser.parse_args()
    try:
        asyncio.run(run(args.config, args.social))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == '__main__':
    main()
