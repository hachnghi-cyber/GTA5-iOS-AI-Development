"""Exact-build, read-only ARM64 sender/callback evidence. Never installs hooks.

Uses LC_SYMTAB and selected instruction assertions, not v12 address guesses.
Apple layout reference: apple-oss-distributions/xnu/EXTERNAL_HEADERS/mach-o/loader.h.
Only metadata/selected instruction evidence is emitted; no binary extraction.
"""
import argparse
import hashlib
import json
import struct
import uuid
import zipfile
from pathlib import Path

SHA256 = 'f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc'
UUID = 'EB122C35-96F4-307F-91C3-A2255DD9C685'
SYMBOLS = {
    'sandbox_program': '__Z21MacportSandboxProgramv',
    'sandbox_callback': '__ZL20MacportSandboxNativeRN4rage9scrThread4InfoE',
    'online_update': '__ZL19MacportOnlineUpdatev',
    'jobs_update': '__ZL17MacportJobsUpdateP4CPedi',
    'job_send': '__ZL14MacportJobSendR13MacportJobMsgjj',
    'register_command': '__ZN4rage9scrThread15RegisterCommandEmPFvRNS0_4InfoEE',
    'startup_script': '__ZN11CTheScripts19LaunchStartupScriptEv',
    'on_net_event': '__ZN4rage16netPlayerMgrBase10OnNetEventEPNS_20netConnectionManagerEPKNS_8netEventE',
    'dispatch': '__ZN4rage12atDelegator1IvRKNS_19ReceivedMessageDataEE8DispatchES3_',
    'send_buffer': '__ZN4rage16netPlayerMgrBase10SendBufferEPKNS_9netPlayerEPKvjjPtS3_',
    'on_message': '__ZN4rage11netEventMgr17OnMessageReceivedERKNS_19ReceivedMessageDataE',
    'packed_events': '__ZN4rage11netEventMgr21HandlePackedEventsMsgERKNS_19ReceivedMessageDataE',
    'process_events': '__ZN4rage11netEventMgr19ProcessPackedEventsERNS_12datBitBufferERKNS_9netPlayerES5_',
    'process_data': '__ZN4rage11netEventMgr16ProcessEventDataERKNS_9netPlayerES3_tjjtRNS_12datBitBufferE',
    'handle_event': '__ZN4rage11netEventMgr11HandleEventEPNS_12netGameEventERNS_12datBitBufferERKNS_9netPlayerES7_tjj',
    'script_event_handler': '__ZN18CScriptedGameEvent12EventHandlerERN4rage12datBitBufferERKNS0_9netPlayerES5_tjj',
    'script_decide': '__ZN18CScriptedGameEvent6DecideERKN4rage9netPlayerES3_',
    'script_ctor': '__ZN18CScriptedGameEventC1ER13CGameScriptIdPvjj',
    'group_event_ctor1': '__ZN24CEventNetworkScriptEventC1EPvjPKN4rage9netPlayerE',
    'group_event_ctor2': '__ZN24CEventNetworkScriptEventC2EPvjPKN4rage9netPlayerE',
    'player_valid': '__ZNK4rage9netPlayer7IsValidEv',
    'session_state': '__ZN15CNetworkSession15SetSessionStateENS_13eSessionStateEb',
    'handle_packet': '__ZN4rage20netConnectionManager20HandleReceivedPacketERKNS_10netAddressEPKvj',
    'p2p_decrypt': '__ZN4rage20netConnectionManager10P2pDecryptERKNS_10netAddressEPPhRjRb',
    'packet_unpack': '__ZN4rage20netConnectionManager6UnpackERKNS_10netAddressEPKvjb',
    'network_update': '__ZN8CNetwork6UpdateEb',
    'connection_update': '__ZN4rage20netConnectionManager6UpdateEj',
    'connection_dispatch': '__ZN4rage20netConnectionManager8DispatchEv',
    'scripts_process': '__ZN11CTheScripts7ProcessEv',
    'scripts_internal_process': '__ZN11CTheScripts15InternalProcessEv',
    'script_update_all': '__ZN4rage9scrThread9UpdateAllEi',
    'script_run': '__ZN4rage9scrThread3RunEi',
    'script_vm_run': '__ZN4rage9scrThread3RunEPNS_8scrValueEPS2_RKNS_10scrProgramEPNS0_10SerializedE',
    'current_gta_script': '__ZN11CTheScripts25GetCurrentGtaScriptThreadEv',
    'active_script': '__ZN4rage9scrThread15GetActiveThreadEv',
}


def parse_image(data):
    if len(data) < 32:
        raise ValueError('short Mach-O')
    magic, cpu, _, kind, count, size, _, _ = struct.unpack_from('<IiiIIIII', data)
    if (magic, cpu, kind) != (0xfeedfacf, 0x100000c, 2):
        raise ValueError('expected thin ARM64 executable')
    end = 32 + size
    if count > 4096 or end > len(data):
        raise ValueError('invalid load-command bounds')
    at = 32
    sections, symtab, image_uuid = [], None, None
    for _ in range(count):
        if at + 8 > end:
            raise ValueError('truncated load command')
        cmd, length = struct.unpack_from('<II', data, at)
        if length < 8 or length % 8 or at + length > end:
            raise ValueError('invalid load command size')
        if cmd == 0x1b:
            if length != 24 or image_uuid is not None:
                raise ValueError('invalid UUID command')
            image_uuid = str(uuid.UUID(bytes=data[at+8:at+24])).upper()
        elif cmd == 0x19:
            if length < 72:
                raise ValueError('short segment')
            nsects = struct.unpack_from('<I', data, at + 64)[0]
            if length != 72 + 80*nsects:
                raise ValueError('invalid section table')
            for i in range(nsects):
                p = at + 72 + 80*i
                name, seg, va, sz, off = struct.unpack_from('<16s16sQQI', data, p)
                sections.append((name.rstrip(b'\0'), seg.rstrip(b'\0'), va, sz, off))
        elif cmd == 2:
            if length != 24 or symtab is not None:
                raise ValueError('invalid symbol command')
            symtab = struct.unpack_from('<IIII', data, at + 8)
        at += length
    if at != end or not image_uuid or symtab is None:
        raise ValueError('incomplete Mach-O metadata')
    text = [s for s in sections if s[:2] == (b'__text', b'__TEXT')]
    if len(text) != 1:
        raise ValueError('expected one text section')
    _, _, va, sz, off = text[0]
    if off < end or off+sz > len(data) or sz % 4:
        raise ValueError('text section out of bounds')
    so, ns, st, ss = symtab
    if ns > 1_000_000 or so+16*ns > len(data) or st+ss > len(data):
        raise ValueError('symbol table out of bounds')
    wanted = set(SYMBOLS.values())
    found = {}
    for i in range(ns):
        ix, ty, se, _, value = struct.unpack_from('<IBBHQ', data, so+16*i)
        if ix >= ss:
            raise ValueError('symbol name out of bounds')
        stop = data.find(b'\0', st+ix, st+ss)
        if stop < 0:
            raise ValueError('unterminated symbol name')
        name = data[st+ix:stop].decode('utf-8', 'replace')
        if name not in wanted or ty & 0xe0 or ty & 0xe != 0xe:
            continue
        if not 0 < se <= len(sections) or not va <= value < va+sz or value % 4:
            raise ValueError('selected symbol outside code')
        if name in found:
            raise ValueError('ambiguous selected symbol')
        found[name] = value
    return image_uuid, (va, sz, off), found


def branch_target(pc, word):
    if word & 0x7c000000 != 0x14000000:
        return None
    imm = word & 0x3ffffff
    if imm & 0x2000000:
        imm -= 0x4000000
    return pc + imm*4


def inspect(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('SHA-256 mismatch: no v12/Winstom offset reuse')
    image_uuid, (va, size, off), found = parse_image(data)
    if image_uuid != UUID or set(found) != set(SYMBOLS.values()):
        raise ValueError('UUID or required symbols mismatch')
    sites = {k: found[n] for k, n in SYMBOLS.items()}
    def word(pc):
        if not va <= pc <= va+size-4 or pc % 4:
            raise ValueError('instruction outside code')
        return struct.unpack_from('<I', data, off+pc-va)[0]
    branches = []
    for src, delta, dst, kind in (
        ('startup_script', 0x20, 'sandbox_program', 'BL'),
        ('sandbox_program', 0x34, 'register_command', 'BL'),
        ('sandbox_callback', 0, 'online_update', 'B'),
        ('online_update', 0x4fe8, 'jobs_update', 'BL'),
        ('on_net_event', 0xa4, 'dispatch', 'BL'),
        ('send_buffer', 0x98, 'dispatch', 'BL'),
        ('on_message', 0x78, 'packed_events', 'BL'),
        ('packed_events', 0x134, 'process_events', 'BL'),
        ('process_events', 0xe0, 'process_data', 'BL'),
        ('script_event_handler', 0xec, 'handle_event', 'BL'),
        ('script_decide', 0x40, 'group_event_ctor1', 'BL'),
        ('group_event_ctor2', 0x64, 'player_valid', 'BL'),
        ('handle_packet', 0x7c, 'p2p_decrypt', 'BL'),
        ('handle_packet', 0x118, 'packet_unpack', 'BL'),
        ('network_update', 0x4a4, 'connection_update', 'BL'),
        ('network_update', 0x4f8, 'connection_update', 'BL'),
        ('connection_update', 0x2c0, 'connection_dispatch', 'BL'),
        ('connection_update', 0x404, 'connection_dispatch', 'BL'),
        ('scripts_process', 0xac, 'scripts_internal_process', 'BL'),
        ('scripts_internal_process', 0x294, 'script_update_all', 'BL'),
        ('script_run', 0x16c, 'script_vm_run', 'BL'),
        ('current_gta_script', 0, 'active_script', 'B'),
    ):
        pc = sites[src]+delta
        w = word(pc)
        actual_kind = 'BL' if w & 0x80000000 else 'B'
        if branch_target(pc, w) != sites[dst] or kind != actual_kind:
            raise ValueError('branch assertion failed: '+src+' -> '+dst)
        branches.append(dict(at=hex(pc), source=src, target=dst, kind=kind))
    # Small, independently disassembled ARM64 observations, not original source.
    checks = (
        ('startup_script', 0x1c, 0x34000460, 'sandbox-mode guard; registration is conditional'),
        ('sandbox_program', 0x1c, 0x90000001, 'ADRP callback page into x1'),
        ('sandbox_program', 0x20, 0x910e1021, 'ADD callback offset 0x384 into x1'),
        ('on_net_event', 0x58, 0xb940192b, 'player connection ID load at +0x18'),
        ('on_net_event', 0x5c, 0x6b0a017f, 'compare player connection ID with transport event'),
        ('on_net_event', 0x94, 0xa9012be9, 'ReceivedMessageData source/destination from engine pointers'),
        ('script_decide', 0x30, 0xaa0103e3, 'first netPlayer reference forwarded as constructor x3'),
        ('group_event_ctor2', 0x70, 0x394086a8, 'read engine player slot byte at +0x21'),
        ('group_event_ctor2', 0x7c, 0x39402029, 'read payload byte at +8'),
        ('group_event_ctor2', 0x8c, 0xb9000828, 'conditional 32-bit sender slot overwrite at payload +8'),
        ('jobs_update', 0x118, 0x7102b81f, 'script group event type 0xAE filter'),
        ('jobs_update', 0x130, 0x52801e82, 'retrieve 244-byte stock job message'),
        ('jobs_update', 0x13c, 0xb9414bf6, 'read claimed slot from stack payload +8'),
        ('handle_packet', 0x50, 0x39006fff, 'initialize decrypt out-byte to zero'),
        ('handle_packet', 0x104, 0x39406fe4, 'forward out-byte as fifth argument to Unpack'),
        ('p2p_decrypt', 0x284, 0x52800008, 'successful tunneling branch writes zero'),
        ('p2p_decrypt', 0x288, 0x390002c8, 'write out-byte separately from return value'),
        ('packet_unpack', 0x24, 0xaa0403f6, 'preserve fifth argument for Unpack checks'),
        ('packet_unpack', 0x320, 0x340009f6, 'one Unpack branch tests the boolean argument'),
        ('packet_unpack', 0x3b4, 0x340067d6, 'second Unpack branch tests the boolean argument'),
        ('script_run', 0xd0, 0xf9000014, 'publish active script before VM run'),
        ('script_run', 0x174, 0xf90002b9, 'restore previous active script after VM run'),
        ('active_script', 0x18, 0xf9400000, 'read active script pointer through storage accessor'),
        ('session_state', 0x3c, 0x6b08003f, 'compare requested state with current state'),
        ('session_state', 0xd8, 0xb9058693, 'conditionally write state enum, not a session generation'),
    )
    observations = []
    for src, delta, expected, note in checks:
        pc = sites[src]+delta
        if word(pc) != expected:
            raise ValueError(f'instruction assertion failed at {pc:#x}: {word(pc):#x}')
        observations.append(dict(at=hex(pc), function=src, word=hex(expected), observation=note))
    return dict(status='STATIC_VERIFIED', executable_sha256=SHA256, uuid=UUID,
                symbols={k: dict(name=SYMBOLS[k], va=hex(v)) for k,v in sites.items()},
                branches=branches, observations=observations,
                engine_owned_sender_path_static=True, cryptographic_authentication_verified=False,
                runtime_thread_verified=False, hook_installed=False,
                transport_connected=False, two_device_verified=False,
                warning='Sender pointer provenance is static evidence only. Local SendBuffer also dispatches; exclude loopback. Native constructor can overwrite PRP3 session_id at offset 8. Do not send bare PRP3 as CScriptedGameEvent payload.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('ipa', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    with zipfile.ZipFile(args.ipa) as archive:
        name = 'Payload/GTAV.app/GTA5'
        matches = [i for i in archive.infolist() if i.filename == name]
        if len(matches) != 1 or matches[0].file_size > 128*1024*1024:
            raise ValueError('missing/duplicate/oversized executable')
        report = inspect(archive.read(matches[0]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Exact v13.3 static assertions PASS; no runtime authentication established')


if __name__ == '__main__':
    main()
