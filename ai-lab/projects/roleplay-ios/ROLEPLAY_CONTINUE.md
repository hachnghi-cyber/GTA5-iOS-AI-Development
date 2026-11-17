# Continue — native receive provenance

Latest packet-integrity checkpoint (parent `66961ca8ab49b82f42f9de592d6a6c1b987966f0`):
47 exact instructions and nine call targets establish the address-selected
key lookup, HMAC tag comparison and AES path. An intraprocedural CFG check
confirms the HMAC-success block dominates the AES call and success literal;
calls are modeled as returning, not emulated. Profile v3 hashes four additional
functions before inferring `address_key_hmac_candidate` from a normal immediate
frame. Zero remains `tunnel_or_bypass_unresolved`; buffered events stay unobserved.
133 host Python tests pass, including branch-bypass and guard-removal cases.
No key, packet payload or address is read/exported by the added observer logic.
Authentication, replay, key-to-game-player binding and lifetime remain unverified.
No new device capture or ARM64 build. Continue static key/peer metadata analysis
on the available host; do not wait for USB to investigate that independent edge.
Parent CI source `44124651444`, AI Lab `44124651572`, Source Watch `44124651628`
all passed. Profile v2 preflight cannot validate the new 17 function guards.

Latest endpoint/channel checkpoint (parent `35bbb15ba5a68130ab3f92d869915bab457c68e4`):
the immediate received-frame observer now checks the connection selected by
manager Unpack in the endpoint's bounded channel table, using caller registers
saved by connection Unpack. Seventeen additional exact opcode pins passed on
the original executable. All 126 Python tests passed, including null, unaligned,
overflow, missing/mismatched connection, read failure, channel bounds and ASLR.
No pointers/IDs are exported. A matching table entry is not authenticated
transport, session generation or continuous object lifetime. Buffered events
never borrow this current-packet evidence. No new iPhone capture or IPA build.
CI for parent `35bbb15`: source `44074391157`, AI Lab `44074391084`, Source Watch
`44074391197` succeeded. Check Actions for this checkpoint's own commit.

Current P0 correction (parent `5605e8e779ee7c3b3333e79d7d4c9d9e572d3ec7`):
the Phase 19 enqueue site was a `netEventConnectionError` producer. Exact
constructor/vtable analysis identifies received `InFrame` producers at
`0x101cc684c` (new frame) and `0x101cc5cec` (buffered frame). USB profile v2
now traces these sites and verifies the live event class, type, connection
and queue before proceeding. Buffered frames never inherit the current
packet's decrypt indicator. The original Phase 19 opcode checks remain
historical evidence only; their claimed received-frame interpretation was wrong.

Validation: 32 additional exact opcodes, three chained-vtable targets and
18 total direct-call targets passed on the original executable; 124 Python
tests passed locally. New tests reject the error event, wrong type/getter,
connection/queue mismatch and the obsolete profile, and cover buffered frames.
No device observation is claimed. The old preflight does not validate the new
13 code guards or the new enqueue sites. After USB returns, verify profile v2
and capture one controlled same-event trace before any adapter implementation.

Latest source correction (parent `b57346d83f1770afb5e81d1b34c59341d770580d`):
`rp_rage_scope_begin` now revokes the old scope before admitting a new one.
Previously a missing session ID or exhausted counter could leave old candidates
active after a failed renewal. The regression fails against the original C
source and passes after the fix on Windows x86_64 (Zig 0.13.0 clang, assertions
enabled). It covers stale rejection, same-ID recovery and counter saturation.
All 121 Python tests passed locally. Check the source and iPhoneOS Actions for
the commit containing this checkpoint; these are not device tests.

Current capture blocker: usbmux sees a Network connection but no USB device;
the user confirmed they cannot reconnect now. No live queue/scripted/session
sample was collected. Resume at `jobs_update --session-context` after USB is
available, then the existing same-event trace with a cooperating peer.
This source correction does not identify the engine lifecycle callback or
authenticate a RAGE sender. Do not enable gameplay from these candidate records.

Branch: `feature/winstom-rp-ipa-audit-20261116`; PR #16 remains unmerged.
Base checkpoint: `64e450ef7616fd35b32e0646241be0f8a08bc7d2`.
Implementation commit: `63cfdf33c34ffbe5c50163048830e050a618da82`.
Use `git log -1` for the subsequent documentation/CI checkpoint commit.

- New code: optional `--receive-context` in the existing Windows USB observer.
  Compares guarded call chain and source/destination references at scripted
  handler entry, distinguishes receive versus local SendBuffer, checks matching
  connection IDs. Never attests authentication or enables gameplay.
- Evidence: `ENGINE_INTEGRATION_MAP.md` and regenerated exact binary baseline.
- Local verification: exact user IPA inspector PASS; 54 Python tests PASS,
  including 21 USB protocol/context tests. These are synthetic source tests.
  [GitHub CI 43877645973](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43877645973)
  passed Python checks and all ten C binaries with GCC/Clang ASan/UBSan.
  AI Lab and Source Watch also passed at the implementation commit.
- No ARM64 source changed, so no repeated macOS build or IPA packaging needed.
- Real USB sample at 2026-11-16 20:48 UTC+07:00: `jobs_update` and its
  `MacportOnlineUpdate` caller matched; known empty stock job ID, kind/state 0.
  See `baselines/v133-stock-job-device-20261116.json`. Hardware breakpoint
  removal and detach were acknowledged. The later log shows backgrounding;
  scripted-event follow-up found no running GTA. This does not prove a crash.
- USB reconnected on 2026-11-17. After DDI mount, `script_event_handler`
  (with receive-context) and `on_net_event` each timed out after 30 seconds.
  A subsequent `jobs_update` sample hit the exact caller, kind/state 0.
  Hardware removal/detach succeeded; GTA was still running after both network
  observations. See `baselines/v133-usb-receive-attempts-20261117.json`.
  Timeout does not establish absence of peers or lack of transport support.
- `--session-context` sampled main=false, transition=true at the guarded
  `jobs_update` callback on iPhone at 05:31 UTC+07:00 on 2026-11-17.
  See `baselines/v133-usb-session-context-20261117.json`. The sample reports
  the two native progress bits at one stop. A session identity, its lifetime
  and the cause of the earlier receive timeouts remain unknown.
- PR #19 iPhoneOS build at `1e910d4` passed Actions `43969424836`.
  The later PR #19 checkpoint `844ea9c` records E3 PC-to-iPhone UDP ACK
  and the native call receipt, with RAGE player binding still pending.
- Imported the queue audit and correlator from the user-supplied Phase 19
  archive. All 21 original Python tests, 65 pins and 12 direct targets passed
  locally against the exact binary. The archive omitted `tests/test_guard_v2.c`.
  Use the repository's existing C11 guards for the RP source tests.
- Historical profile v1 (producer interpretation superseded above):
  Windows `--queue-context` checks seven dispatch instructions and 13
  transport-frame instructions, then verifies eight code ranges on attach.
  It reads the native Unpack caller indicator only when frame layout,
  return PC and manager all match on the enqueue stop.
  It attempts one queue-to-predispatch trace per attach.
  It checks the actual consumer queue, matching event addresses and thread,
  and ends the sample if the selected dispatch call returns first.
  See `baselines/phase19-v133-event-queue.json` and the observer runbook.
- Real iPhone debugger preflight at 11:03 UTC+07:00 on 2026-11-17 checked
  all eight code ranges and got acknowledgments for arming and removing two
  hardware breakpoints and detaching. GTA was running at the follow-up.
  See `baselines/v133-phase19-usb-preflight-20261117.json`. The next capture
  requires a controlled Sandbox session with a cooperating peer.
- Risks: limited supported call chain, debugger pause, unverified authenticated
  session/membership lifetime; read failure or unexpected chain rejects sample.

Next action: use the development-signed iPhone in a controlled Sandbox
session. Start with the queue-context experiment from the observer runbook,
then compare with the Phase 17 peer check and a scripted receive capture
with a cooperating peer. Preserve sanitized JSON and the triggering action.
Establish transport provenance for the same event, session lifetime and
thread affinity before wiring PRP3 to gameplay. Final cuff/release
validation requires two iPhones.

Do not repeat the IPA inventory, TLS diagnostic or Phase 5–9 source work.
Do not publish raw device logs, game payloads/assets, identities or keys.

Before repeating the device experiment after reconnect/reboot, verify the
DeveloperDiskImage. `pymobiledevice3 mounter auto-mount` succeeded before the
real jobs sample after three pre-attach qSupported connection aborts. See the
Windows preflight in `V133_SCRIPTED_EVENT_OBSERVER_VI.md`.

## Additional fail-closed diagnostic fix (2026-11-16)

The observer no longer sets `network_receive_stack_confirmed` at frame-chain
recognition before source/destination and connection ID comparisons. Instead
it records `network_receive_call_chain_observed` as the weaker first gate;
`network_receive_stack_confirmed` requires the complete same-event association.
Host regression fixtures cover wrong handler references, connection mismatch,
invalid event pointer, local SendBuffer and genuine synthetic receive; no
sender authentication/session ownership or device origin is asserted.
The USB device/controlled peer test remains required. No iPhoneOS build or
additional game hook is implied by this source-only correction.
