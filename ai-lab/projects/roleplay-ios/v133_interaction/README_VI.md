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
