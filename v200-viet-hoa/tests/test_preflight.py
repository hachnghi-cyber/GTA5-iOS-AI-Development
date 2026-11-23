#!/usr/bin/env python3
"""Synthetic test pack; no game data."""
import json
from pathlib import Path
import struct
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from preflight_pack import inspect

def reject(file,reason):
    try: inspect(file)
    except ValueError: return
    raise AssertionError('Unexpectedly accepted '+reason)

def pack(name='x64/data/lang/american.rpf/demo.gxt2',text=b'Vi\xe1\xbb\x87t Nam'):
    text=text+b'\0'
    gxt=b'2TXG'+struct.pack('<I',1)+struct.pack('<II',123,24)+b'2TXG'+struct.pack('<I',24+len(text))+text
    idx=json.dumps([[name,0,len(gxt)]],separators=(',',':')).encode()
    return b'NOVAPAK1'+struct.pack('<Q',len(idx))+idx+gxt

with tempfile.TemporaryDirectory() as directory:
    file=Path(directory)/'test.nvp'
    file.write_bytes(pack())
    result=inspect(file)
    assert result['entries']==1 and result['text_entries']==1
    file.write_bytes(pack(text=b'\xff'))
    reject(file,'invalid UTF8')
    file.write_bytes(pack(name='x64/data/network/session.xml'))
    reject(file,'Online asset')
    file.write_bytes(pack(name='x64/data/lang/american.rpf/a/../demo.gxt2'))
    reject(file,'traversal')
    file.write_bytes(pack()[:-1])
    reject(file,'truncated')
    file.write_bytes(pack()+b'junk')
    reject(file,'trailing bytes')
    file.write_bytes(b'INVALID!'+pack()[8:])
    reject(file,'magic')
    print('PASS: Story-mode-only preflight of synthetic GXT2 and invalid packs')
