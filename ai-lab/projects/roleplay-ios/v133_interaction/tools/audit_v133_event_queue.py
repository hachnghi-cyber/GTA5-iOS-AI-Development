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
from inspect_v133_engine import chained_rebase, parse_image

# Opcode and call checks imported from the supplied Phase 19 source archive.
PINS = {
    # Historical Phase 19 site: this constructs netEventConnectionError, NOT a
    # received frame. Keep its pins to make the rejected producer reproducible.
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
    0x101cd70bc: 0x101cc7be0,  # manager Unpack -> QueueEvent (connection error)
    0x101cd6b10: 0x101cc5020,  # manager Unpack -> connection Unpack
    0x101cc5768: 0x101cc67b0,  # connection Unpack -> QueueFrameEvent
    0x101cc682c: 0x101cc7d28,  # QueueFrameEvent -> AllocInFrame
    0x101cc7ea4: 0x101d42768,  # AllocInFrame -> InFrame constructor
    0x101cc684c: 0x101cc7be0,  # newly allocated frame -> queue
    0x101cc5cec: 0x101cc7be0,  # buffered frame -> queue
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

# Follow the actual received-frame producer and the vtable installed by its
# constructor; a matching QueueEvent call alone does not establish event type.
FRAME_PINS = {
    0x101cd7070: 0xb0005b69,  # rejected producer's connection-error vtable page
    0x101cd7074: 0x91234129,  # address point 0x1028448d0
    0x101cc5020: 0xd10543ff,  # connection Unpack allocates 0x150
    0x101cc5038: 0xa9147bfd,  # saves FP/LR
    0x101cc503c: 0x910503fd,  # FP = SP+0x140
    0x101cc5044: 0xaa0003f4,  # x20 = connection
    0x101cc5768: 0x94000412,
    0x101cc5cd8: 0xf9405e9a,  # buffered queue = connection+0xb8
    0x101cc5ce4: 0xaa1a03e0,
    0x101cc5ce8: 0xaa1c03e1,  # buffered event = x28
    0x101cc5cec: 0x940007bd,
    0x101cc67b0: 0xd101c3ff,  # QueueFrameEvent allocates 0x70
    0x101cc67c0: 0xa9067bfd,
    0x101cc67c4: 0x910183fd,  # FP = SP+0x60
    0x101cc67d0: 0xaa0003f4,  # x20 = connection
    0x101cc682c: 0x9400053f,
    0x101cc6834: 0xaa0003f5,  # x21 = newly allocated event
    0x101cc6838: 0xf9405e93,  # queue = connection+0xb8
    0x101cc6844: 0xaa1303e0,
    0x101cc6848: 0xaa1503e1,
    0x101cc684c: 0x940004e5,
    0x101cc7ea4: 0x9401ea31,
    0x101d427a8: 0xfd400828,  # constructor copies connection metadata +0x10
    0x101d4280c: 0xfc03c268,  # into event+0x3c
    0x101d428ec: 0xd0005808,  # InFrame derived vtable page
    0x101d428f0: 0x911ae108,  # address point 0x1028446b8
    0x101d428f4: 0xf9000268,
    0x101d42a24: 0xb000af48,  # frame GetId reads native AutoId storage
    0x101d42a28: 0xb9467500,  # global 0x10332b674
    0x101d42a2c: 0xd65f03c0,
    0x101d43098: 0x9000af48,  # distinct connection-error GetId storage
    0x101d4309c: 0xb945f500,
}

TRANSPORT_PINS = {
    0x101cd6230: 0x6db923e9,  # save registers and allocate 0x70
    0x101cd6240: 0xa90457f6,  # save caller x21 at Unpack FP-0x18
    0x101cd6248: 0xa9067bfd,  # save parent FP and LR
    0x101cd624c: 0x910183fd,  # set Unpack FP
    0x101cd6250: 0xd11503ff,  # Unpack FP is 0x5a0 above working SP
    0x101cd7690: 0xd10183ff,  # HandleReceivedPacket frame size
    0x101cd769c: 0xa9057bfd,  # save parent FP and LR
    0x101cd76a0: 0x910143fd,  # caller FP is 0x50 above its SP
    0x101cd76a8: 0xaa0003f5,  # caller keeps manager in x21
    0x101cd76e0: 0x39006fff,  # initialize the caller's local indicator
    0x101cd7700: 0x91006fe4,  # pass the indicator by reference
    0x101cd7794: 0x39406fe4,  # forward it to Unpack in w4
    0x101cd77a8: 0x97fffaa2,  # call Unpack with that indicator
}

# Guard the complete functions used to interpret the stopped frames. The
# Unpack range is split to stay within the observer's code read limits.
USB_GUARDS = (
    ('connection_unpack', 0x101cc5020, 0xe08),
    ('queue_frame_event', 0x101cc67b0, 0x190),
    ('alloc_in_frame', 0x101cc7d28, 0x19c),
    ('in_frame_constructor', 0x101d42768, 0x200),
    ('frame_get_id', 0x101d42a24, 0xc),
    ('unpack_head', 0x101cd6230, 0x1000),
    ('unpack_tail', 0x101cd7230, 0x130),
    ('handle_received_packet', 0x101cd7690, 0x160),
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

    for pc, expected in (PINS | USB_PINS | TRANSPORT_PINS | FRAME_PINS).items():
        if word(pc) != expected:
            raise AuditError(f'opcode mismatch at {pc:#x}')
    for pc, expected in CALLS.items():
        if decode_bl_target(pc, word(pc)) != expected:
            raise AuditError(f'call-target mismatch at {pc:#x}')
    unpack_call = 0x101cd77a8
    if decode_bl_target(unpack_call, word(unpack_call)) != 0x101cd6230:
        raise AuditError('Unpack caller target mismatch')
    for slot, target in ((0x1028446d0, 0x101d42a24), (0x102844738, 0x101d42a24),
                         (0x1028448e8, 0x101d43098)):
        if chained_rebase(data, slot) != target:
            raise AuditError('event vtable GetId target mismatch')

    return {
        'status':'PASS_STATIC_EXACT_BUILD',
        'executable_sha256':sha,
        'uuid':image_uuid,
        'verified_opcode_pins':len(PINS),
        'verified_direct_call_targets':len(CALLS),
        'verified_usb_additional_opcode_pins':len(USB_PINS),
        'verified_transport_frame_opcode_pins':len(TRANSPORT_PINS),
        'verified_received_frame_opcode_pins':len(FRAME_PINS),
        'verified_event_vtable_targets': 3,
        'rejected_old_enqueue': {
            'va': '0x101cd70bc', 'event_class': 'netEventConnectionError',
            'reason': 'constructor installs the connection-error vtable, not the frame-received vtable',
        },
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
            'version': 2,
            'enqueue_sites': {'immediate_frame': '0x101cc684c', 'buffered_frame': '0x101cc5cec'},
            'frame_vtable_va': '0x1028446b8',
            'frame_get_id_va': '0x101d42a24',
            'frame_type_id_va': '0x10332b674',
            'immediate_parent_returns': ['0x101cc576c', '0x101cd6b14'],
            'dispatch_event_va': '0x101cdbe50',
            'dispatch_caller_returns': ['0x101cd9ec4', '0x101cd9fa0'],
            'on_net_event_pre_dispatch_va': '0x1020249a8',
            'unpack_caller_return_va': hex(unpack_call + 4),
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
