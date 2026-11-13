# v13 GTA Online RP — Source-only frame dispatcher review

Date: 2026-11-13T15:16:07Z. Parent: draft PR #14 (stacked onto PR #12). **No IPA/engine patch.**

## Why this addition
The existing `RP_V13_SessionGate` checks metadata and latches RELEASE_REQUIRED. It did not itself coordinate the order of frame processing and local controls release if the gameplay callback failed or no verified game-thread callback was present. The new `RP_V13_FrameDispatcher` is a small C11 dependency-injected layer, NOT a discovered RAGE hook.

## Contract and behavior
- `rp_v13_dispatcher_init()`: initialize once before enabling RP; both process/stop callbacks must be available for processing. Reinitializing a live dispatcher can discard a pending release and is forbidden by caller contract.
- `rp_v13_dispatcher_tick()`: accepts binary UUID evidence and an independently attested session snapshot. If required callbacks/evidence are missing, refuses gameplay; after previously being ready, it requires release.
- A switch of host, session, local ID or peer generation, monotonic clock rollback, bad UUID or offline/unauthenticated session requires local RP release via `stop_local`.
- If frame callback returns anything other than exactly 1, block further frames and require release; a failed stop callback remains pending.
- When `game_thread_verified != 1` or the session is missing, **never invoke local GTA controls**; keep release pending until a verified game-thread call arrives. This avoids a background-thread GTA native call, but it also means a missing callback can leave restraints pending; a safe independently verified dispatch/cleanup mechanism is still needed on the real device.
- A stop succeeds only if its callback returns exactly 1. The next trusted frame, not the same stopping frame, may re-arm. These flags and callback returns do NOT prove GTA authenticity.

## Reproducible tests (Linux)
```bash
gcc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
  police-rp/v13/{rp_v13_identity_gate.c,rp_v13_session_gate.c,rp_v13_frame_dispatcher.c,test_rp_v13_frame_dispatcher.c} \
  -o /tmp/rp_v13_dispatcher_gcc && /tmp/rp_v13_dispatcher_gcc
clang -std=c11 -O1 -g -fno-omit-frame-pointer -Wall -Wextra -Werror \
  -pedantic -fsanitize=address,undefined -fno-sanitize-recover=all \
  police-rp/v13/{rp_v13_identity_gate.c,rp_v13_session_gate.c,rp_v13_frame_dispatcher.c,test_rp_v13_frame_dispatcher.c} \
  -o /tmp/rp_v13_dispatcher_san && \
  ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 /tmp/rp_v13_dispatcher_san
```

Observed from both executions: `RP v13 frame dispatcher PASS: 59 assertions (host-only)`. GCC Debian 14.2.0, Clang 17.0.0; no sanitizer errors on executed paths.

SHA-256:
- `rp_v13_frame_dispatcher.h`: `1fa3ecc3af917cb83dfd27fc577b982b93dfe037b0b1f7fce0271c0c4600cdc2`; Git blob SHA-1 `52028e559e862b9db50f1b56389ed514f05c5596`.
- `rp_v13_frame_dispatcher.c`: `68da806bb72e4d370582a78d965a17c8b1d31ac32cadf6ae4b048ec3c66047d8`; Git blob SHA-1 `5c8abe0216a8b809b4105cb6fb8ce24025fc3adb`.
- `test_rp_v13_frame_dispatcher.c`: `47ea9c0a39fef7becf141a079c27b94ba0960263bb20ab29cd8954cdd8676eca`; Git blob SHA-1 `dab63575aa9b34db062da2a77a5c7953838807ab`.

All GitHub blobs were verified to match exact locally tested source via Git object SHA-1. Updated source-only CI workflow to compile both host/sanitizer and an *unsigned* iPhoneOS dylib exporting `_rp_v13_dispatcher_tick`; **that Apple build has not executed**.

## Engine integration still blocked
A future trusted v13 adapter must prove:
1. Dyld-verified `GTA5` and `libgtacompat` identifiers for the exact IPA; UUID alone is not a code-signing/ABI guarantee.
2. A verified GTA game-thread callback for every relevant gameplay frame (not a fabricated boolean or ScriptHook/Menu tick).
3. Authenticated host/session/local IDs and peer generation from game engine networking (not raw UDP).
4. Callback implementation: `process(ctx)` can call `prp_port_frame(...)` **only if the PRP core is separately reviewed and version-compatible**. `stop_local(ctx)` must prove `prp_port_stop(...)` actually released LOCAL controls; since `prp_port_stop` currently returns `void`, merely calling it is insufficient proof without independent state validation.
5. Two-device Online checks including disconnect, host migration, local cuff cleanup, performance and crash logs.

## CI blocker, status and rollback
PR #14 GitHub-hosted jobs previously failed with `runner_id=0`, `steps=[]` on both Linux/macOS and no usable job logs. No claim of successful GitHub CI nor Apple ARM64 code compilation; rerun only after runner access is understood.

Rollback: revert this isolated dispatcher change on PR #14, leave PR #12, PR #10, main and proprietary IPA untouched. No automatic merge or release.
