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
- Latest USB attempt: device absent; no new iPhone context sample obtained.
- Risks: limited supported call chain, debugger pause, unverified authenticated
  session/membership lifetime; read failure or unexpected chain rejects sample.

Next highest-value action: reconnect the development-signed iPhone, enter a
controlled Sandbox session with a cooperating peer, and run the command in
`V133_SCRIPTED_EVENT_OBSERVER_VI.md` under **Receive context**. Preserve the
sanitized JSON and the triggering action. A receive-source comparison is only
the next evidence gate; authentication/session/reconnect must be traced before
connecting PRP3 or testing remote cuff/release. Only one iPhone is known here.

Do not repeat the IPA inventory, TLS diagnostic or Phase 5–9 source work.
Do not publish raw device logs, game payloads/assets, identities or keys.
