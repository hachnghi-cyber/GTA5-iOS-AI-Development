#!/usr/bin/env python3
"""Exact v13.3 ARM64 OnNetEvent: event->peer numeric match and dispatch order.

READ ONLY. No RAGE game-code hook, no authenticated sender/session evidence.
Uses the pre-existing exact-version SHA/UUID/pin audit in the same folder.
"""
import argparse
import json
from pathlib import Path
import struct
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_v133_connection_chain as chain

BASE = 0x100000000
EVENT_PINS = {
    0x102024914:0xb9403c48, # event+0x3c numeric connection ID
    0x102024918:0x37f80848, # reject flagged id
    0x102024944:0x7100101f, # event virtual kind == 4
    0x102024948:0x54000661, # branch away if not type 4
    0x10202494c:0xf9402688, # event+0x48 payload metadata ptr
    0x102024950:0xb4000628, # reject null metadata
    0x10202495c:0x3963e269, # manager bit flags at +0x8f8
    0x102024960:0x360005a9, # manager active flag check
    0x102024964:0xf9409669, # manager peer linked list at +0x128
    0x102024968:0xb4000569, # reject empty list
    0x10202496c:0xb940192b, # peer+0x18 numeric connection ID
    0x102024970:0x6b0a017f, # compare peer ID/event ID
    0x102024974:0x54000080, # branch on equality
    0x102024978:0xf9401d29, # peer next +0x38
    0x10202497c:0xb5ffff89, # loop until match/list ends
    0x102024988:0xf947dd4a, # global state load
    0x102024990:0xb400042a, # global context guard
    0x102024994:0xb941010b, # received payload metadata
    0x102024998:0xf940850c, # received payload pointer
    0x10202499c:0x79422908, # received payload bitfield
    0x1020249b8:0x940005d7, # atDelegator1<ReceivedMessageData>::Dispatch
    0x1020249d8:0x977f9ff0, # datBitBuffer::SetReadOnlyBytes
    0x1020249e4:0x978047ab, # netMessage::ReadHeader
    0x1020249e8:0x34000160, # missing header exits
    0x1020249f0:0x977fa023, # GetNumBytesRead
    0x1020249f4:0x34000100, # no parsed bytes exits
    0x102024a04:0x6b09011f, # decoded message code check
    0x102024a08:0x54000061, # branch if decoded kind mismatch
    0x102024a10:0x94000a93, # HandleNonPhysicalUpdateMsg
}
BL_TARGETS = {
    0x1020249b8:0x102026114,
    0x1020249d8:0x10000c998,
    0x1020249e4:0x100036890,
    0x102024a10:0x10202745c,
}


def decode_bl_target(pc, opcode):
    if opcode >> 26 != 0b100101:
        raise chain.AuditError('not BL instruction at '+hex(pc))
    disp = opcode & ((1 << 26) - 1)
    if disp & (1 << 25):disp -= 1 << 26
    return pc + (disp << 2)


def verify_event_pins(read_word):
    for va, expected in EVENT_PINS.items():
        if read_word(va) != expected:
            raise chain.AuditError('OnNetEvent opcode mismatch at '+hex(va))
    for va, target in BL_TARGETS.items():
        if decode_bl_target(va, read_word(va)) != target:
            raise chain.AuditError('OnNetEvent BL target mismatch at '+hex(va))
    if not (0x1020249b8 < 0x1020249e4 < 0x102024a10):
        raise chain.AuditError("event dispatch stage ordering violated")


def audit(binary):
    baseline=chain.audit(binary) # exact original SHA256/UUID + 26 connection pins
    def read_word(va):
        offset=va-BASE
        if offset<0 or offset+4>len(binary):
            raise chain.AuditError('bad address '+hex(va))
        return struct.unpack_from('<I',binary,offset)[0]
    verify_event_pins(read_word)
    return {
        'status':'STATIC_EVENT_ROUTE_VERIFIED_NOT_RAGE_AUTHENTICATED',
        'baseline_sha256':baseline['sha256'],
        'baseline_uuid':baseline['macho_uuid'],
        'previous_connection_pins':baseline['pinned_instructions'],
        'on_net_event_new_instruction_pins':len(EVENT_PINS),
        'event_kind_compared_to_4':True,
        'peer_list_connection_id_full32_matched':True,
        'delegate_dispatch_va':'0x1020249b8',
        'header_parse_va':'0x1020249e4',
        'nonphysical_update_va':'0x102024a10',
        'delegate_dispatch_precedes_header_parse':True,
        'delegate_dispatch_is_proof_of_header_validation':False,
        'numeric_connection_id_is_authentication':False,
        'sender_cryptographic_identity_verified':False,
        'session_generation_runtime_verified':False,
        'one_device_runtime_provenance_verified':False,
        'roleplay_gameplay_enabled':False,
    }


def main():
    p=argparse.ArgumentParser(description='Read-only exact GTA v13.3 OnNetEvent static audit')
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    try:
        result=audit(chain.load(args.source));code=0
    except (chain.AuditError,OSError,KeyError,ValueError,zipfile.BadZipFile,struct.error) as exc:
        result={'status':'REJECTED','reason':str(exc)};code=1
    data=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.out:args.out.write_text(data,encoding='utf-8')
    print(data,end='')
    return code

if __name__=='__main__':raise SystemExit(main())
