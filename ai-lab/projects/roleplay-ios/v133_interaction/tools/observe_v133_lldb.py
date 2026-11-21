"""One-shot external LLDB observer for a development-signed v13.3 device build."""

import json
import struct
import hmac
import hashlib
import secrets
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[2] / "baselines" / "phase9-v133-engine.json"
EXPECTED_UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
MAX_FRAMES = 32
_active = None
_thread_labels = {}
_conn_tag_uid = None
_conn_tag_secret = None


def ephemeral_connection_tag(process_uid, conn):
    """Per-debuggee-process opaque HMAC label. No IDs or secret in output.

    This correlates connection lifetimes, NOT individual packets,
    session generations, encryption status or police permissions.
    """
    global _conn_tag_uid, _conn_tag_secret
    if not isinstance(process_uid,int) or process_uid<=0 or (
        not isinstance(conn,int) or not 0<conn<0x80000000
    ):
        return None
    if process_uid != _conn_tag_uid or _conn_tag_secret is None:
        _conn_tag_secret = secrets.token_bytes(32)
        _conn_tag_uid = process_uid
    digest=hmac.new(_conn_tag_secret,b"RAGE-CXN:\\0"+struct.pack(">I",conn),
                    hashlib.sha256).hexdigest()
    return digest[:24] # truncated 96-bit HMAC; key lives in LLDB process only



def describe_stack(site, frames, thread_label):
    remote = any(x in frames for x in ("on_net_event", "on_net_event_pre_dispatch")) and "connection_dispatch" in frames
    local = "send_buffer" in frames
    path = "undetermined"
    if remote and not local:
        path = "network_receive_stack"
    if local and not any(x in frames for x in ("on_net_event", "on_net_event_pre_dispatch")):
        path = "local_send_stack"
    return {
        "schema": "v133-lldb-observation-v1",
        "site": site,
        "thread_label": thread_label,
        "frames": frames,
        "observed_path": path,
        "session_generation_verified": False,
        "authenticated_rp_sender_verified": False,
    }


def stopped_target(debugger):
    import lldb

    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    if not (target.GetTriple() or "").startswith("arm64") or process.GetState() != lldb.eStateStopped:
        raise ValueError("Select a stopped ARM64 device process.")
    if (target.GetModuleAtIndex(0).GetUUIDString() or "").upper() != EXPECTED_UUID:
        raise ValueError("Main executable UUID mismatch.")
    return target, process


def arm(debugger, command, result, _):
    import lldb

    global _active
    try:
        target, process = stopped_target(debugger)
        if _active is not None:
            raise ValueError("Capture the active site or run prp-disarm first.")
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        site = command.strip()
        if baseline["uuid"] != EXPECTED_UUID or site not in baseline["trace_sites"]:
            raise ValueError("Choose one site: " + ", ".join(baseline["trace_sites"]))
        if site in baseline.get("internal_sites", {}):
            va = int(baseline["internal_sites"][site], 16)
        else:
            va = int(baseline["symbols"][site]["va"], 16)
        module = target.GetModuleAtIndex(0)
        address = module.ResolveFileAddress(va).GetLoadAddress(target)
        if address == lldb.LLDB_INVALID_ADDRESS:
            raise ValueError("Site is not mapped in the running image.")
        error = lldb.SBError()
        expected = struct.pack("<I", int(baseline["trace_sites"][site], 16))
        if process.ReadMemory(address, len(expected), error) != expected or error.Fail():
            raise ValueError("Live instruction mismatch. No breakpoint installed.")

        prior = {target.GetBreakpointAtIndex(i).GetID() for i in range(target.GetNumBreakpoints())}
        report = lldb.SBCommandReturnObject()
        debugger.GetCommandInterpreter().HandleCommand(
            f"breakpoint set --hardware --address {address:#x}", report
        )
        created = [target.GetBreakpointAtIndex(i) for i in range(target.GetNumBreakpoints())
                   if target.GetBreakpointAtIndex(i).GetID() not in prior]
        for breakpoint in created:
            breakpoint.SetOneShot(True)
        if (not report.Succeeded() or len(created) != 1 or not created[0].IsHardware()
                or not created[0].IsOneShot() or created[0].GetNumResolvedLocations() != 1):
            for breakpoint in created:
                target.BreakpointDelete(breakpoint.GetID())
            raise ValueError("LLDB could not resolve a one-shot hardware breakpoint.")
        _active = process.GetUniqueID(), created[0].GetID(), site, address
        result.AppendMessage("Armed " + site + ". Continue manually, then run prp-capture at the stop.")
    except (AttributeError, OSError, ValueError) as exc:
        result.SetError(str(exc))



def scan_remote_connection(read_u32, read_u64, manager_ptr, event_ptr):
    """Read at exact-UUID OnNetEvent entry. Bounded; emits no identities."""
    report = {
        "schema": "v133-onnet-connection-scan-v1",
        "status": "invalid_entry",
        "players_scanned": 0,
        "single_connection_match": False,
        "session_membership_verified": False,
        "authenticated_rp_sender_verified": False,
        "session_generation_verified": False,
    }
    if not isinstance(manager_ptr, int) or not isinstance(event_ptr, int) or (
        manager_ptr <= 0 or event_ptr <= 0
    ):
        return report
    try:
        event_conn = read_u32(event_ptr + 0x3c)
        if event_conn & 0x80000000:
            report["status"] = "invalid_event_connection"
            return report
        node = read_u64(manager_ptr + 0x128)
        visited = set()
        matched = 0
        for _ in range(32):
            if not node:
                break
            if node in visited:
                report["status"] = "cyclic_player_list"
                return report
            visited.add(node)
            player_conn = read_u32(node + 0x18)
            next_node = read_u64(node + 0x38)
            report["players_scanned"] += 1
            if player_conn == event_conn:
                matched += 1
            node = next_node
        if node:
            report["status"] = "list_exceeds_32"
        elif matched > 1:
            report["status"] = "ambiguous_duplicate_connection"
        elif matched == 1:
            report["status"] = "connection_candidate_only"
            report["single_connection_match"] = True
        else:
            report["status"] = "no_matching_player"
    except (KeyError, ValueError, RuntimeError, TypeError, OverflowError):
        report["status"] = "read_failed"
    return report


def scan_pre_dispatch(read_u32, read_u64, manager, event, chosen, local):
    """Exact-UUID OnNetEvent+0x94 only. NO RAGE authentication authority."""
    r={"status":"invalid_entry","players_scanned":0,
       "selected_sender_in_player_list":False,
       "authenticated_rp_sender_verified":False,
       "session_membership_verified":False,"session_generation_verified":False}
    if not all(isinstance(v,int) and v>0 for v in
               (manager,event,chosen,local)):return r
    if chosen==local:
        r["status"]="sender_aliases_local"
        return r
    try:
        conn=read_u32(event+0x3c)
        if conn & 0x80000000 or conn!=read_u32(chosen+0x18):
            r["status"]="sender_connection_mismatch";return r
        node=read_u64(manager+0x128)
        seen=set();matches=0;chosen_matches=0
        for _ in range(32):
            if not node:break
            if node in seen:
                r["status"]="list_cycle";return r
            seen.add(node)
            node_conn=read_u32(node+0x18)
            nxt=read_u64(node+0x38)
            r["players_scanned"]+=1
            if node_conn==conn:
                matches+=1
                if node==chosen:chosen_matches+=1
            node=nxt
        if node:r["status"]="list_exceeds_32"
        elif matches!=1 or chosen_matches!=1:r["status"]="no_unique_selected_sender"
        else:
            r["status"]="connection_candidate_only"
            r["selected_sender_in_player_list"]=True
    except (KeyError,TypeError,ValueError,RuntimeError,OverflowError):
        r["status"]="read_failed"
    return r



def scan_selected_peer_identity(read_u64, selected_netplayer, expected_getter):
    """Never call game code. Verify exact CNetGamePlayer vtable layout."""
    r={"status":"invalid_entry","peer_id_present":False,
       "authenticated_rp_sender_verified":False,
       "session_membership_verified":False}
    if not all(isinstance(n,int) and n>0 for n in
               (selected_netplayer,expected_getter)):
        return r
    try:
        vtable=read_u64(selected_netplayer)
        if not vtable or read_u64(vtable+0x38)!=expected_getter:
            r["status"]="unexpected_gamer_info_vtable"
            return r
        player_info=read_u64(selected_netplayer+0xa0)
        if not player_info:
            r["status"]="missing_player_info"
            return r
        # CNetGamePlayer.GetGamerInfo=>CPlayerInfo+0x20,
        # rlPeerInfo.GetPeerId=>rlGamerInfo+0x1d0.
        peer_id=read_u64(player_info+0x20+0x1d0)
        if not peer_id or peer_id==0xffffffffffffffff:
            r["status"]="invalid_peer_id"
            return r
        r["status"]="netplayer_peer_id_candidate_only"
        r["peer_id_present"]=True
    except (KeyError,ValueError,RuntimeError,TypeError,OverflowError):
        r["status"]="read_failed"
    return r


def read_stopped_u(process, address, n):
    import lldb
    err = lldb.SBError()
    data = process.ReadMemory(address, n, err)
    if err.Fail() or not isinstance(data, (bytes, bytearray)) or len(data) != n:
        raise ValueError("bounded read failed")
    return int.from_bytes(data, "little", signed=False)


def capture(debugger, command, result, _):
    import lldb

    global _active
    try:
        target, process = stopped_target(debugger)
        if command.strip() or _active is None or _active[0] != process.GetUniqueID():
            raise ValueError("No site armed for this process.")
        uid, breakpoint_id, site, address = _active
        thread = process.GetSelectedThread()
        if (thread.GetStopReason() != lldb.eStopReasonBreakpoint
                or thread.GetFrameAtIndex(0).GetPC() != address
                or breakpoint_id not in [
                    thread.GetStopReasonDataAtIndex(i)
                    for i in range(0, thread.GetStopReasonDataCount(), 2)
                ]):
            raise ValueError("Selected thread did not hit the armed breakpoint.")
        symbols = json.loads(BASELINE.read_text(encoding="utf-8"))["symbols"]
        keys = {int(info["va"], 16): name for name, info in symbols.items()}
        frames = [site]
        for i in range(1, min(thread.GetNumFrames(), MAX_FRAMES)):
            frame = thread.GetFrameAtIndex(i)
            if (frame.GetModule().GetUUIDString() or "").upper() != EXPECTED_UUID:
                continue
            start = frame.GetSymbol().GetStartAddress().GetFileAddress()
            if start in keys:
                frames.append(keys[start])
        label_key = uid, thread.GetThreadID()
        label = _thread_labels.setdefault(label_key, f"T{len(_thread_labels) + 1}")
        report = describe_stack(site, frames, label)
        if site == "on_net_event":
            frame = thread.GetFrameAtIndex(0)
            mgr = frame.FindRegister("x0").GetValueAsUnsigned()
            evt = frame.FindRegister("x2").GetValueAsUnsigned()
            report["connection_scan"] = scan_remote_connection(
                lambda address: read_stopped_u(process, address, 4),
                lambda address: read_stopped_u(process, address, 8),
                mgr, evt
            )
        if site == "on_net_event_pre_dispatch":
            frame=thread.GetFrameAtIndex(0)
            report["pre_dispatch"]=scan_pre_dispatch(
                lambda a:read_stopped_u(process,a,4),
                lambda a:read_stopped_u(process,a,8),
                frame.FindRegister("x19").GetValueAsUnsigned(),
                frame.FindRegister("x20").GetValueAsUnsigned(),
                frame.FindRegister("x9").GetValueAsUnsigned(),
                frame.FindRegister("x10").GetValueAsUnsigned())
        if site == "on_net_event_pre_dispatch":
            if report["pre_dispatch"]["selected_sender_in_player_list"]:
                try:
                    event=thread.GetFrameAtIndex(0).FindRegister("x20").GetValueAsUnsigned()
                    conn=read_stopped_u(process,event+0x3c,4)
                    opaque=ephemeral_connection_tag(uid,conn)
                    if opaque:report["opaque_connection_tag"]=opaque
                except (ValueError,RuntimeError,OverflowError):
                    pass
        if site == "on_net_event_pre_dispatch":
            if report["pre_dispatch"]["selected_sender_in_player_list"]:
                pin=json.loads(BASELINE.read_text(encoding="utf-8"))["peer_info_static"]
                module=target.GetModuleAtIndex(0)
                try:
                    for address_key, opcode_key in (
                        ("getter_va","getter_instruction"),
                        ("getter_next_va","getter_next_instruction"),
                        ("peer_getter_va","peer_getter_instruction"),
                    ):
                        at=module.ResolveFileAddress(int(pin[address_key],16)).GetLoadAddress(target)
                        if at==lldb.LLDB_INVALID_ADDRESS:
                            raise ValueError("peer getter unmapped")
                        expected=struct.pack("<I",int(pin[opcode_key],16))
                        error=lldb.SBError()
                        if process.ReadMemory(at,4,error)!=expected or error.Fail():
                            raise ValueError("peer getter opcode mismatch")
                    getter_va=int(pin["getter_va"],16)
                    loaded_getter=module.ResolveFileAddress(getter_va).GetLoadAddress(target)
                    selected=thread.GetFrameAtIndex(0).FindRegister("x9").GetValueAsUnsigned()
                    report["peer_info_probe"]=scan_selected_peer_identity(
                        lambda addr:read_stopped_u(process,addr,8),
                        selected,loaded_getter)
                except (KeyError,ValueError,RuntimeError,OverflowError):
                    report["peer_info_probe"]={
                        "status":"unsupported_peer_getter_build",
                        "peer_id_present":False,
                        "authenticated_rp_sender_verified":False,
                        "session_membership_verified":False}
            else:
                report["peer_info_probe"]={
                    "status":"skipped_unverified_connection",
                    "peer_id_present":False,
                    "authenticated_rp_sender_verified":False,
                    "session_membership_verified":False}
        if site == "on_connection_peer_verify":
            # In this branch x19=CNetworkSession, x21=event,
            # x22=snSession from [x19+0x20], x24=selected netPlayer,
            # x1=peer ID returned by netPlayer::GetRlPeerId.
            frame=thread.GetFrameAtIndex(0)
            info=json.loads(BASELINE.read_text(encoding="utf-8"))["peer_info_static"]
            module=target.GetModuleAtIndex(0)
            try:
                for key,opcode in (("getter_va","getter_instruction"),
                                   ("getter_next_va","getter_next_instruction"),
                                   ("peer_getter_va","peer_getter_instruction")):
                    addr=module.ResolveFileAddress(int(info[key],16)).GetLoadAddress(target)
                    error=lldb.SBError()
                    expected=struct.pack("<I",int(info[opcode],16))
                    if addr==lldb.LLDB_INVALID_ADDRESS or (
                        process.ReadMemory(addr,4,error)!=expected or error.Fail()):
                        raise ValueError("gamer info getter opcode mismatch")
                from importlib.util import spec_from_file_location, module_from_spec
                script=Path(__file__).with_name("check_v133_peer_session_map.py")
                spec=spec_from_file_location("v133_peer_map",script)
                checker=module_from_spec(spec)
                spec.loader.exec_module(checker)
                event=frame.FindRegister("x21").GetValueAsUnsigned()
                conn=read_stopped_u(process,event+0x3c,4)
                getter=module.ResolveFileAddress(
                    int(info["getter_va"],16)).GetLoadAddress(target)
                report["same_event_peer_session"]=checker.check_peer_session_map(
                    lambda a:read_stopped_u(process,a,4),
                    lambda a:read_stopped_u(process,a,8),
                    frame.FindRegister("x24").GetValueAsUnsigned(),
                    frame.FindRegister("x22").GetValueAsUnsigned(),
                    conn,getter,
                    frame.FindRegister("x1").GetValueAsUnsigned())
            except (AttributeError,KeyError,ValueError,RuntimeError,
                    OverflowError,OSError,TypeError):
                report["same_event_peer_session"]={
                    "status":"read_failed_or_unknown_native_build",
                    "peer_map_consistent":False,
                    "authenticated_rage_sender_verified":False,
                    "session_membership_verified":False,
                    "session_generation_verified":False}
            if report["same_event_peer_session"]["peer_map_consistent"]:
                try:
                    event=frame.FindRegister("x21").GetValueAsUnsigned()
                    conn=read_stopped_u(process,event+0x3c,4)
                    opaque=ephemeral_connection_tag(uid,conn)
                    if opaque:report["opaque_connection_tag"]=opaque
                except (ValueError,RuntimeError,OverflowError):
                    pass
        result.AppendMessage(json.dumps(report))
        _active = None
    except (AttributeError, OSError, ValueError) as exc:
        result.SetError(str(exc))


def disarm(debugger, command, result, _):
    global _active
    try:
        target, process = stopped_target(debugger)
        if _active is not None and _active[0] == process.GetUniqueID():
            target.BreakpointDelete(_active[1])
        _active = None
        result.AppendMessage("Observer disarmed.")
    except (AttributeError, ValueError) as exc:
        result.SetError(str(exc))


def __lldb_init_module(debugger, _):
    for name, function in (("prp-arm", "arm"), ("prp-capture", "capture"),
                           ("prp-disarm", "disarm")):
        debugger.HandleCommand(f"command script add -f {__name__}.{function} {name}")
