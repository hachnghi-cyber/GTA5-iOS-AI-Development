# Baseline — Operation RAGE Breakthrough

2026-11-16; PR #16, `feature/winstom-rp-ipa-audit-20261116`.
Restored from remote checkpoint `64e450ef7616fd35b32e0646241be0f8a08bc7d2`.
Current continuation: [ROLEPLAY_CONTINUE.md](ROLEPLAY_CONTINUE.md).

| Component | Evidence and scope | Status |
| --- | --- | --- |
| Exact GTA v13.3 binary | SHA/UUID in `baselines/phase9-v133-engine.json`; local inspector succeeds against user IPA | VERIFIED (static) |
| Original game loop | Prior one-iPhone USB `jobs_update` stop and `MacportOnlineUpdate` caller; `state.json` | DEVICE VERIFIED (one sample) |
| Local stock job fields | `baselines/v133-stock-job-device-20261116.json`: empty known ID, kind=0, state=0 at guarded callback | DEVICE VERIFIED (idle sample only) |
| Diagnostic transport | `baselines/phase10-iphone-windows-tls.json`: real GREET/DOCUMENTS over mTLS 1.3 | DEVICE VERIFIED (iPhone ↔ Windows only) |
| Police rules / mapping / transactions | Ten C programs with GCC/Clang sanitizers; CI 43843235701 | IMPLEMENTED; host tests only |
| iPhoneOS library | CI 43843224585, exact ARM64 cross-build | BUILD PASSED; latest source modules dormant |
| E0/E1/E3 diagnostic dylibs | PR19 `1e910d4`, CI 43969424836; independent downloaded artifact inspection | IPHONEOS ARM64 BUILD PASSED; unsigned, no device test |
| Native receive origin observer | `--receive-context`; exact code hashes and synthetic receive/local/error fixtures | IMPLEMENTED; DEVICE VALIDATION PENDING |
| Authenticated native sender + session incarnation | No runtime evidence carrying these together into scripted callback | PENDING |
| Remote gameplay and A/B cuff/release | No live engine adapter or two-iPhone result | PENDING |

The known test iPhone reconnected on 2026-11-17. Scripted-handler and
OnNetEvent observations each timed out after 30s, while jobs_update hit the
exact caller. This does not establish authenticated receipt or absence of
peers; see `baselines/v133-usb-receive-attempts-20261117.json`. A second
cooperating iPhone is still needed for the requested gameplay acceptance test.
Existing IPA and private game assets remain local. No new IPA is required for
the optional USB observation if the installed development signature is valid.
