"""Run a private LAN kit with account login. Use a separate terminal for each login."""
import argparse
import asyncio
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from prepare_private_rp import prepare
from rp_private_server import serve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True, type=Path)
    commands = parser.add_subparsers(dest='action', required=True)
    start = commands.add_parser('start')
    start.add_argument('--ip', required=True, type=ipaddress.IPv4Address)
    start.add_argument('--library', required=True, type=Path)
    start.add_argument('--port', type=int, default=30133)
    start.add_argument('--login-port', type=int, default=30443)
    for action in ('add', 'reset'):
        account = commands.add_parser(action)
        account.add_argument('username')
        account.add_argument('--rp-id', required=True, type=int, choices=(11, 22))
    commands.add_parser('login')
    args = parser.parse_args()
    folder = args.folder.resolve()
    tools = Path(__file__).resolve().parent
    pointer = folder / 'current-kit.json'
    if args.action == 'start':
        args.host = str(args.ip)
        kit = folder / ('kit-' + secrets.token_hex(8))
        prepare(kit, args.ip, args.port, panel=True, login_port=args.login_port)
        args.config = kit / 'server.json'

        def ready():
            tmp = kit / 'current.tmp'
            tmp.write_text(json.dumps(kit.name), encoding='utf-8')
            os.replace(tmp, pointer)
            print('Hồ sơ iPhone của lượt này:', kit, flush=True)
        async def serve_kit():
            # The installed v13.3 panel reads a 20-minute profile on launch.
            async with asyncio.timeout(1200):
                await serve(args, ready=ready)

        try:
            asyncio.run(serve_kit())
        except TimeoutError:
            print('Lượt thử đã hết 20 phút. Mở lại server để tạo hồ sơ mới.')
        except KeyboardInterrupt:
            pass
    elif args.action == 'login':
        if not pointer.is_file():
            parser.error('Hãy khởi động server trước.')
        kit = folder / json.loads(pointer.read_text(encoding='utf-8'))
        subprocess.run([sys.executable, str(tools / 'rp_laptop_login.py'), '--config',
                        str(kit / 'server.json')], check=True)
    else:
        subprocess.run([sys.executable, str(tools / 'rp_accounts.py'), '--database',
                        str(folder / 'rp-accounts.sqlite3'), args.action, args.username,
                        '--rp-id', str(args.rp_id)], check=True)


if __name__ == '__main__':
    main()
