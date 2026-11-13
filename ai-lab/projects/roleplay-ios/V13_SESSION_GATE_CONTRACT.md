# RP v13 — Session lifecycle metadata gate (source only)

## Scope
This stacked change targets feature/rp-v13-identity-baseline-20261113 (PR #12), not main or the unmerged v12/P0 integration PR #10. The source-only v13 baseline was recorded for GTAV-v13(4).ipa; no IPA or proprietary assets are committed here.

Files: police-rp/v13/rp_v13_session_gate.h, .c, test_rp_v13_session_gate.c. The module depends only on the existing rp_v13_identity_gate and C11. It does not search for GTA5 offsets or install hooks.

## Decision contract
- BLOCKED: missing/malformed evidence, absent game-thread/session/carrier attestation, offline session or zero peer identity/generation. No RP processing.
- READY: exact v13 GTA5 and libgtacompat UUIDs match loader-verified evidence, and an engine-sourced session/host/local snapshot is complete. This is an ADAPTER CONTRACT ONLY; it never automatically opts a player in or authorizes police actions.
- RELEASE_REQUIRED: after a previously READY state, any attestation loss, host/local/session/peer-generation change or monotonic clock rollback. The gate will not re-arm while release is pending even if valid metadata returns.
- After a real game-thread prp_port_stop (including releasing local restraints), the integrator may call rp_v13_session_gate_acknowledge_released. A subsequent trusted frame can then re-arm. A bare acknowledgement without actually stopping is a caller contract violation.

No status is a security proof by itself: user-space flags can be forged unless an independent trusted game/transport adapter supplies them. The v13 IPA export names alone do not prove such an adapter exists. Never pass raw UDP payload fields or player labels as trusted identities.

## Reproduction (Linux host; exact sources)
gcc -std=c11 -O2 -Wall -Wextra -Werror -pedantic police-rp/v13/rp_v13_identity_gate.c police-rp/v13/rp_v13_session_gate.c police-rp/v13/test_rp_v13_session_gate.c -o /tmp/test_session_gcc
/tmp/test_session_gcc
clang -std=c11 -O1 -g -fno-omit-frame-pointer -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-sanitize-recover=all police-rp/v13/rp_v13_identity_gate.c police-rp/v13/rp_v13_session_gate.c police-rp/v13/test_rp_v13_session_gate.c -o /tmp/test_session_san
ASAN_OPTIONS=detect_leaks=1 /tmp/test_session_san

Observed in working container on 2026-11-13: GCC 48/48 assertions PASS; Clang ASan+UBSan 48/48 assertions PASS (both print PASS: 48 assertions). The three Git blob SHA-1 identifiers were cross-checked against local git hash-object before commit.

## CI and limitations
Updated .github/workflows/gta-rp-v13-identity.yml to run both regressions, and to compile/export the session gate symbol from an unsigned ARM64 source-only dylib on a macOS runner.

At time of authoring, most recent PR #12 workflows at commit 5e3cafea reported failure but returned no steps and no downloadable logs (BlobNotFound); earlier v13 workflows on 364283a7 succeeded. Do not attribute latest failures to specific source errors without logs. This change requires fresh CI results and reviewer evaluation.

NOT VERIFIED: IPA build/injection, iPhone/iPad test, dynamic dyld image identity, RAGE game-frame callback, trusted sender ID, encrypted/authorized carrier, cross-phone arrest, persistence, signing and gameplay. No gameplay release/merge is authorized.

## Next experiment / rollback
1. Collect exact v13 device logs for a trusted frame callback, authoritative host/local IDs, carrier dispatch and host migration. Only then implement the adapter that binds this gate to PRP_TransportPort. Never reuse v12 code offsets.
2. Regression-test disconnect, host migration, 32-peer churn, consent revoke and late packets using two iPhones.
3. Rollback the stacked PR or revert its commit. The parent PR #12, main and the GTA IPA remain unchanged.
