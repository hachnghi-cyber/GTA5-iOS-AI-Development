#!/usr/bin/env python3
"""Read-only arm64 BL cross references for exactly GTA5 v12.

No hooking, IPA writing or heuristic patching. An absence of a BL xref does
not establish the absence of an indirect/virtual callback.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

EXPECTED_GTA5 = "d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b"
EXPECTED_UUID = "6a498e32e70c334cbca3affd35e8d171"
BASE = 0x100000000
TARGETS = {
    "MacportOnlineUpdate": 0x1000E01A0,
    "MacportJobsUpdate": 0x1000EA024,
    "MacportWorkTaskFrame": 0x100112010,
    "MacportWorkArrestScene": 0x10011BC8C,
}

def sections(blob):
    if len(blob)<32 or struct.unpack_from('<I',blob)[0]!=0xfeedfacf:
        raise ValueError('not Mach-O64')
    _,cpu,_,filetype,n,cmdsize,_,_=struct.unpack_from('<IiiIIIII',blob)
    if cpu!=0x100000c or filetype!=2 or n>4096 or 32+cmdsize>len(blob):
        raise ValueError('not expected arm64 executable')
    at=32; found=[]; uuid=None
    for _ in range(n):
        cmd,cs=struct.unpack_from('<II',blob,at)
        if cs<8 or at+cs>32+cmdsize:
            raise ValueError('bad Mach-O load command')
        if cmd==0x1b:
            if cs<24:raise ValueError('short UUID')
            uuid=blob[at+8:at+24].hex()
        if cmd==0x19:
            if cs<72:raise ValueError('short segment')
            nsec=struct.unpack_from('<I',blob,at+64)[0]
            if 72+80*nsec>cs:raise ValueError('bad section count')
            for i in range(nsec):
                off=at+72+i*80
                sect,seg,addr,size,fileoff=struct.unpack_from('<16s16sQQI',blob,off)
                if sect.rstrip(b'\0')==b'__text' and seg.rstrip(b'\0')==b'__TEXT':
                    if fileoff+size>len(blob) or size%4:
                        raise ValueError('bad __text boundaries')
                    found.append((addr,size,fileoff))
        at+=cs
    if uuid!=EXPECTED_UUID or len(found)!=1:
        raise ValueError('not verified v12 UUID/text section')
    return found[0]

def scan(blob):
    if hashlib.sha256(blob).hexdigest()!=EXPECTED_GTA5:
        raise ValueError('Unexpected GTA5 SHA-256: refusing analysis')
    addr,size,off=sections(blob)
    xrefs={k:[] for k in TARGETS}
    inverted={v:k for k,v in TARGETS.items()}
    # ARM64 BL immediate encoding: op[31:26] = 0b100101, signed imm26 << 2.
    for i in range(off,off+size,4):
        insn=struct.unpack_from('<I',blob,i)[0]
        if (insn & 0xfc000000)!=0x94000000:continue
        imm=insn & 0x03ffffff
        if imm & (1<<25):imm-=1<<26
        pc=addr+(i-off)
        target=pc+imm*4
        if target in inverted:
            xrefs[inverted[target]].append({
                'caller_vmaddr':f'0x{pc:016x}', 'call_instruction':f'0x{insn:08x}',
                'target_vmaddr':f'0x{target:016x}'})
    return {'read_only':True,'source_gta5_sha256':EXPECTED_GTA5,'uuid':EXPECTED_UUID,
            'text_section_va':f'0x{addr:016x}','text_section_bytes':size,
            'targets':{name:{'vmaddr':f'0x{target:016x}',
                             'direct_BL_calls':xrefs[name],
                             'direct_BL_count':len(xrefs[name])}
                       for name,target in TARGETS.items()},
            'interpretation':(
              'MacportJobsUpdate and MacportWorkTaskFrame receive direct BL calls '
              'from within MacportOnlineUpdate. A zero direct BL count for '
              'MacportOnlineUpdate does not rule out an indirect callback. '
              'No game-thread/transport hook is verified.'),
            'ipa_modified':False,'hook_installed':False,'ipa_playable':False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('ipa',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.ipa) as z:
        blob=z.read('Payload/GTAV.app/GTA5')
    result=scan(blob)
    data=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.output:args.output.write_text(data,encoding='utf-8')
    else:print(data)
if __name__=='__main__':main()
