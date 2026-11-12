#!/usr/bin/env python3
"""Verify native police-duty offsets against *this exact* GTA V iOS v12 binary.
Works offline. It does not patch or sign the IPA.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import zipfile

MACHO_MAGIC_64 = 0xFEEDFACF
CPU_ARM64 = 0x0100000C
UUID = bytes.fromhex('6A498E32E70C334CBCA3AFFD35E8D171')
MAIN_BASE = 0x100000000
WORK_KIND_TABLE = 0x10261A3A0
JOB_INDEX = 0x1027B1B2C
ON_SHIFT = 0x10355EE34
EXPECTED_NAMES = ('cop_ls', 'cop_sandy', 'cop_paleto')


def binary(source):
    if source.suffix.lower() == '.ipa':
        with zipfile.ZipFile(source) as z:
            return z.read('Payload/GTAV.app/GTA5')
    return source.read_bytes()


def macho(binary):
    if len(binary) < 4096:
        raise ValueError('GTA5 too small')
    magic, cputype, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from('<IiiIIIII', binary, 0)
    if magic != MACHO_MAGIC_64 or cputype != CPU_ARM64:
        raise ValueError('Expected Mach-O arm64')
    offset = 32
    sections = []
    uid = None
    for _ in range(ncmds):
        command, size = struct.unpack_from('<II', binary, offset)
        if size < 8 or offset + size > len(binary):
            raise ValueError('Malformed Mach-O load command')
        if command == 0x1B:
            uid = binary[offset+8:offset+24]
        elif command == 0x19:
            _,_,segname,addr,vmsize,fileoff,filesize,_,_,nsects,_ = struct.unpack_from('<II16sQQQQiiII',binary,offset)
            if fileoff + filesize > len(binary):
                raise ValueError('Malformed segment size')
            sections.append((segname.rstrip(b'\x00').decode('ascii'),addr,vmsize,fileoff,filesize))
        offset += size
    if uid != UUID:
        raise ValueError('Unsupported GTA5 UUID: ' + str(uid.hex() if uid else None))
    def mem(addr, count, zero_fill=False):
        for name,base,vm_size,file_off,file_size in sections:
            if base <= addr and addr+count <= base+vm_size:
                at = addr-base
                if at+count<=file_size:return binary[file_off+at:file_off+at+count]
                if zero_fill:return b'\x00'*count
        raise ValueError('Unmapped memory address '+hex(addr))
    # kMacportWorkJobs is an array of 72-byte records. The first field is a chained
    # fixup pointer to the job's key. For this binary, low 32 bits encode VM offset.
    actual=[]
    for idx in range(3):
        raw_ptr = struct.unpack('<Q',mem(WORK_KIND_TABLE+idx*72,8))[0]
        strptr = MAIN_BASE + (raw_ptr & 0xffffffff)
        txt = mem(strptr,32).split(b'\x00')[0].decode('utf-8')
        actual.append(txt)
    if tuple(actual)!=EXPECTED_NAMES:
        raise ValueError('Native job enumeration changed: '+str(actual))
    idx_before = struct.unpack('<i',mem(JOB_INDEX,4))[0]
    if idx_before != -1:
        raise ValueError('Unexpected initial native job value '+str(idx_before))
    # This byte lives in __DATA,__bss, not as a byte on disk. Validate its range.
    if not any(name=='__DATA' and addr<=ON_SHIFT<addr+vmsize
                for name,addr,vmsize,_,_ in sections):
        raise ValueError('OnShift is not within __DATA')
    return {'uuid':uid.hex().upper(),'sha256':hashlib.sha256(binary).hexdigest(),
            'jobs':actual,'job_offset':hex(JOB_INDEX-MAIN_BASE),
            'duty_offset':hex(ON_SHIFT-MAIN_BASE),'initial_job':idx_before,
            'ready_for_runtime_probe':True}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('file',type=Path,help='GTAV-v12(1).ipa or Payload/GTAV.app/GTA5')
    args=p.parse_args()
    try:
        result=macho(binary(args.file))
    except Exception as exc:
        print('FAILED:',str(exc),file=sys.stderr)
        sys.exit(1)
    for key,value in result.items():
        print(f'{key}: {value}')
    print('STATIC CHECK PASS. This does NOT verify P/Invoke inside iOS ScriptHook.')

if __name__=='__main__': main()
