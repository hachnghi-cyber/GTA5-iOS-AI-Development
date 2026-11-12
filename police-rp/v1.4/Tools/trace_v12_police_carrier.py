#!/usr/bin/env python3
"""Verify read-only call chain from GTA v12, plus potential network carrier.

This tool does NOT install hooks, add a protocol to RAGE or alter an IPA.
A proof of CScriptedGameEvent usage does NOT prove the dispatch accepts PRP.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from inspect_v12_calls import EXPECTED_GTA5, EXPECTED_UUID, sections

BASE = 0x100000000
FUNCTIONS = {
    'CTheScripts::LaunchStartupScript': 0x100e30564,
    'MacportSandboxProgram': 0x100039d88,
    'MacportSandboxNative': 0x100039e34,
    'MacportOnlineUpdate': 0x1000e01a0,
    'MacportJobsUpdate': 0x1000ea024,
    'MacportWorkTaskFrame': 0x100112010,
    'MacportJobSend': 0x1000f5e34,
    'rage::scrThread::RegisterCommand': 0x101f952bc,
    'CScriptedGameEvent::CScriptedGameEvent': 0x10190ef20,
    'CStartNetworkPedArrestEvent::EventHandler': 0x101914e68,
    'CStartNetworkPedUncuffEvent::EventHandler': 0x101915030,
}

def instruction(blob, pc):
    addr, size, off = sections(blob)
    if pc < addr or pc + 4 > addr + size:
        raise ValueError('instruction lies outside __TEXT,__text')
    return struct.unpack_from('<I', blob, off + pc - addr)[0]

def branch_target(pc, word):
    if (word & 0x7c000000) != 0x14000000:
        return None
    displacement = word & 0x3ffffff
    if displacement & (1 << 25): displacement -= 1 << 26
    return pc + displacement * 4

def branch_kind(word):
    if (word & 0xfc000000) == 0x94000000: return 'BL'
    if (word & 0xfc000000) == 0x14000000: return 'B'
    return None

def require_branch(blob, address, target, kind):
    word = instruction(blob,address)
    if branch_target(address,word)!=target or branch_kind(word)!=kind:
        raise ValueError(f'expected {kind} to {hex(target)} at {hex(address)}')
    return {'at':hex(address), 'kind':kind, 'target':hex(target), 'opcode':hex(word)}

def verify(blob):
    if hashlib.sha256(blob).hexdigest() != EXPECTED_GTA5:
        raise ValueError('SHA mismatch: this tool only supports GTA5 v12 verified binary')
    _ = sections(blob)   # UUID, load commands and section bounds
    chain = [
        require_branch(blob,0x100e30584,FUNCTIONS['MacportSandboxProgram'],'BL'),
        require_branch(blob,0x100039dbc,FUNCTIONS['rage::scrThread::RegisterCommand'],'BL'),
        require_branch(blob,0x100039e34,FUNCTIONS['MacportOnlineUpdate'],'B'),
        require_branch(blob,0x1000e5188,FUNCTIONS['MacportJobsUpdate'],'BL'),
        require_branch(blob,0x1000e6de0,FUNCTIONS['MacportWorkTaskFrame'],'BL'),
        require_branch(blob,0x1000f5f3c,FUNCTIONS['CScriptedGameEvent::CScriptedGameEvent'],'BL'),
    ]
    # ARM64 guard: startup script only registers sandbox program when enabled.
    # cbz w0 at 0x100e30580 -> 0x100e3060c
    if instruction(blob,0x100e30580) != 0x34000460:
        raise ValueError('unexpected sandbox-mode guard')
    # ADRP x1 (PC relative page) + ADD x1,x1,#0xe34 == 0x100039e34
    if instruction(blob,0x100039da4)!=0x90000001 or instruction(blob,0x100039da8)!=0x9138d021:
        raise ValueError('unexpected RAGE command callback address construction')
    # mov w3,#0xf4; observed CScriptedGameEvent payload width in v12.
    if instruction(blob,0x1000f5f34)!=0x52801e83:
        raise ValueError('CScriptedGameEvent buffer size no longer 244')
    # mov + movk form 0x324a504d ("MPJ2" little endian), separate from PRP6.
    if instruction(blob,0x1000f5e90)!=0x528a09a8 or instruction(blob,0x1000f5e94)!=0x72a64948:
        raise ValueError('unexpected native job message magic')
    # Confirm both registered engine arrest/un-cuff event handler bodies lie in __text.
    events = {}
    for name in ['CStartNetworkPedArrestEvent::EventHandler','CStartNetworkPedUncuffEvent::EventHandler']:
        events[name] = {'vmaddr':hex(FUNCTIONS[name]),
                        'first_instruction':hex(instruction(blob,FUNCTIONS[name])),
                        'meaning':'event handler present; player applicability NOT verified'}
    return {
        'source':'GTAV-v12(1).ipa/Payload/GTAV.app/GTA5',
        'sha256':EXPECTED_GTA5, 'uuid':EXPECTED_UUID, 'read_only':True,
        'findings': {
          'sandbox_registration_guard':'CTheScripts::LaunchStartupScript checks MacportSandboxMode before registering native',
          'native_command_callback':'MacportSandboxProgram builds address MacportSandboxNative and registers it with rage::scrThread::RegisterCommand',
          'online_invocation':'MacportSandboxNative tail-branches (B) to MacportOnlineUpdate',
          'job_event_carrier':'MacportJobSend constructs CScriptedGameEvent with 244-byte MPJ2 payload',
          'not_proven':'PRP delivery, authenticated sender metadata, safe hook, UI, iOS dylib, actual game operation'
        },
        'arm64_verified_branches':chain,
        'native_command':'MacportSandboxNative',
        'job_message':{'magic':'MPJ2','bytes':244, 'constructor_call':hex(0x1000f5f3c),
            'warning':'Do not overwrite MPJ2 messages or reuse this type without receiver checks'},
        'existing_game_arrest_events':events,
        'ipa_changed':False,'hook_installed':False,'online_transport_connected':False,'playable':False
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('ipa',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    with zipfile.ZipFile(args.ipa) as z:
        blob=z.read('Payload/GTAV.app/GTA5')
    result=verify(blob)
    payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(payload,encoding='utf-8')
    else:print(payload)
if __name__=='__main__':main()
