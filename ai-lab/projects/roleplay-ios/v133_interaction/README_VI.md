# Cập nhật Phase 9 (16/11/2026)

Đọc [báo cáo sender/carrier](../WINSTOM_V133_PHASE9_SENDER_CARRIER.md).
`rp_v133_carrier` bao gói PRP3 trong 56 byte, chừa payload +8..11 cho thao tác
native đã quan sát tĩnh và đưa frame vào mailbox hiện có. Test hai endpoint vẫn
là fixture host. Chưa có emitter/receiver gắn vào engine hoặc sender được xác
thực trên iPhone. Không gửi bare PRP3 qua CScriptedGameEvent.

# GTA V iOS v13.3 — Winstom-inspired interaction proof of concept

**SOURCE ONLY — NOT an IPA and NOT working Online Police RP.**

The user-provided Winstom 0.7.171 IPA was statically inspected. Its `rp.js` exposes `greet` and `documents` via the `avenor` WebKit-native message handler, with a UI-side 4m target filter. These are **not** proof of server-side distance validation, authenticated reception or working cuff/escort.

### Exact version gate
- Target GTA V v13.3 `GTA5` UUID: `EB122C35-96F4-307F-91C3-A2255DD9C685`
- Target `GTA5` SHA-256 from prior v13.3 baseline: `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`
- Winstom `GTA5` UUID: `048DCEFF-A696-3E7A-9086-2A9953C909CD`
- Winstom `GTA5` SHA-256: `df7427d0e19271b1b49f0132d8d6d3be0dd65a04b4c86991749b75ed9b15f0e4`

Executable fingerprints **differ**, and no binary-to-binary v13.3 code diff has been performed here. Do not reuse Winstom code addresses or memory layouts in v13.3.

### What this code implements
- `rp_v133_interact_gate.h/.c` — small C11 gateway for `greet` and `documents` only, with independent *caller-supplied* attestation callbacks.
- Checks build UUID/hash, game-thread context, user consent, verified session+epoch, local/target ID, 400cm trusted proximity, monotonic nonce per peer, and callback-reentrancy safety.
- Transport metadata **must** carry authenticated sender; no sender ID accepted from UI or packet.
- `RP_V133_ATTEMPTED` means callback invocation, **not** packet delivery. `RP_V133_RECEIVED` means an externally attested callback observed a matching event, **not** any gameplay effect.
- No Menyoo/ScriptHook in Online, no game native calls, no engine patch, no wire protocol or sockets.

### Reproduce host tests
```bash
cd ai-lab/projects/roleplay-ios/v133_interaction
cc -std=c11 -Wall -Wextra -Werror -Wpedantic -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -I include src/rp_v133_interact_gate.c tests/test_v133_interact_gate.c -o /tmp/rp_v133_gate
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 /tmp/rp_v133_gate
```

**Locally verified 2026-11-16:** GCC+ASan+UBSan PASS, Clang 17 host PASS, Clang 17 `--target=arm64-apple-ios17.0 -ffreestanding` produces a Mach-O ARM64 `.o` (compile only, no iPhoneOS SDK link). Test printed: `PASS, denied=19, emitted=6, observed=4`. GitHub CI on PR #16 had failed and did not return usable job logs; do **not** claim GitHub Actions passes.

### Missing before live Online
1. Actual verified v13.3 game-frame callback and attested runtime build check, not a stub returning true.
2. Session/player ID/epoch from engine-owned metadata and trusted coordinates; no UI-supplied distance or identity.
3. Authenticated private RP carrier separate from MPJ2/JobsUpdate; receive callback with trusted sender metadata, not a slot hint.
4. Two iPhones confirming one benign `greet` A→B event with matching session, sender and nonce. Test disconnect, host migration and crash.
5. Only after the above, design and validate cuff/escort; never modify remote ped without authority.

**Verified only:** code compiles, deterministic host tests pass, ARM64 object generated. No signed IPA, actual network transport, iPhone runtime, or Police RP gameplay was created or tested.


## Phase 5: diagnostic wire v1 (source-only)

The read-only Winstom reverse engineering indicates that the WebKit script
message proxy forwards WKScriptMessage to its target (LMXMessageProxy
implementation 0xe888); the AVPanel script handler checks `interact`
using `isEqual:` (0xb8784). Separately, the native state parser uses
`objectForKeyedSubscript:` to **read** `cuffed` and `follow` (0xbc2ec,
0xbc63c, 0xbc6b0). Reading these fields is NOT proof of working police arrests.

Clean-room wire format `RP_V133_WIRE_BYTES = 40`:
- bytes 0–3 `PRP3`; byte 4 version=1; byte 5 interaction kind (1 greet, 2 documents); bytes 6–7 reserved zero.
- little-endian 64-bit values at offsets 8 session, 16 receiver, 24 epoch, 32 nonce.
- **NO sender/player-origin and NO trusted flag in the wire body.** The engine-owned native transport must supply authenticated sender/session metadata independently.

Implementation `include/rp_v133_wire.h`, `src/rp_v133_wire.c`.
`rp_v133_wire_deliver` decodes exact-length frames then calls the existing
source-only gate. The two-peer fixture now transports serialized byte buffers.
It additionally tests malformed reserved bytes, unauthenticated metadata,
unknown peer and epoch mismatch.

Reproduce with `CC=gcc bash tools/run_host_tests.sh` and
`CC=clang bash tools/run_host_tests.sh`.
On 2026-11-16, both suites ran successfully with AddressSanitizer and
UndefinedBehaviorSanitizer on Linux. Clang freestanding ARM64 Apple object
compilation passed for the gate and codec; this is **NOT** iPhoneOS SDK
link/sign, not native GTA transport, and not proof of multiplayer gameplay.
GitHub Actions remains FAILED with job logs unavailable through the connector.


## Phase 6 — cross-device PRP3 device-trace audit

Winstom lmx analysis distinguishes HTTP/account transport (\`WRTransport\`, \`WRAccountSession\`) and independent voice transport (\`WRVoice.openHost:port:ticket:\`, \`encodeAndSend\`, \`receive\`) from Westrayn gameplay state. None of those Objective-C class names proves an authenticated GTA RAGE player sender.

New files:
- \`tools/verify_device_trace.py\`: parse two JSONL files representing A's \`tx\` and B's \`rx\`. Require the exact original v13.3 build UUID, compare full PRP3 bytes, session/epoch, sender and receiver metadata, strictly increasing nonce per peer, local monotonic clock and distinct device IDs. A/B monotonic timestamps are never compared.
- \`tests/test_verify_device_trace.py\`: synthetic cases for matching packet, wrong sender, wrong build, missing authentication claim, replay, changed nonce, kind, malformed length, out-of-order per-peer, clock rollback, etc.

Example command (with REAL captured logs after instrumenting a real engine-owned callback):
\`\`\`bash
python3 tools/verify_device_trace.py --tx device_A_TX.jsonl --rx device_B_RX.jsonl --out audit.json
\`\`\`

**Synthetic examples** require \`--allow-synthetic-demo\` when the log includes \`fixture_only=true\`. The offline tool cannot authenticate log origin, cannot validate a real engine hook, and always returns \`safe_to_enable_cuff_or_escort=false\`.

Locally on 2026-11-16, 13 Python unit tests passed for the packaged Phase 6 implementation; three Phase 5 C11 regressions also passed under GCC and Clang ASan/UBSan. GitHub Actions is still marked failure; source-only tests are not an iPhone or network gameplay proof.

See \`WINSTOM_V133_PHASE6_TRACE_VALIDATION.md\`. The R19/H5 captured diagnostics still showed \`sender_auth=0\` and \`gameplay=0\` in sampled event probes; no authenticated game transport is established.

## Phase 7 — bounded mailbox + multi-threaded regression

Files added:
- `include/rp_v133_mailbox.h` and `src/rp_v133_mailbox.c`: 64-slot fixed-size, allocation-free C11 mailbox that copies only the exact 40-byte PRP3 frame and externally supplied native transport metadata.
- `tests/test_v133_mailbox.c`: deterministic full-queue/drop, replay, eight events/frame, stale session and host migration, game-thread-only callbacks, reentrant revocation, clear.
- `tests/test_v133_mailbox_threads.c`: four concurrent synthetic producer pthreads, 500 packets per sender, with one game-thread consumer.
- `tools/run_host_tests.sh` now executes all **five** C11 test programs, under either GCC or Clang and ASan+UBSan.

For a fresh Linux checkout:
```bash
cd ai-lab/projects/roleplay-ios/v133_interaction
CC=gcc bash tools/run_host_tests.sh
CC=clang bash tools/run_host_tests.sh
```

Verified GitHub Actions on PR #16, exact source commit `9855965f4f6f86304c6b683b1a186dcf9a2343c9`:
- [Winstom RP CI SUCCESS](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43786760288).
- [AI Lab CI SUCCESS](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43786760234).
- [Source Watch SUCCESS](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43786760343).

The queue is intentionally **lossy** under load. Success counts vary by thread scheduling. GCC+ASan/UBSan and Clang verified memory-safety/undefined-behavior checks for the tested cases, **not** ThreadSanitizer or iOS runtime. `rp_v133_mailbox_pump()` must run on the genuine GTA game thread, and `rp_v133_mailbox_enqueue()` must be called only when the authentic native transport has already supplied a verified sender, session, epoch and channel authentication state. No such real callback has been established on v13.3 yet.

Technical design and blockers: `WINSTOM_V133_PHASE7_MAILBOX.md`.
