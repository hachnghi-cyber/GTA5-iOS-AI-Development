# Exact v13.3 receive integration map

Scope: static disassembly of SHA `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`,
UUID `EB122C35-96F4-307F-91C3-A2255DD9C685`. No Winstom/PC offsets reused.
The machine-readable assertions are in `baselines/phase9-v133-engine.json`.

```text
OnNetEvent: netEvent connection ID == engine-list player connection ID
  -> stack ReceivedMessageData {source, destination}
  -> Dispatch -> OnMessageReceived -> HandlePackedEventsMsg
  -> ProcessPackedEvents -> ProcessEventData (tail dispatch)
  -> CScriptedGameEvent::EventHandler -> HandleEvent -> Decide
  -> CEventNetworkScriptEvent (may overwrite payload bytes 8..11)
  -> stock jobs_update consumes script group events

SendBuffer local branch -> same Dispatch and scripted handler chain
```

## ABI and lifetime evidence

At scripted handler **entry, before its prologue**, x1 is source `netPlayer&`,
x2 is destination `netPlayer&`. Its LR can still point into `ProcessPackedEvents`
because `ProcessEventData` is a frameless tail dispatcher. The USB observer
requires the following exact return chain; it never scans arbitrary stack data:

| Caller frame | Unslid return PC |
| --- | --- |
| ProcessPackedEvents | `0x10200c23c` |
| HandlePackedEventsMsg | `0x10200bf44` |
| OnMessageReceived | `0x10200a808` |
| Dispatch member callback | `0x102026194` |
| Receive origin OR local origin | `0x1020249bc` OR `0x101ffeed0` |

For the receive origin, the message is at origin FP−0x60; source/destination
are at message+0x10/+0x18. Dispatch's saved caller x20 at FP−0x10 holds the
outer netEvent pointer. The observer compares the message references with
handler registers, then compares event+0x3c and source+0x18 connection IDs.
For local SendBuffer the message is at FP−0x68 and no receive event is read.
All these are exact-build observations, **not** portable C++ structure types.

The message and scripted event are stack objects, so retaining their pointers
after the callback would be invalid. The observer reads while the process is
stopped and discards pointers before detach; it emits only comparisons/labels.
Eight entire function bodies are hashed against the private binary before the
hardware breakpoint is installed. FP links must be aligned, increasing and
within 64 KiB of stopped SP. Unknown frames, PAC-tagged return addresses or
read errors fail the sample. No PAC bits are stripped.

[Apple ARM64 ABI](https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms)
provides the frame-chain reference, including omitted leaf/tail frames. The
actual offsets and calls above come from local disassembly, not Apple or FiveM.

## What still blocks the runtime adapter

Connection equality and a receive stack do not prove cryptographic sender
authentication, membership lifetime, session generation or game-thread affinity.
The decrypt output boolean is already known to be zero on a successful tunnel
path; setting authenticated=true from it, a player slot or a pointer is invalid.
`SetSessionState` stores an enum, not an incarnation counter. `ClearSession`
and migration entry points are candidates, without a verified lifecycle adapter.
The one-iPhone jobs callback sample cannot establish that scripted receive runs
on the same OS thread. No native gameplay call is enabled by this observer.

## Transport choice for this goal

| Route | Current evidence | Complexity / risk | Infrastructure and next gate |
| --- | --- | --- | --- |
| A: native events (priority) | Real binary receive path; 56-byte carrier host tests | Highest unresolved issue: authenticated provenance and custom-event compatibility | Existing multiplayer; needs real receive and two-client carrier test |
| B: session-bound custom transport (fallback only) | iPhone↔Windows mTLS diagnostic | Verified TLS, unverified game identity binding, peer discovery and Internet NAT | Would need a peer discovery/reachability design; no separate backend assumed |
| C: replication extension (deferred) | No verified extension API | Unknown ownership/layout and high regression risk | No implementation selected |

Work on A first. B's existing diagnostic is evidence to preserve, not the
requested user-operated RP server. Do not add another transport or gameplay
prototype before this receive experiment and its identity/lifecycle follow-up.
