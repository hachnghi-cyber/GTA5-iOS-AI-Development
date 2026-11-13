# v13 Session Stop Callback — Host regression evidence

Date: 2026-11-13 (UTC). Work item: PR #14, stacked on PR #12. Pure C11 source, **no GTA IPA and no iPhone test**.

## Verified source change
- `rp_v13_session_gate_release_with_stop(gate, stop_local, ctx)` fails closed if gate is null, release is not pending, callback is absent or callback returns anything other than exactly `1`.
- An unsuccessful callback leaves the `RELEASE_REQUIRED` latch intact. A successful callback acknowledges release and clears old identity; RP cannot become READY until another independently verified update call.
- `stop_local` is a **synthetic C callback for testing**. Real engine integration must invoke `prp_port_stop()` and release LOCAL controls on the GTA game thread before returning 1; not implemented here.
- Previously exposed lower-level `acknowledge_released()` is retained for ABI continuity; integrations should prefer the callback-gated wrapper. No code-signing, RAGE hook, network traffic or gameplay alteration.

## Local reproducible commands (working container)
```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
 police-rp/v13/rp_v13_identity_gate.c \
 police-rp/v13/rp_v13_session_gate.c \
 police-rp/v13/test_rp_v13_session_gate.c -o out/test_release_gcc
./out/test_release_gcc

clang -std=c11 -O1 -g -fno-omit-frame-pointer -Wall -Wextra -Werror \
 -pedantic -fsanitize=address,undefined -fno-sanitize-recover=all \
 police-rp/v13/rp_v13_identity_gate.c \
 police-rp/v13/rp_v13_session_gate.c \
 police-rp/v13/test_rp_v13_session_gate.c -o out/test_release_san
ASAN_OPTIONS=detect_leaks=1 ./out/test_release_san
```

Observed stdout on both commands:
```text
RP v13 session gate PASS: 74 assertions, host-only; no device test
```

Local toolchains: GCC 14.2.0; Clang 17.0.0. These check synthetic transport/session evidence and fake release callback only. Both commands exited 0, and no sanitizer failure appeared on exercised paths.

## Exact source fingerprints
| File | SHA256 | Git blob SHA-1 |
|---|---|---|
| `rp_v13_session_gate.h` | `88585fed44895f98426b7c137fb778c8de8309c7f39c9c417ded3a5878b8a720` | `8bd2f8359308bcfb9cb9d0bcbb2c2b06c94b61a1` |
| `rp_v13_session_gate.c` | `eadd5dc89cf1042561030df92ea637331ecc67148292c49bd5793e11453d81e2` | `d08c15f5e73be254d84e2fe251917c39d04ad4bf` |
| `test_rp_v13_session_gate.c` | `036219397e64632b029e1d89a448ba6da93d5784ef0f7e6e3c6df88c541ae35d` | `9ebd09abe4f400e5525ee0e483730fb1dc8de0df` |

Uploaded Git blobs were checked to match exactly the local compiled files.

## GitHub-hosted Actions blocker — not a C compilation error
At head `1b82f11665dbd4441e58cdfc4de82cab55463794`, CI run [43446132796](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43446132796) reported failure for both Linux `host` and macOS `iphoneos`:
- Job metadata: `runner_id=0`, `runner_name=""`, `steps=[]`, wall duration about two seconds.
- Job logs previously returned HTTP 404 `BlobNotFound`; no code checkout or build steps were executed.
- Cause not confirmed. Potential account-level Actions quota/billing and runner restrictions should be verified in the repo owner's Settings; neither conclusion is proven from current metadata.

GitHub docs: https://docs.github.com/en/actions/how-tos/troubleshoot-workflows and https://docs.github.com/en/actions/concepts/billing-and-usage.

## Remaining blockers / next step
1. Review annotations for failed job using GitHub UI; inspect Actions spending/budgets and runner permission/status without exposing payment details to commits.
2. Rerun source-only CI after runner access is restored; verify Linux and macOS separately.
3. Instrument exact v13 IPA for trusted loader identity/game-frame/session/carrier evidence. Only then bind `stop_local` to real `prp_port_stop`, and perform two-device tests.
4. Do not auto-merge PR #14, publish IPA, infer FiveM compatibility or claim genuine online arrest.

Rollback: revert this feature commit on PR #14, leaving PR #12, main and IPA untouched.
