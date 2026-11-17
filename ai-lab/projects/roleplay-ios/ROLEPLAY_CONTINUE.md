# Continue — native receive provenance

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
- Windows `--queue-context` checks seven additional instructions and hashes
  six code ranges, then attempts one queue-to-predispatch trace per attach.
  It checks the actual consumer queue, matching event addresses and thread,
  and ends the sample if the selected dispatch call returns first.
  See `baselines/phase19-v133-event-queue.json` and the observer runbook.
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
