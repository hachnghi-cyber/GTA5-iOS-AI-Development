#!/usr/bin/env python3
"""Create a PC -> physical iPhone RBP1 diagnostic pair (not GTA RAGE Online).

The two keys are intentionally only stored locally in protected files. Avoid
sharing .cfg or pasting its contents into chat, logs, version control, or CI.
"""
import argparse
import ipaddress
import os
from pathlib import Path
import secrets

from make_two_phone_configs import make_config


def make_pair(pc_ip, iphone_ip, pc_port=47880, iphone_port=47881):
    pc_addr, iphone_addr = ipaddress.IPv4Address(pc_ip), ipaddress.IPv4Address(iphone_ip)
    for ip in (pc_addr, iphone_addr):
        if ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise ValueError('Use real, LAN-reachable unicast IPv4 addresses, not loopback/link-local/multicast')
    if pc_addr == iphone_addr:
        raise ValueError('PC and iPhone need distinct IPv4 addresses')
    for port in (pc_port, iphone_port):
        if not 1024 <= port <= 65535:
            raise ValueError('UDP ports must be 1024..65535')
    if pc_port == iphone_port:
        raise ValueError('Use distinct PC/iPhone UDP ports for ease of diagnosis')
    ida, idb, session, key = (secrets.token_bytes(n) for n in (16, 16, 16, 32))
    pc = make_config('sender', pc_port, iphone_port, str(iphone_addr), ida, idb, session, key)
    iphone = make_config('receiver', iphone_port, pc_port, str(pc_addr), idb, ida, session, key)
    return pc, iphone


def atomic_create_pair(output_dir, pc, iphone):
    """Never overwrite or leave a half-created pair on ordinary error."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = (out / 'PC_sender.cfg', out / 'iPhone_RBPProbe.cfg')
    if any(path.exists() for path in paths):
        raise FileExistsError('Existing configs found; choose a new directory to rotate credentials')
    completed = []
    try:
        for path, data in zip(paths, (pc, iphone)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            completed.append(path)
            try:
                with os.fdopen(fd, 'w', encoding='ascii') as f:
                    f.write(data)
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
    except BaseException:
        for path in completed:
            path.unlink(missing_ok=True)
        raise
    return paths


def main(argv=None):
    p = argparse.ArgumentParser(description='Create PC sender + iPhone receiver configs for RBP1 E3 only')
    p.add_argument('--pc-ip', required=True, help='Actual Wi-Fi/LAN IPv4 of PC')
    p.add_argument('--iphone-ip', required=True, help='Actual Wi-Fi IPv4 of iPhone')
    p.add_argument('--pc-port', type=int, default=47880)
    p.add_argument('--iphone-port', type=int, default=47881)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(argv)
    try:
        pc, iphone = make_pair(a.pc_ip, a.iphone_ip, a.pc_port, a.iphone_port)
        paths = atomic_create_pair(a.output_dir, pc, iphone)
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print('Created:', paths[0].name, 'and', paths[1].name)
    print('Copy iPhone_RBPProbe.cfg to GTAV Documents/RBPProbe.cfg (rename filename).')
    print('Keep BOTH files private; rotate after testing. No game commands are supported.')


if __name__ == '__main__':
    main()
