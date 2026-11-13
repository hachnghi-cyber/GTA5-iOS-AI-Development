# GTA V iOS v12+ — partial v13 features (EXPERIMENTAL)

This branch is stacked on `feature/menyoo-v13-ios-keyboard-bridge` and must not be merged into main as a release without real device QA.

## Verified build (GitHub Actions)

- ARM64 `V12Places.shv.dylib` compiled with iOS SDK on macOS / Xcode; host C++ tests and ad-hoc codesign verification passed.
- GitHub Actions run: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43436889200
- Dylib SHA256: `4b6a07a4d1cf5a5107e3da641d55dfc8c43950e9c1d34ea18d2912a155279c9c`
- Source revision: `233e6580eb13d39f5e4d6098a3c5751d59014896`
- **No signed iPhone run / touch runtime / native action has been verified.**

## Code

- `native/V12Places.mm`: optional ScriptHook UIKit location overlay with three buttons; one saved position persisted to UserDefaults; waypoint with conservative ground check; only Story Mode.
- `native/PointValidation.hpp`: finite coordinate bounds and Online gating.
- `tests/test_point.cpp`: host-side logic tests.
- Workflow: `.github/workflows/build-v12plus-places.yml`.

## Local integration on exact v12

A version-locked local Python tool packages the feature dylib into the *user-provided* v12 keyboard IPA. **Game assets and IPA are NOT committed**.

- Base original v12 IPA SHA256: `23c039cb59e24f0107243a32252a3a60fbca1c934ac482d285109c323132f0dc`.
- v12 Keyboard IPA SHA256: `2d8dcf385f315750aca22a63da6c970eef7fd8119f6b083ae7525a9f946ec7e9`.
- Safe translation-only v12+ IPA SHA256: `f0a549558241425cdf1a3b1ad74202e65a341c9a5ea18f911ced4af694b5cc6b`.
- With addon experimental IPA SHA256: `a5980001fc7af769b24a175a4e27a6d7490337a14c6eda63893f0af8476e116b`.
- 198 existing v12 Vietnamese UI strings updated from v13; no v13 gameplay binaries transplanted; no executable modified.

## Release blockers

1. Confirm that ScriptHookV discovers/loads `Frameworks/V12Places.shv.dylib`. Its presence in ZIP proves **nothing** about actual load.
2. Confirm native `Vector3` return ABI and callback lifetime on real iPhone. Look for `[V12_PLUS]` in run.log.
3. Confirm Story Mode buttons Save / Return / Waypoint and edge cases. Never use this prototype as Online movement capability.
4. Sign the modified IPA and every dylib with authorized Apple credentials. Preserve the last known working v12 IPA as rollback.
5. New v13 renderer (libgtamsl), Online weapon restrictions, extended bodyguards, custom keys, trainer sizing and RAM 2 GB profiles are **NOT ported**.

Source cannot reproduce proprietary v13 game engine features without legal source, verified ABI and device regression tests. This prototype implements a narrow independent subset, not a full v13 feature transplant.
