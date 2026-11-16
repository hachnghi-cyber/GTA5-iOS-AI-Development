# Phase 11 — Minimize E3 device bring-up blockers

Only diagnostic E0/E1/E3, **no police actions or RAGE network hooks**. Based on Phase10 verified host source in draft PR #19. Original GTA v13.3 IPA, Mach-O executable and original Online code unchanged.

## Source changes
1. One `config_sane()` gate used by both the sandbox text config parser and direct `rbp_network_start()`. Rejects all-zero HMAC key, session, player/peer IDs, identical IDs, out-of-range ports, bad IPv4 and unterminated peer address. A nonzero key alone is **not** proof of cryptographic entropy; use `tools/make_two_phone_configs.py` to generate each ephemeral test session.
2. Negative C network tests cover blank key in file plus key/session/player/peer/port/address bypass of parser. Tests also preserve existing valid-path and wrong-peer UDP assertions.
3. Xcode iPhoneOS build validates exported `_DllMain`, ARM64 slice, actual `LC_RPATH @loader_path`, `LC_BUILD_VERSION platform IOS`, and absence of strong dependencies on optional ScriptHookV/libgtacompat libraries. Static metadata is logged with artifact; no IPA or signing credentials are uploaded.

## Evidence and bounds
- Locally: `CC=clang bash tools/run_phase3_checks.sh` PASS; `CC=gcc bash tools/run_phase3_checks.sh` PASS; original SHA/UUID preflight PASS, Python 46/46, C ASan/UBSan, localhost UDP, two independent Linux processes and three ARM64 object builds.
- iPhoneOS link is **only confirmed** if workflow run on `macos-15` completes and produces its unsigned dylib artifact.
- Genuine callback registration, native HUD visibility, two-iPhone E3 transfer and RAGE sender/session authentication remain unverified until real device logs and visual evidence.
- Local tests check configuration *misuse*, not RAGE transport authentication. Must not enable arrest, escort, incarceration, or other gameplay from this diagnostic endpoint.
