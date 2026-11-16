#!/usr/bin/env python3
"""Static, exact-binary audit of the ScriptHookV API chosen for RBP.
A symbol, hash literal or branch instruction is NOT proof of runtime invocation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import uuid
import zipfile

EXPECTED_SHV_UUID='F768B7B5-AD75-39F4-83D3-8E49234325B5'
EXPECTED_OFFSETS={
    '_sh_game_start':0x4bec,
    '_scriptRegister':0x59a0,
    '_scriptWait':0x569c,
    '_nativeInit':0x5720,
    '_nativePush64':0x5734,
    '_nativeCall':0x575c,
}
HUD_HASHES={
    'BEGIN_TEXT_COMMAND_PRINT':0xB87A37EEB7FAA67D,
    'ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME':0x6C188BE134E074AA,
    'END_TEXT_COMMAND_PRINT':0x9D77056A530643F6,
}

def static_audit(shv:bytes):
    if len(shv)<32: raise ValueError('short Mach-O')
    hdr=struct.unpack_from('<IiiIIIII',shv,0)
    magic,cpu,_,_,ncmds,cmds_size,_,_=hdr
    if magic!=0xfeedfacf or cpu!=0x0100000c or ncmds>512 or 32+cmds_size>len(shv):
        raise ValueError('not an ARM64 Mach-O 64 with bounded commands')
    pos=32
    image_uuid=None
    symtab=None
    for _ in range(ncmds):
        if pos+8>len(shv):raise ValueError('truncated load command')
        cmd,size=struct.unpack_from('<II',shv,pos)
        if size<8 or pos+size>32+cmds_size:raise ValueError('out-of-bounds load command')
        if cmd==0x1b and size>=24:image_uuid=str(uuid.UUID(bytes=shv[pos+8:pos+24])).upper()
        if cmd==0x2 and size>=24:symtab=struct.unpack_from('<IIII',shv,pos+8)
        pos+=size
    if symtab is None:raise ValueError('Mach-O has no LC_SYMTAB')
    symoff,nsyms,stroff,strsize=symtab
    if nsyms>300000 or stroff+strsize>len(shv) or symoff+nsyms*16>len(shv):
        raise ValueError('out of bounds symbol table')
    symbols={}
    for i in range(nsyms):
        strx,typ,sect,desc,val=struct.unpack_from('<IBBHQ',shv,symoff+i*16)
        if strx>=strsize or not strx:continue
        start=stroff+strx
        end=shv.find(b'\x00',start,stroff+strsize)
        if end<start:continue
        name=shv[start:end].decode('utf-8','replace')
        if name in EXPECTED_OFFSETS and (typ & 0x0e)==0x0e: symbols[name]=val
    return {
        'status':'STATIC_ONLY',
        'sha256':hashlib.sha256(shv).hexdigest(),
        'uuid':image_uuid,
        'uuid_matches_baseline':image_uuid==EXPECTED_SHV_UUID,
        'function_offsets':{name:{'observed':symbols.get(name),
                                  'expected':off,'matches':symbols.get(name)==off}
                            for name,off in EXPECTED_OFFSETS.items()},
        'hud_hash_literals':{name:{'hash':f'0x{h:016X}',
                                  'little_endian_occurrences':shv.count(h.to_bytes(8,'little')),
                                  'name_in_binary':(name.encode() in shv)}
                             for name,h in HUD_HASHES.items()},
        'scripthook_off_sentinel_name_present':b'posthook/scripthook-off' in shv,
        'api_symbol_locations_match':all(symbols.get(name)==off for name,off in EXPECTED_OFFSETS.items()),
        'native_action_executed':False,
        'signed_ios_dylib_created':False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('ipa',type=Path)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.ipa) as z:
        shv=z.read('Payload/GTAV.app/Frameworks/ScriptHookV.dylib')
    r=static_audit(shv)
    serialized=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
    if a.out:a.out.write_text(serialized)
    print(serialized,end='')
    if not (r['uuid_matches_baseline'] and r['api_symbol_locations_match']):return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
