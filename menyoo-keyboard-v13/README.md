# Menyoo iOS Keyboard — v13 (Experimental)

Goal: Menyoo → SEARCH → show the native iOS software keyboard → enter text → Done → return text to the GTA native API. This is **not a verified gameplay fix**.

## Implementation

- src/MKBBridge.mm: Objective-C++ UIKit alert and bridge for GTA on-screen keyboard natives. Re-exports nativeInit, nativePush64, nativeCall; forwards non-keyboard calls to the original ScriptHookV.
- tools/patch_ipa.py: version-locked patch of exactly three chained imports in Menyoo.shv.dylib, plus an additional dynamic library dependency. Refuses unexpected binaries or IPA versions.
- .github/workflows/menyoo-keyboard-v13.yml: builds the iOS ARM64 dylib automatically on pushes and PRs; packages a test IPA only when explicitly dispatched, if GTAV_V13_IPA_URL is configured.

Source binary fingerprint required:
- Exact input IPA SHA256: 57ad5135178ceac4ca20247c7e0985956c71ccaee24a6c9faf7a70490bd5addb
- Menyoo dylib SHA256: 7dab057f15d87e50ebc5512fd4be3f5535ae6a732ca68c61294d3037d52eeee8

The base IPA is deliberately **not included in Git**. Never upload Apple signing certificates, provisioning profiles, private assets, or game data.

## GitHub Actions

The workflow runs the source-only ARM64 compile automatically when this branch changes or a PR is opened and uploads the MenyooKeyboardBridge.dylib build artifact.

To additionally package the IPA, a maintainer must:

1. Merge the reviewed workflow to the default branch so workflow_dispatch becomes available (GitHub requirement).
2. Configure repository secret GTAV_V13_IPA_URL as a temporary, authorized HTTPS link to the **exact** v13 VI + Telegram unsigned IPA. Do not publish the link.
3. Run Actions → Menyoo v13 iOS Keyboard Bridge → Run workflow → package_ipa = true.
4. Retrieve the unsigned IPA artifact. Re-sign the app **and every changed dylib** locally using authorized Apple credentials.
5. Test on-device: Story Mode → Menyoo → SEARCH, Vietnamese/Unicode text, Done, Cancel, repeated entry, other ScriptHook calls and background/foreground.

IPA packaging is **not** a loader/runtime test. If the fingerprint differs, halt and re-audit the Mach-O imports; do not bypass the fingerprint guard.

## Technical limitations / release gates

- Keyboard native hashes and eight-argument DISPLAY signature were inferred from prior v13 static inspection, not proven on a live iPhone.
- The port might not expose the expected ABI, nativeCall pointer lifetime or dlopen library path. These require device logs.
- The shim changes a dylib load command and three import ordinals; it is NOT a portable patch for v14.
- This does not alter Online gameplay, RPF assets or Vietnamese translations.
- Do not merge into a general release until macOS CI and real-device QA pass. Keep the previous working v13 IPA as a rollback.

**CI success and actual iPhone functionality are separate.** Fix is not considered complete until Menyoo receives input on device without regressions.
