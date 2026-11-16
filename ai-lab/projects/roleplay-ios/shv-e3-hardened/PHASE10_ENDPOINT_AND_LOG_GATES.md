# Phase 10 — fail-closed E3 LAN endpoint and device-log validation

**Scope:** GTA V iOS v13.3 ScriptHook **diagnostic-only PING**, not native RAGE replication/Police RP. Exact v13.3 game IPA and executable remain unchanged. Parent source: Phase 9, PR #19.

## Verified fixes
1. Receiver precomputes configured peer IP and UDP port and discards unexpected endpoints *before HMAC decode, sequence commit, queue write or ACK*. No IP, player ID or secret is logged. This is network endpoint filtering, **not** native multiplayer identity authentication.
2. Regression constructs a correctly HMAC-signed RBP1 packet from a wrong local UDP port; expects no ACK, queue empty, then sends genuine seq 1 from configured peer and verifies native receipt. Regression avoids an unsynchronized read of worker-owned sequence.
3. E3 log gate now matches actual Phase9 text (\`queue receipt ONLY\`) and requires the same sequence across A transmit+ACK, B accepted+native called+native report queued+native report sent, and A verified the HMAC report.
4. Any fail-closed scheduler marker in the last RUN_BEGIN invalidates the evaluation even if earlier positive ticks exist. A host/forged text log remains **untrusted** without physical device provenance.

## Local exact-source checks
- Clang, then GCC strict C sanitizer/full Python/shared mock script/UDP tests **PASS**.
- 46/46 Python tests PASS, including 15 device-log evaluator regression cases.
- 12 repeated hostile-sender endpoint tests per compiler under ASan+UBSan: **24/24 PASS**.
- Original private IPA static preflight verified locally, no binary committed.
- CI run must be checked on the exact GitHub commit before reporting CI PASS.

## Not yet verified
No iPhoneOS SDK-linked and signed diagnostic dylib, no iPhone E0/E1/E3 runtime evidence, no RAGE-authenticated sender/session binding, no Remote Police Roleplay interaction. Earlier macOS build job was cancelled without compilation; do not infer compile failure or success.

### Real device gates
1. Link E0 using iPhoneOS SDK and development-sign matching app; require fresh loader + callback ticks.
2. E1 local HUD visual recording; logs alone prove only native API invocation attempt.
3. E3 two development-signed iPhones on controlled LAN with fresh random RBPProbe.cfg for each. Collect same-run A/B logs and B screen capture; classify with tools/evaluate_device_logs.py. Device origin and OS version must be independently checked.
4. PR #16: independently prove RAGE receive-context source authorization and session incarnation after disconnect/reconnect before enabling còng tay/áp giải/tù.

No automatic merge, no IPA publishing, no live multiplayer manipulation.
