#!/usr/bin/env python3
"""Read-only disassembly assertions for GTA5 v12 MPJ2 receiver.
Does not install hooks, link a dylib, or demonstrate a private RP transport.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from inspect_v12_calls import EXPECTED_GTA5, EXPECTED_UUID, sections

# Selected instructions of MacportJobsUpdate: static, exact-build evidence.
# Deliberately do not claim event-source authentication from MPJ2 header.
STEPS = {
  0x1000EA13C: (0x7102B81F, 'Checks RAGE event type = 0xAE'),
  0x1000EA154: (0x52801E82, 'Requests 244 bytes from the event object'),
  0x1000EA168: (0x528A09A9, 'Loads low half of MPJ2 magic'),
  0x1000EA16C: (0x72A64949, 'Loads upper half of MPJ2 magic'),
  0x1000EA170: (0x7A491100, 'Compares received magic against MPJ2'),
  0x1000EA174: (0x7A5F0B02, 'Checks claimed slot against 31'),
  0x1000EA1A0: (0x54FFFAE0, 'Skips event claiming own slot'),
  0x1000EA1BC: (0xF001A3A9, 'Addresses replay-state page'),
  0x1000EA1C0: (0x9129B129, 'Addresses replay-state + 0xA6C'),
  0x1000EA1C8: (0x6B09011F, 'Compares sequence against stored value'),
  0x1000EA1D8: (0xB8207928, 'Stores updated sequence'),
}

def inspect(blob: bytes) -> dict:
    got=hashlib.sha256(blob).hexdigest()
    if got!=EXPECTED_GTA5:
        raise ValueError('GTA5 SHA256 mismatch; refusing to inspect a different build')
    vm,sz,off=sections(blob)   # load commands, UUID, TEXT bounds
    found=[]
    for pc,(expected,description) in STEPS.items():
        if pc<vm or pc+4>vm+sz: raise ValueError(f'outside __text: {pc:#x}')
        word=struct.unpack_from('<I',blob,off+pc-vm)[0]
        if word!=expected: raise ValueError(f'{pc:#x}: expected {expected:#x}, got {word:#x}')
        found.append({'vmaddr':f'{pc:#x}', 'word':f'{word:#010x}', 'evidence':description})
    return {
      'gta_sha256':EXPECTED_GTA5, 'gta_uuid':EXPECTED_UUID,
      'function':'MacportJobsUpdate', 'receiver_event_type':174,
      'receiver_payload_bytes':244, 'required_magic':'MPJ2',
      'accepts_PRC1_without_changes':False,
      'trusted_sender_confirmed':False,
      'private_rp_event_registered':False,
      'event_receive_hook_installed':False,
      'ipa_modified':False,
      'verified_arm64_instructions':found,
      'interpretation':('Original jobs receiver only handles the existing MPJ2 protocol. '
           'The sender-slot number is read from the received message, so this '
           'observation does not establish the identity of its network origin. '
           'Do not reuse 0xAE/MPJ2 for Police RP without a dedicated authenticated receiver.'),
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument('ipa',type=Path)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.ipa) as z: blob=z.read('Payload/GTAV.app/GTA5')
    report=inspect(blob)
    data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.output: a.output.write_text(data,encoding='utf-8')
    else: print(data)
if __name__=='__main__': main()
