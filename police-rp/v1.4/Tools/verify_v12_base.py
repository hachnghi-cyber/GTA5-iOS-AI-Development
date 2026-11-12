#!/usr/bin/env python3
"""Read-only exact-version gate for GTA V iOS v12 baseline.
No Mach-O edits. This tool refuses other IPA versions.
"""
import hashlib
import struct
import sys
import zipfile
from pathlib import Path
EXPECTED_GTA5_SHA256 = 'd252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b'
EXPECTED_UUID = '6a498e32e70c334cbca3affd35e8d171'

def inspect(path):
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad is not None: raise ValueError(f'Bad archive: {bad}')
        exe=z.read('Payload/GTAV.app/GTA5')
        assert z.getinfo('Payload/GTAV.app/GTA5').file_size == len(exe)
        for required in ('Payload/GTAV.app/Frameworks/Menyoo.shv.dylib',
                         'Payload/GTAV.app/Frameworks/ScriptHookV.dylib',
                         'Payload/GTAV.app/Frameworks/libgtacompat.dylib'):
            assert required in z.namelist(),f'missing {required}'
    digest=hashlib.sha256(exe).hexdigest()
    if digest!=EXPECTED_GTA5_SHA256:
        raise ValueError('Wrong GTA5 build; refuse to use symbol offsets')
    magic,cputype,subtype,filetype,ncmds,sizeofcmds,flags,reserved=struct.unpack_from('<IIIIIIII',exe,0)
    if magic!=0xfeedfacf or cputype!=0x100000c or filetype!=2: raise ValueError('Not ARM64 Mach-O executable')
    offset=32
    uuid=None
    for i in range(ncmds):
        cmd,size=struct.unpack_from('<II',exe,offset)
        if size<8 or offset+size>32+sizeofcmds: raise ValueError('Invalid load command')
        if cmd==0x1b:uuid=exe[offset+8:offset+24].hex()
        offset+=size
    if uuid!=EXPECTED_UUID:raise ValueError(f'Wrong UUID: {uuid}')
    print(f'PASS: v12 original GTA5; UUID={uuid}; SHA256={digest}')
    print('No binary patches performed. No Police RP runtime hook present.')

if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit(f'usage: {sys.argv[0]} /path/to/v12.ipa')
    inspect(Path(sys.argv[1]))
