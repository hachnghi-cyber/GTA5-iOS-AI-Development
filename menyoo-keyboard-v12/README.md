# GTA V iOS v12 — Menyoo iOS keyboard (EXPERIMENTAL)

## Verified version fingerprints

- Base user-uploaded IPA SHA-256: `23c039cb59e24f0107243a32252a3a60fbca1c934ac482d285109c323132f0dc`
- Menyoo ARM64 SHA-256: `7dab057f15d87e50ebc5512fd4be3f5535ae6a732ca68c61294d3037d52eeee8` (identical to v13)
- v12 ScriptHookV SHA-256: `f8272dc62894dc45bf0d8bc75ef6ff23c6b1ea35d22b6bc4a65fb7df62b6f176` (different binary from v13)
- Target app minimum iOS: 16.3; bundle ID: `com.macport.gtav`
- Verified original exports: `nativeInit`, `nativePush64`, `nativeCall`.

## Files

- The shared UIKit bridge is at `menyoo-keyboard-v13/src/MKBBridge.mm` (same Menyoo binary v12/v13).
- The v12-only, version-gated IPA packer is `menyoo-keyboard-v12/tools/patch_ipa.py`.
- Build the bridge on macOS through `.github/workflows/menyoo-keyboard-v13.yml`, then run the v12-only packer.

Example using only authorized local files (no original IPA uploaded to GitHub):

    python3 menyoo-keyboard-v12/tools/patch_ipa.py --ipa 'GTAV-v12(4).ipa' --dylib MenyooKeyboardBridge.dylib --out GTAV-v12-Keyboard-UNSIGNED.ipa

## Local static integration (2026-11-13)

- The exact v12 uploaded IPA was repackaged locally using the **CI-built ARM64 dylib** from GitHub Actions run 43427034865.
- Experimental unsigned IPA SHA-256: `2d8dcf385f315750aca22a63da6c970eef7fd8119f6b083ae7525a9f946ec7e9`.
- ZIP CRC PASS; only the original `Menyoo.shv.dylib` changed, plus new executable `MenyooKeyboardBridge.dylib`.
- `llvm-objdump` confirmed the extra dyld dependency and the exported bridge symbols.
- **Not signed, not installed on an iPhone, and NOT verified to accept typed text in Menyoo.**

Before device QA, sign all binaries as required and back up saves. Test Story Mode → Menyoo → SEARCH → keyboard → Vietnamese input → Done and Cancel; gather device log if loading or native-call faults occur.

**Do not merge as a release before on-device verification.** The v13 GitHub Actions macOS build validates the bridge compiler only, not the v12 runtime or IPA signing.
