#!/usr/bin/env python3
"""Read-only v13.3 IPA preflight: identity and loader prerequisites.
Does not build, change, sign, run or inspect a device.
"""
import argparse
import hashlib
import json
import plistlib
import struct
import uuid
import zipfile
from pathlib import Path

EXPECTED_IPA='7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7'
EXPECTED_GAME='f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc'
EXPECTED_GAME_UUID='EB122C35-96F4-307F-91C3-A2255DD9C685'
EXPECTED_SHV_UUID='F768B7B5-AD75-39F4-83D3-8E49234325B5'
MH_MAGIC_64=0xFEEDFACF

def macho_info(data):
    if len(data)<32:raise ValueError('Mach-O too short')
    magic,cpu,sub,typ,count,cmdsize,flags,reserved=struct.unpack_from('<IiiIIIII',data)
    if magic!=MH_MAGIC_64 or cpu!=0x0100000c or count>512 or cmdsize>len(data)-32:
        raise ValueError('unsupported Mach-O or malformed commands')
    offset=32; result={'arch':'ARM64','uuid':None,'rpaths':[]}
    for _ in range(count):
        if offset+8>len(data):raise ValueError('truncated load command')
        cmd,size=struct.unpack_from('<II',data,offset)
        if size<8 or offset+size>len(data):raise ValueError('malformed load command')
        if cmd==0x1b:
            if size<24:raise ValueError('invalid LC_UUID')
            result['uuid']=str(uuid.UUID(bytes=data[offset+8:offset+24])).upper()
        elif cmd==0x8000001c: # LC_RPATH
            if size<12:raise ValueError('bad LC_RPATH')
            rel=struct.unpack_from('<I',data,offset+8)[0]
            if rel<12 or rel>=size:raise ValueError('bad rpath bounds')
            raw=data[offset+rel:offset+size].split(b'\x00',1)[0]
            result['rpaths'].append(raw.decode('utf-8','replace'))
        offset+=size
    return result

def audit(path):
    ipafile=Path(path)
    with ipafile.open('rb') as fp:
        ipa_digest=hashlib.file_digest(fp,'sha256').hexdigest()
    with zipfile.ZipFile(ipafile) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any(
            not n or n.startswith('/') or '\\' in n or '..' in Path(n).parts for n in names):
            raise ValueError('unsafe or duplicate ZIP member')
        if z.testzip() is not None:raise ValueError('failed ZIP CRC')
        def item(name):
            if name not in names:raise ValueError('missing '+name)
            return z.read(name)
        base='Payload/GTAV.app/'
        game=item(base+'GTA5')
        shv=item(base+'Frameworks/ScriptHookV.dylib')
        info=plistlib.loads(item(base+'Info.plist'))
        game_info=macho_info(game)
        shv_info=macho_info(shv)
        game_hash=hashlib.sha256(game).hexdigest()
        has_fw_rpath='@executable_path/Frameworks' in game_info['rpaths']
        shv_symbol_mention=b'scriptRegister' in shv and b'nativeCall' in shv
        result={
            'status':'STATIC_ONLY', 'ipa_sha256':ipa_digest,'ipa_matches_expected':ipa_digest==EXPECTED_IPA,
            'game_sha256':game_hash,'game_matches_expected':game_hash==EXPECTED_GAME,
            'game_uuid':game_info['uuid'],'game_uuid_match':game_info['uuid']==EXPECTED_GAME_UUID,
            'script_hook_uuid':shv_info['uuid'],'script_hook_uuid_match':shv_info['uuid']==EXPECTED_SHV_UUID,
            'game_rpath_has_frameworks':has_fw_rpath,
            'hook_symbol_names_present_in_bytes':shv_symbol_mention,
            'bundle_id':info.get('CFBundleIdentifier'),
            'local_network_usage_description_present':bool(info.get('NSLocalNetworkUsageDescription')),
            'plugin_already_exists':base+'Frameworks/RBPProbe.shv.dylib' in names,
            'entries':len(names),'zip_crc':'PASS'
        }
        result['accepted_for_known_probe_build'] = all([
            result['ipa_matches_expected'],result['game_matches_expected'],
            result['game_uuid_match'],result['script_hook_uuid_match'],has_fw_rpath,
            shv_symbol_mention,not result['plugin_already_exists']])
        return result

def main():
    p=argparse.ArgumentParser();p.add_argument('ipa');p.add_argument('--out',type=Path)
    a=p.parse_args(); result=audit(a.ipa)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if a.out:a.out.write_text(encoded)
    print(encoded,end='')
    if not result['accepted_for_known_probe_build']:raise SystemExit(2)
if __name__=='__main__':main()
