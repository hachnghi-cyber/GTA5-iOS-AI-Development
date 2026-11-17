# Exact v13.3 receive integration map

Scope: static disassembly of SHA `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`,
UUID `EB122C35-96F4-307F-91C3-A2255DD9C685`. No Winstom/PC offsets reused.
The machine-readable assertions are in `baselines/phase9-v133-engine.json`.

The Phase 19 producer selection was corrected after checking constructor
vtables, including their on-disk chained rebases. `0x101cd70bc` queues a
`netEventConnectionError`; it is not the received-frame producer. Passing its
opcode audit did not justify expecting that object at scripted receive.

Actual frame paths established on the exact binary:

| Queue call site | Producer | Object |
| --- | --- | --- |
| `0x101cc684c` | `netConnection::QueueFrameEvent -> AllocInFrame` | New `InFrame`, deriving from `netEventFrameReceived` |
| `0x101cc5cec` | `netConnection::Unpack`, after removing a buffered frame | Previously allocated `InFrame` |

The constructor copies connection metadata from connection+0x10 into
event+0x3c. Its final vtable at `0x1028446b8` resolves GetId to
`netEventFrameReceived::GetId`; the rejected error vtable resolves a different
method. USB profile v2 checks the live vtable, GetId target, expected type 4,
connection ID and owning queue before tracing the same event to Dispatch.
For a buffered frame it deliberately leaves the packet decrypt indicator
unobserved: the current packet cannot attest the origin of previously queued
bytes. The new profile has no device capture yet and does not authenticate peers.

The immediate-frame stop also exposes the endpoint/channel selection made by
manager `Unpack`. At `0x101cd6874`, x22 is loaded from `[x23 + x25*8]`, after
the channel is checked against 16; x22 is passed to connection `Unpack` at
`0x101cd6b10`. That callee saves the endpoint x23 at FP-0x28 and channel x25
at FP-0x38 before reusing the registers. Seventeen additional exact opcode
checks establish these locations. The existing full-function guards cover them.
The USB reader now compares this same-stop table entry with the connection
retained by the enqueue caller. It emits only `endpoint_connection_observed`,
never endpoint/connection values or the packet address. Invalid pointers,
out-of-range channels, empty/mismatched entries or read failures leave that
flag false and the packet indicator unobserved. This links another native
lookup edge; it does not establish the endpoint's cryptographic identity,
continuous object lifetime or session membership. Buffered frames remain excluded.

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

The exact `netP2pCrypt::Decrypt` routine at `0x101cdfee4` calls
`GenerateHmac`, compares an eight-byte received tag with the computed prefix,
and rejects mismatch before AES-CBC. Its HMAC-success block `0x101ce0090`
dominates the AES call `0x101ce0224` and success literal `0x101ce02cc` in the
conservative intraprocedural CFG. Forty-seven pins and nine call-target checks
cover the lookup, wrapper and crypto path; this is static evidence only.
The normal P2pDecrypt branch selects a key via `netKeyExchange::GetP2pKey`
using transport-address metadata, and sets its output byte to one only after
that routine succeeds. The tunnel branch sets zero; the outer bypass leaves
zero. Profile v3 therefore adds four full-function guards and labels only a
guarded immediate frame's set byte as `address_key_hmac_candidate`. It leaves
zero unresolved, and never reads a key. This does not identify the owner of
the key, prove the key exchange authentic, establish freshness, or bind it to
the game session/player. The imported crypto primitive implementations are
not emulated by the CFG check. Native lookup identity and lifetime remain P0.

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

## Receive observability gate: phase 9 hardening (2026-11-16)

The USB observer now emits **two different statuses** for a stopped scripted
event, both strictly read-only:
- `network_receive_call_chain_observed=true`: exact SHA256-guarded stack
  frames terminate in `OnNetEvent` receive origin. Sender/source references
  or connection identity **may still be invalid**.
- `network_receive_stack_confirmed=true` (and
  `engine_source_association_observed=true`): in addition to the receive
  frame chain, same-stop message source/destination pointers equal handler
  registers and a nonnegative event connection ID equals source connection
  ID. **This is only engine-source association, not cryptographic
  authentication, session membership lifetime or permission for Roleplay.**

A sample with `handler_reference_mismatch`, `connection_mismatch` or
`invalid_event_pointer` must never set `network_receive_stack_confirmed`.
The first field may still be true when only its own call-chain predicate was
proven. `thread_label=T1` is anonymous and valid for one capture only,
not stable across attempts; `game_thread_affinity_verified` always remains
false. No actual iPhone receive-context sample has been captured after this
change. Older baseline reports are not retrospectively upgraded.
