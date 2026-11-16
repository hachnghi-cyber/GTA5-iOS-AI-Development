#!/usr/bin/env python3
"""Generate TWO strictly diagnostic RBP1 test configs with ephemeral secrets.

This is not a GTA player identity or RAGE session credential. Keys are
stored plaintext in the Files sandbox for testing ONLY; rotate each test.
"""
import argparse
import ipaddress
from pathlib import Path
import secrets
import os


def make_config(mode, local_port, peer_port, peer_ip, self_id, other_id, session, key):
    return '\n'.join([
        '# RBP1 diagnostic PING only. NEVER use for production privileges.',
        f'mode={mode}', f'listen_port={local_port}', f'peer_port={peer_port}',
        f'peer_ipv4={peer_ip}',f'self_id_hex={self_id.hex()}',
        f'peer_id_hex={other_id.hex()}', f'session_hex={session.hex()}',
        f'key_hex={key.hex()}',''
    ])

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--a-ip',required=True,help='iPhone A IPv4 address on LAN')
    p.add_argument('--b-ip',required=True,help='iPhone B IPv4 address on LAN')
    p.add_argument('--port-a',type=int,default=47880)
    p.add_argument('--port-b',type=int,default=47881)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    for ip in (a.a_ip,a.b_ip):ipaddress.IPv4Address(ip)
    for port in (a.port_a,a.port_b):
        if not 1024<=port<=65535:p.error('port must be 1024..65535')
    if a.port_a==a.port_b:p.error('use distinct ports')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    pa=a.output_dir/'iPhone_A_RBPProbe.cfg'
    pb=a.output_dir/'iPhone_B_RBPProbe.cfg'
    if pa.exists() or pb.exists():p.error('refuse to overwrite secrets')
    ida,idb,sess,key=(secrets.token_bytes(n) for n in (16,16,16,32))
    for path,content in [
        (pa,make_config('sender',a.port_a,a.port_b,a.b_ip,ida,idb,sess,key)),
        (pb,make_config('receiver',a.port_b,a.port_a,a.a_ip,idb,ida,sess,key))]:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='ascii') as f:f.write(content)
    print(f'Created {pa.name} and {pb.name}; each must be installed as Documents/RBPProbe.cfg on its own phone.')
    print('Rotate BOTH configs whenever either game restarts; never share the secret in logs or chats.')

if __name__=='__main__':main()
