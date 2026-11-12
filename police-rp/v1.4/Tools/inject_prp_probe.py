#!/usr/bin/env python3
"""Offline/reversible opt-in diagnostic-only Mach-O loader integration for exactly GTA V iOS v12.
Usage: python Tools/inject_prp_probe.py original.ipa PoliceRPProbe.dylib --out diagnostic-unsigned.ipa
Never run on a different version. No game hooks, ScriptHook changes or Police RP gameplay.
Output MUST be re-signed by the user's authorized installer before use.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import struct
import zipfile
from pathlib import Path

GTA_PATH = 'Payload/GTAV.app/GTA5'
DYLIB_PATH = 'Payload/GTAV.app/Frameworks/PoliceRPProbe.dylib'
LOAD_NAME = '@executable_path/Frameworks/PoliceRPProbe.dylib'
GTA_SHA256 = 'd252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b'
GTA_UUID = bytes.fromhex('6a498e32e70c334cbca3affd35e8d171')
MH_MAGIC_64 = 0xFEEDFACF
MH_EXECUTE = 2
MH_DYLIB = 6
CPU_TYPE_ARM64 = 0x0100000c
LC_SEGMENT_64 = 0x19
LC_UUID = 0x1b
LC_LOAD_DYLIB = 0x0c
LC_ID_DYLIB = 0x0d
LC_BUILD_VERSION = 0x32

class ProbeError(ValueError): pass

def sha(b): return hashlib.sha256(b).hexdigest()

def parse_macho(data: bytes, filetype: int):
    if len(data) < 32: raise ProbeError('Mach-O too short')
    magic, cpu, subtype, kind, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<8I',data)
    if magic != MH_MAGIC_64 or cpu != CPU_TYPE_ARM64 or kind != filetype:
        raise ProbeError('Need arm64 Mach-O with requested filetype')
    if ncmds > 512 or sizeofcmds > 1048576 or 32+sizeofcmds>len(data):
        raise ProbeError('Corrupted load command sizes')
    commands=[]; off=32; uuid=None; min_data=None; platform=None; names=[]; id_name=None
    for i in range(ncmds):
        if off+8>32+sizeofcmds: raise ProbeError('Load command truncated')
        cmd, size=struct.unpack_from('<II',data,off)
        if size < 8 or size % 8 or off+size>32+sizeofcmds: raise ProbeError('Bad Mach-O load command')
        commands.append((cmd, off, size))
        if cmd==LC_UUID and size>=24: uuid=data[off+8:off+24]
        if cmd==LC_SEGMENT_64 and size>=72:
            fileoff,filesize=struct.unpack_from('<QQ',data,off+40)
            nsects=struct.unpack_from('<I',data,off+64)[0]
            if nsects > 256 or size<72+80*nsects:
                raise ProbeError('Malformed segment sections')
            if filesize and fileoff:
                min_data=fileoff if min_data is None else min(min_data,fileoff)
            # For __TEXT, segment fileoff is zero while its first actual code
            # section is usually at 0x4000. Do NOT assume all bytes up to the
            # next nonzero SEGMENT fileoff are available header padding!
            for sec_i in range(nsects):
                section_off=off+72+80*sec_i
                section_fileoff=struct.unpack_from('<I',data,section_off+48)[0]
                section_size=struct.unpack_from('<Q',data,section_off+40)[0]
                if section_size and section_fileoff:
                    min_data=section_fileoff if min_data is None else min(min_data,section_fileoff)
        if cmd==LC_BUILD_VERSION and size>=24:
            platform=struct.unpack_from('<I',data,off+8)[0]
        if cmd in (LC_LOAD_DYLIB,LC_ID_DYLIB) and size>=24:
            start=struct.unpack_from('<I',data,off+8)[0]
            if start < 24 or start>=size: raise ProbeError('Invalid load dylib name')
            s=data[off+start:off+size].split(b'\0')[0]
            if cmd==LC_LOAD_DYLIB: names.append(s.decode('utf-8'))
            else: id_name=s.decode('utf-8')
        off+=size
    if off!=32+sizeofcmds: raise ProbeError('Mach-O header commands do not align')
    return dict(ncmds=ncmds, sizeofcmds=sizeofcmds, end=off, first_segment_data=min_data,
                uuid=uuid, platform=platform, load_names=names, dylib_id=id_name, commands=commands)

def dylib_check(dylib: bytes):
    v=parse_macho(dylib,MH_DYLIB)
    # The iOS device platform is 2. macOS = 1. Reject macOS and simulator.
    if v['platform']!=2: raise ProbeError(f'Not an iOS-device dylib (LC_BUILD_VERSION platform={v["platform"]})')
    if v['dylib_id']!=LOAD_NAME: raise ProbeError('Unexpected dylib install_name; rebuild the correct v1.4 probe')
    return v

def make_load_cmd(name=LOAD_NAME):
    s=name.encode()+b'\0'
    n=(24+len(s)+7)&~7
    # dylib_command: cmd, cmdsize, name_offset, timestamp, current_version, compatibility_version
    return struct.pack('<6I', LC_LOAD_DYLIB,n,24,2,0x10000,0x10000)+s.ljust(n-24,b'\0')

def inject_macho(exe: bytes, *, require_digest=True):
    if require_digest and sha(exe)!=GTA_SHA256:
        raise ProbeError('Wrong GTA5 original SHA-256; refuse to patch')
    p=parse_macho(exe,MH_EXECUTE)
    if p['uuid']!=GTA_UUID: raise ProbeError('Wrong GTA5 UUID; refuse to patch')
    if LOAD_NAME in p['load_names']: raise ProbeError('Probe already installed')
    cmd=make_load_cmd()
    if not p['first_segment_data']:
        raise ProbeError('No segment offsets to check header slack')
    start=p['end']; stop=start+len(cmd)
    if stop>p['first_segment_data'] or stop>len(exe):
        raise ProbeError('Insufficient reserved Mach-O header space')
    if any(exe[start:stop]):
        raise ProbeError('Header slack is not zero; refusing to overwrite')
    out=bytearray(exe)
    struct.pack_into('<I',out,16,p['ncmds']+1)
    struct.pack_into('<I',out,20,p['sizeofcmds']+len(cmd))
    out[start:stop]=cmd
    chk=parse_macho(out,MH_EXECUTE)
    if chk['ncmds']!=p['ncmds']+1 or LOAD_NAME not in chk['load_names']:
        raise ProbeError('Reparse failed')
    # Ensure only intended bytes changed (ncmds, sizeofcmds, load command).
    diffs=[i for i,(a,b) in enumerate(zip(exe,out)) if a!=b]
    if any(i not in {*range(16,24),*range(start,stop)} for i in diffs):
        raise ProbeError('Unexpected executable mutation')
    return bytes(out),dict(load_cmd_offset=start,load_cmd_bytes=len(cmd),bytes_changed=len(diffs),
                            original_sha256=sha(exe),diagnostic_sha256=sha(out))

def create_diagnostic_ipa(original: Path, dylib_path: Path, output: Path):
    if not original.is_file() or not dylib_path.is_file():
        raise ProbeError('Original IPA and built iOS dylib must exist')
    if original.resolve()==output.resolve(): raise ProbeError('Never overwrite original IPA')
    dylib=dylib_path.read_bytes();dylib_check(dylib)
    if output.exists(): raise ProbeError('Refusing to overwrite existing output')
    with zipfile.ZipFile(original) as src:
        if src.testzip() is not None: raise ProbeError('Corrupt source IPA')
        if DYLIB_PATH in src.namelist(): raise ProbeError('IPA already contains diagnostic probe')
        if src.namelist().count(GTA_PATH)!=1 or len(src.namelist())!=len(set(src.namelist())):
            raise ProbeError('Missing or duplicated IPA entries')
        exe=src.read(GTA_PATH)
        patched,details=inject_macho(exe)
        tmp=output.with_suffix(output.suffix+'.tmp')
        try:
            with zipfile.ZipFile(tmp,'w') as dst:
                for info in src.infolist():
                    if info.filename==GTA_PATH: dst.writestr(info,patched)
                    else: dst.writestr(info,src.read(info.filename))
                di=zipfile.ZipInfo(DYLIB_PATH)
                di.create_system=3
                di.external_attr=(0o100755 << 16)
                di.compress_type=zipfile.ZIP_DEFLATED
                dst.writestr(di,dylib)
            with zipfile.ZipFile(tmp) as verify:
                if verify.testzip() is not None: raise ProbeError('Output IPA failed CRC')
                if verify.read(DYLIB_PATH)!=dylib: raise ProbeError('Dylib changed while packaging')
                if verify.read(GTA_PATH)!=patched: raise ProbeError('Game executable changed while packaging')
                for info in src.infolist():
                    if info.filename!=GTA_PATH and src.read(info.filename)!=verify.read(info.filename):
                        raise ProbeError(f'Original IPA member changed: {info.filename}')
            os.replace(tmp,output)
        finally:
            if tmp.exists(): tmp.unlink()
    return details | dict(ipa_source=str(original),ipa_output=str(output),dylib_sha256=sha(dylib),
                          original_ipa_sha256=sha(original.read_bytes()),output_ipa_sha256=sha(output.read_bytes()),
                          executable_changed_only_load_commands=True,gameplay_hook_installed=False,
                          real_police_network_connected=False,requires_resigning=True)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('original_ipa',type=Path)
    a.add_argument('ios_dylib',type=Path)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args()
    try: report=create_diagnostic_ipa(args.original_ipa,args.ios_dylib,args.out)
    except (KeyError,zipfile.BadZipFile,ProbeError,ValueError) as exc:
        a.exit(2,f'REFUSED: {exc}\n')
    report_path=args.out.with_name(args.out.stem+'.verify.json')
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('PASS: UNSIGNED diagnostic-only IPA created. Not a Police RP gameplay build.')
    print('Output:',args.out)
    print('Report:',report_path)

if __name__=='__main__':main()
