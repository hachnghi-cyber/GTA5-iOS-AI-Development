#!/usr/bin/env python3
"""Read-only Mach-O fingerprinting of v12 candidate functions.
No code patching, no runtime hooks and no IPA mutation are performed.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

EXPECTED_GTA5_SHA = 'd252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b'
EXPECTED_UUID = '6a498e32e70c334cbca3affd35e8d171'
CANDIDATES = {
    'MacportOnlineUpdate': (0x1000e01a0, 'Online update path; still need to prove game-thread callback and transport provenance.'),
    'MacportJobsUpdate': (0x1000ea024, 'Jobs frame logic; cannot assume it runs when a local player is outside the job UI.'),
    'MacportWorkTaskFrame': (0x100112010, 'NPC task-specific; NOT suitable as a global Police RP frame callback.'),
    'MacportWorkArrestScene': (0x10011bc8c, 'NPC arrest animation; DO NOT pass remote player ped handles to this function.'),
}

def inspect(blob):
    if hashlib.sha256(blob).hexdigest() != EXPECTED_GTA5_SHA:
        raise ValueError('GTA5 SHA256 mismatch: refuse to inspect as v12 verified build')
    if len(blob) < 32:
        raise ValueError('Mach-O header truncated')
    magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<IiiIIIII',blob)
    if magic != 0xfeedfacf or cputype != 0x100000c or filetype != 2 or ncmds > 2048:
        raise ValueError('Expected 64-bit ARM64 Mach-O executable')
    if sizeofcmds > 2_000_000 or 32+sizeofcmds > len(blob):
        raise ValueError('Malformed load commands')
    segs=[]; uuid=None; at=32
    for _ in range(ncmds):
        if at+8>32+sizeofcmds:raise ValueError('Truncated LC')
        cmd,cmdsize=struct.unpack_from('<II',blob,at)
        if cmdsize<8 or at+cmdsize>32+sizeofcmds:raise ValueError('Invalid LC size')
        if cmd==0x19:
            if cmdsize<72:raise ValueError('Invalid segment command')
            name,vmaddr,vmsize,fileoff,filesize=struct.unpack_from('<16sQQQQ',blob,at+8)
            if fileoff+filesize > len(blob):raise ValueError('Segment beyond EOF')
            segs.append({'name':name.rstrip(b'\0').decode('ascii','replace'),
                         'vmaddr':vmaddr,'vmsize':vmsize,'fileoff':fileoff,'filesize':filesize})
        if cmd==0x1b:
            if cmdsize<24:raise ValueError('Invalid LC_UUID')
            uuid=blob[at+8:at+24].hex()
        at+=cmdsize
    if uuid!=EXPECTED_UUID:raise ValueError('Unexpected UUID')
    sites={}
    for name,(vmaddr,note) in CANDIDATES.items():
        for seg in segs:
            if seg['vmaddr']<=vmaddr<seg['vmaddr']+seg['filesize']:
                off=seg['fileoff']+vmaddr-seg['vmaddr']
                sites[name]={'vmaddr':f'0x{vmaddr:016x}', 'file_offset':off,
                    'prologue_hex_32':blob[off:off+32].hex(),
                    'segment':seg['name'], 'assessment':note,
                    'hook_installed':False}
                break
        else:raise ValueError('Candidate address unmapped: '+name)
    return {'GTA5_SHA256':EXPECTED_GTA5_SHA,'GTA5_UUID':uuid,'arch':'arm64',
        'read_only':True,'patched':False,'ipa_playable':False,
        'candidate_sites':sites,
        'findings':'No safe native event-loop or authenticated RAGE packet dispatch has been verified as injectable; do not patch IPA from this report.'}

def main():
    a=argparse.ArgumentParser();a.add_argument('ipa');a.add_argument('--output',default=None);args=a.parse_args()
    with zipfile.ZipFile(args.ipa) as z:blob=z.read('Payload/GTAV.app/GTA5')
    report=inspect(blob)
    doc=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:Path(args.output).write_text(doc,encoding='utf-8')
    print(doc)
if __name__=='__main__':main()
