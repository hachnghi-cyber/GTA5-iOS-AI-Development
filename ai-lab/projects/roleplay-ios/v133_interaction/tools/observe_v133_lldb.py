"""One-shot external LLDB observer for a development-signed v13.3 device build."""

import json
import struct
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[2] / "baselines" / "phase9-v133-engine.json"
EXPECTED_UUID = "EB122C35-96F4-307F-91C3-A2255DD9C685"
MAX_FRAMES = 32
_active = None
_thread_labels = {}


def describe_stack(site, frames, thread_label):
    remote = "on_net_event" in frames and "connection_dispatch" in frames
    local = "send_buffer" in frames
    path = "undetermined"
    if remote and not local:
        path = "network_receive_stack"
    if local and "on_net_event" not in frames:
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
        result.AppendMessage(json.dumps(describe_stack(site, frames, label)))
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
