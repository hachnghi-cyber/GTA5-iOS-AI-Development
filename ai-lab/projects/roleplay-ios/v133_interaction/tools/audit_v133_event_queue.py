#!/usr/bin/env python3
"""Independent read-only instruction audit of GTA V v13.3 event-queue chain.

Only confirms exact-build static call/control flow; never authenticates player or
promotes a gameplay authority. Does not contain, patch or redistribute game code.
"""
import argparse
import hashlib
import json
import struct
import uuid
from pathlib import Path
from audit_v133_connection_chain import AuditError, SHA256, UUID, load, macho_uuid
from audit_v133_event_route import decode_bl_target
from inspect_v133_engine import parse_image

# Opcode and call checks imported from the supplied Phase 19 source archive.
PINS = {
    # Unpack constructs the netEvent. These are 32-bit connection metadata, not identity.
    0x101cd7064: 0x2907e67a,  # stp w26,w25,[x19,#0x3c]
    0x101cd7068: 0xb9005276,  # str w22,[x19,#0x50]
    0x101cd706c: 0xf9002673,  # str x19,[x19,#0x48]
    0x101cd7078: 0xf9000269,  # str x9,[x19] : vtable
    0x101cd70a4: 0x91244340,  # add x0,x26,#0x910: critical section
    0x101cd70b4: 0x9108e340,  # add x0,x26,#0x238: event queue
    0x101cd70b8: 0xaa1303e1,  # mov x1,x19: event pointer
    0x101cd70bc: 0x97ffc2c9,  # bl QueueEvent
    0x101cd70c0: 0x91244340,  # unlock critical section
    # QueueEvent(x0=queue,x1=event,x2=timestamp), linked-list insertion.
    0x101cc7be0: 0xa9bd57f6,
    0x101cc7bf0: 0xaa0203f5,
    0x101cc7bf4: 0xaa0103f4,
    0x101cc7bf8: 0xaa0003f3,
    0x101cc7bfc: 0x91016000,
    0x101cc7cb0: 0xb9000a95,
    0x101cc7cb4: 0xf9401668,
    0x101cc7cbc: 0xf9001674,
    0x101cc7cc0: 0xf9401688,
    0x101cc7cc4: 0xf9001114,
    0x101cc7cc8: 0xf9000e93,
    # NextEvent(x0=queue,x1=consumer) reads consumer->last and returns event.
    0x101a3801c: 0xa9bd57f6,
    0x101a3802c: 0xaa0103f4,
    0x101a38030: 0xaa0003f3,
    0x101a38058: 0xf9401260,
    0x101a3809c: 0xf9401409,
    0x101a380a0: 0xf90016a9,
    0x101a380ac: 0xa9007d1f,
    0x101a380b4: 0xb9404268,
    0x101a3810c: 0xf9400694,  # x20=consumer->last
    0x101a38110: 0x91016260,  # unlock queue lock
    0x101a38114: 0x94041e5b,
    0x101a38118: 0xaa1403e0,  # x0=x20, result event
    0x101a38128: 0xd65f03c0,
    # Update -> Dispatch -> NextEvent -> DispatchEvent -> Channel::DispatchEvent
    # confirms a concrete queue consumer and downstream channel dispatch path.
    0x101cd9004: 0xaa1303e0,  # Update manager arg
    0x101cd9008: 0x94000202,  # Update -> Dispatch
    0x101cd9858: 0xf9416000,  # manager+0x2c0 event queue reference
    0x101cd9860: 0x910b0375,  # manager+0x2c0 consumer
    0x101cd9868: 0xaa1503e1,  # consumer to NextEvent
    0x101cd986c: 0x97f579ec,  # Dispatch -> NextEvent
    0x101cd9874: 0xaa0003fc,  # returned netEvent retained x28
    0x101cd9ebc: 0xaa1c03e1,  # netEvent pointer passed to DispatchEvent
    0x101cd9ec0: 0x940007e4,  # Dispatch -> DispatchEvent
    0x101cd9f98: 0xaa1c03e1,
    0x101cd9f9c: 0x940007ad,  # alternate DispatchEvent branch
    0x101cd9fcc: 0xaa1503e1,
    0x101cd9fd0: 0x97f57813,  # next consumer event in loop
    0x101cdbe6c: 0xaa0103f3,  # DispatchEvent netEvent pointer
    0x101cdbe70: 0xaa0003f5,  # DispatchEvent manager pointer
    0x101cdc0ac: 0x910b6100,  # channel table indexed by type
    0x101cdc0b0: 0xaa1503e1,  # manager -> Channel
    0x101cdc0b4: 0xaa1303e2,  # netEvent -> Channel
    0x101cdc0b8: 0x97ffb6f8,  # Channel::DispatchEvent
    0x101cdc144: 0xaa1503e1,
    0x101cdc148: 0xaa1303e2,
    0x101cdc14c: 0x97ffb6d3,  # alternate channel dispatch
    0x101cc9d60: 0xaa1503e1,  # manager -> subscribed virtual callback
    0x101cc9d64: 0xaa1403e2,  # netEvent -> subscribed virtual callback
    0x101cc9d68: 0xd63f0120,  # indirect callback, target NOT proven
    # OnNetEvent receives netEvent pointer as its x2 argument, but sender unproven.
    0x102024914: 0xb9403c48,
    0x10202492c: 0xaa0203f4,
    0x102024930: 0xaa0003f3,
    0x10202496c: 0xb940192b,
    0x1020249b8: 0x940005d7,
    0x1020249e4: 0x978047ab,
    0x102024a10: 0x94000a93,
}
CALLS = {
    0x101cd70bc: 0x101cc7be0,  # Unpack -> QueueEvent
    0x101cd9008: 0x101cd9810,  # Update -> Dispatch
    0x101cd986c: 0x101a3801c,  # Dispatch -> NextEvent
    0x101cd9ec0: 0x101cdbe50,  # Dispatch -> DispatchEvent
    0x101cd9f9c: 0x101cdbe50,  # alternate DispatchEvent
    0x101cd9fd0: 0x101a3801c,  # next iteration of NextEvent
    0x101cdc0b8: 0x101cc9c98,  # DispatchEvent -> Channel::DispatchEvent
    0x101cdc14c: 0x101cc9c98,  # alternate channel dispatch
    0x101a38114: 0x101b3fa80,  # NextEvent -> unlock before returning
    0x1020249b8: 0x102026114,  # pre-header delegate
    0x1020249e4: 0x100036890,  # ReadHeader happens later
    0x102024a10: 0x10202745c,  # nonphysical handler
}

# Additional instructions used by the rolling Windows USB capture.
USB_PINS = {
    0x101cd9844: 0xaa0003fb,  # Dispatch keeps its manager in x27
    0x101cd9eb8: 0xaa1b03e0,  # first DispatchEvent receiver
    0x101cd9f94: 0xaa1b03e0,  # alternate DispatchEvent receiver
    0x101cd9fd4: 0xaa0003fc,  # preserve the next loop's returned event in x28
    0x101cd9fd8: 0xb5ffc620,  # loop on nonnull event
    0x101cdbe50: 0xd10183ff,  # DispatchEvent entry before the prologue
    0x1020249a8: 0xa9012be9,  # OnNetEvent still has x20 event and x9 sender
}

# Guard the complete functions used to interpret the dispatch stops and the
# audited span around the enqueue call before any breakpoint is armed.
USB_GUARDS = (
    ('unpack_enqueue', 0x101cd7064, 0x60),
    ('next_event', 0x101a3801c, 0x110),
    ('dispatch', 0x101cd9810, 0x934),
    ('dispatch_event', 0x101cdbe50, 0x320),
    ('channel_dispatch_event', 0x101cc9c98, 0x154),
    ('on_net_event', 0x102024914, 0x110),
)


def audit(data):
    sha = hashlib.sha256(data).hexdigest()
    if sha != SHA256:
        raise AuditError('exact executable SHA mismatch')
    if macho_uuid(data) != UUID:
        raise AuditError('exact Mach-O UUID mismatch')
    image_uuid, (text_va, text_size, text_offset), _ = parse_image(data)
    if image_uuid != str(uuid.UUID(hex=UUID)).upper():
        raise AuditError('text profile UUID mismatch')

    def code(pc, length):
        if pc % 4 or not text_va <= pc <= text_va + text_size - length:
            raise AuditError('instruction outside __TEXT,__text')
        offset = text_offset + pc - text_va
        return data[offset:offset + length]

    def word(pc):
        return struct.unpack('<I', code(pc, 4))[0]

    for pc, expected in (PINS | USB_PINS).items():
        if word(pc) != expected:
            raise AuditError(f'opcode mismatch at {pc:#x}')
    for pc, expected in CALLS.items():
        if decode_bl_target(pc, word(pc)) != expected:
            raise AuditError(f'call-target mismatch at {pc:#x}')

    return {
        'status':'PASS_STATIC_EXACT_BUILD',
        'executable_sha256':sha,
        'uuid':image_uuid,
        'verified_opcode_pins':len(PINS),
        'verified_direct_call_targets':len(CALLS),
        'verified_usb_additional_opcode_pins':len(USB_PINS),
        'unpack_uses_event_queue':True,
        'consumer_iteration_uses_next_event':True,
        'manager_update_calls_dispatch': True,
        'dispatch_routes_event_into_channel': True,
        'channel_subscriber_callback_is_indirect': True,
        'same_net_event_object_runtime_observed':False,
        'queue_consumer_on_net_event_binding_runtime_observed':False,
        'packet_cryptographic_sender_identity_verified':False,
        'rage_membership_generation_verified':False,
        'rp_actions_enabled':False,
        'usb_profile': {
            'enqueue_va': '0x101cd70bc',
            'dispatch_event_va': '0x101cdbe50',
            'dispatch_caller_returns': ['0x101cd9ec4', '0x101cd9fa0'],
            'on_net_event_pre_dispatch_va': '0x1020249a8',
            'code_guards': [
                {'function': name, 'va': hex(va), 'size': length,
                 'sha256': hashlib.sha256(code(va, length)).hexdigest()}
                for name, va, length in USB_GUARDS
            ],
        },
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('ipa_or_executable',type=Path)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    try:
        result=audit(load(a.ipa_or_executable)); rc=0
    except (OSError,KeyError,ValueError) as exc:
        result={'status':'FAIL_CLOSED','reason':str(exc)};rc=1
    s=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if a.out:a.out.write_text(s,encoding='utf-8')
    print(s,end='')
    return rc
if __name__=='__main__':raise SystemExit(main())
