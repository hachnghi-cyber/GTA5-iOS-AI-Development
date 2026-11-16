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
- PR #19 now has a successful real iPhoneOS SDK build: commit `1e910d4`,
  Actions `43969424836`. E0/E1/E3 metadata was independently verified in the
  downloaded artifact; `baselines/e3-iphoneos-build-1e910d4.json` records it.
  Source tests and linked dylibs do not establish ScriptHook/device gameplay.
- Risks: limited supported call chain, debugger pause, unverified authenticated
  session/membership lifetime; read failure or unexpected chain rejects sample.

Next highest-value action: verify native session context in the existing
read-only observer, then use a controlled Sandbox session with a cooperating
peer and run the command in
`V133_SCRIPTED_EVENT_OBSERVER_VI.md` under **Receive context**. Preserve the
sanitized JSON and the triggering action. A receive-source comparison is only
the next evidence gate; authentication/session/reconnect must be traced before
connecting PRP3 or testing remote cuff/release. Only one iPhone is known here.

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
