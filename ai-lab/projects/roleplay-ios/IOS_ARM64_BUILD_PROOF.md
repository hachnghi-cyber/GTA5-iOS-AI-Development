# RP-002 — Native iPhoneOS ARM64 source-core build proof

**Artifact is a source-only, unsigned `.dylib`, NOT a playable GTA V IPA.**

- GitHub Actions run: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43347091287
- Workflow: `.github/workflows/gta-rp-ios-arm64-core.yml`
- Source branch: `feature/rp-source-inventory-ci`
- Source commit built: `265b359db58363739e6f855990d99b01a96cbb59`
- Artifact: `GTA-RP-iPhoneOS-ARM64-CORE-UNSIGNED-NOT-GAMEPLAY` (artifact ID `14001483889`)
- File: `libPoliceRPCore.dylib`
- File size: **50,840 bytes**
- SHA256: `0c47c248a31996b60d61fcf14be04bdd0711cd4b263c0c5ab2fa4650efd2acf2`
- Architecture: **thin arm64** (`lipo -info`)
- Mach-O `LC_BUILD_VERSION`: platform **IOS**, minimum OS **16.3**, linked with iPhoneOS SDK **18.5**
- Dependencies: `/usr/lib/libSystem.B.dylib` (and own install name `@rpath/libPoliceRPCore.dylib`)
- Exported C functions include `_prp_runtime_init`, `_prp_runtime_tick`,
  `_prp_runtime_receive`, `_prp_runtime_stop`, `_prp_host_receive`,
  and local `_pr_adapter_tick`

The binary metadata and SHA256 were confirmed from the downloaded GitHub
Actions artifact, not merely inferred from workflow YAML. It contains the
protocol and policy source modules from `police-rp/v1.4/P2P/` and
`NativeBridge/`; it has **no game-frame hook, authenticated GTA Online
carrier, GTA5 dependency or input mapping**.

## What is *not* proven

- No `GTA5` executable was patched or launched.
- No Apple code signing or provisioning was applied.
- No target IPA was generated or attached to the repository.
- No authenticated RAGE multiplayer dispatch was integrated.
- No actual iPhone/iPad or two-device roleplay test was performed.
- This standalone library is not sufficient to cuff players in the game.

## Next gate

Obtain an exact-v12 trusted game-thread callback and authenticated host/client
transport carrier, then create an iOS adapter that passes engine-proven
`PRP_TransportContext` and `PR_EngineView` to these exported functions.
Only after host/client integration and device logs should IPA packaging,
signing and rollback be attempted.

**Rollback:** remove the workflow and this source-build evidence without
changing existing IPA binaries or user game saves.
