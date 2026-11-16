#!/usr/bin/env python3
"""Compare Mach-O ARM64 executable code and UUID across re-signing.

Re-signing can change LC_CODE_SIGNATURE and whole-binary SHA256.
Matching __TEXT,__text is stronger evidence code bytes are unchanged,
but it does NOT prove behavior/runtime compatibility.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

MH_MAGIC_64=0xFEEDFACF
LC_SEGMENT_64=0x19
LC_UUID=0x1B

def identity(path):
    b=Path(path).read_bytes()
    if len(b)<32:raise ValueError('truncated header')
    magic,cpu,sub,filetype,ncmds,szcmds,flags,res=struct.unpack_from('<IiiIIIII',b)
    if magic!=MH_MAGIC_64 or cpu!=0x0100000c:raise ValueError('expected ARM64 Mach-O 64')
    if ncmds>512 or 32+szcmds>len(b):raise ValueError('invalid load commands')
    offset=32; uuid=None; text=None; signature=None
    for _ in range(ncmds):
        if offset+8>len(b):raise ValueError('truncated LC')
        cmd,size=struct.unpack_from('<II',b,offset)
        if size<8 or offset+size>len(b):raise ValueError('invalid LC size')
        if cmd==LC_UUID:
            if size<24:raise ValueError('bad UUID load command')
            import uuid as uid
            uuid=str(uid.UUID(bytes=b[offset+8:offset+24])).upper()
        if cmd==LC_SEGMENT_64:
            if size<72:raise ValueError('bad segment load command')
            nsects=struct.unpack_from('<I',b,offset+64)[0]
            if nsects>1024 or 72+nsects*80>size:raise ValueError('bad section array')
            for k in range(nsects):
                sec_off=offset+72+80*k
                secname,segname,addr,nbytes,fileoff=struct.unpack_from('<16s16sQQI',b,sec_off)
                if secname.rstrip(b'\0')==b'__text' and segname.rstrip(b'\0')==b'__TEXT':
                    if fileoff+nbytes>len(b):raise ValueError('bad __text bounds')
                    text={'sha256':hashlib.sha256(b[fileoff:fileoff+nbytes]).hexdigest(),
                          'size':nbytes,'file_offset':fileoff}
        if cmd==0x1d:  # LC_CODE_SIGNATURE
            if size>=16:signature=struct.unpack_from('<II',b,offset+8)
        offset+=size
    if not uuid or not text:raise ValueError('no LC_UUID or __TEXT,__text')
    return {'path':str(path),'uuid':uuid,'file_sha256':hashlib.sha256(b).hexdigest(),
            'text':text,'signature':signature}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('original');parser.add_argument('resigned')
    args=parser.parse_args()
    a,b=identity(args.original),identity(args.resigned)
    same=(a['uuid']==b['uuid'] and a['text']==b['text'])
    print(json.dumps({'code_preserved':same,'original':a,'resigned':b},indent=2))
    if not same:raise SystemExit(1)
if __name__=='__main__':main()
