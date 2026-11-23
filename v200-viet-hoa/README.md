# GTA5Port v2.0.0 – Mugoat Vietnamese native integration (experimental)

**Scope: Story Mode ONLY.** No localization required in Five Star Online. R6 fixes a likely iOS sandbox path issue and seeds a switchable mod ON by default. The standalone R6 IPA produced from these sources is **unsigned/experimental**: Story launch, GXT2 loading and font rendering on iPhone remain **unverified**.

This directory contains a C++17 NOVAPAK1 importer restricted to the 1,216 Story Mode GXT2 replacements (608 each in american.rpf and american_REL.rpf) plus five font/UI paths, an Objective-C++ constructor, a hash-pinned Mach-O IPA patcher, and synthetic unit tests. These files are independently authored source, not GTA or Mugoat game assets.

## GitHub Actions

- Linux CI compiles the importer and tests synthetic NVP packs, corrupted indices, idempotence, file collisions and simulated Mach-O patching.
- macOS 15 with Xcode builds an **unsigned ARM64 iPhoneOS dylib** and statically validates its install name. Only this authored dylib is uploaded as the public CI artifact.
- Optional private repository build: when repository visibility is **private**, manual workflow dispatch and two repository secrets `V200_IPA_URL` / `V200_NVP_URL` can download authorized assets, pin their SHA-256 hashes and build an **unsigned experimental IPA**. This job does not run in a public repo.

**No IPA, proprietary .nvp/.rpf data, signing credentials, or binary game data is committed.**

## macOS local build

With an exact, legally obtained original IPA and accented .nvp pack, run:

    bash v200-viet-hoa/tools/build_on_macos.sh       /path/GTA5Port-v2.0.0-Online-RC1.ipa       /path/VietnameseAccented.nvp       /path/v200-VI-UNSIGNED.ipa

Base IPA SHA-256: `a267c2683ce9df5cd68bc3498ade9282ee6d7dd201a2f0b2afeae0f64b0f587e`.

Accented NVP SHA-256: `a66869101865158c6d480834a7fec0d17ef5170c5e5c33cd037aa8507e4bfaea`.

The patcher emits an **unsigned** archive. Sign both the app and the embedded dylib before attempting to install it. On-device functionality has not been tested. The translation resources are installed under Documents/Mods; no Online translation is intended. The experimental dylib is still loaded on application start, **not** only on entering Story Mode, because no verified mode hook is available. The patched app may be rejected by Online integrity checks, and this project does **not** circumvent them. Loose .gxt2 resources have **not** been confirmed to override streamed RPF data.

## Review/release gates

1. Linux importer and synthetic Mach-O tests pass.
2. ARM64 dylib compiles in Xcode and validates as MH_DYLIB.
3. A privately built IPA passes ZIP checks and signing (not provided in source CI).
4. Test Story Mode, Vietnamese font rendering and RPF resolution on an iPhone.
5. No Online translation or Online gameplay changes are required. Do not claim the modified IPA preserves Online access until separately verified; a safe fallback for Online is the **unmodified v2.0.0 IPA**. Do not release based only on static CI.

Do not merge/release based only on a green CI.

## R6: No Vietnamese text on device — diagnostic / reproducibility

- Earlier R5 defaulted the mod to OFF, so a user who never enabled the toggle would still see English.
- R5 `ensure_dir` checked every ancestor with `O_NOFOLLOW`; the iOS sandbox can use a `/var` symlink. R6 canonicalizes existing `Documents` using `realpath` before creating mod subfolders, avoiding this failure mode while retaining symlink rejection inside `Mods`.
- Fresh R6 install: `Documents/Mods/Việt hoá Cốt truyện` (ON). One-time R5 migration: OFF → ON once; later user OFF/ON toggle choices are preserved using a separate activation marker.
- R6 writes `Documents/PGVI_Status.log` with result code, folder ON/OFF state, and R4/R5 migration indicators. iOS `Info.plist` has `UIFileSharingEnabled=true` and `LSSupportsOpeningDocumentsInPlace=true`, allowing access from Files on compatible signing/install setups.
- **CRITICAL:** In Five Star Port `NativeAssets.m`, `applyMods` drops replacements **inside RPF archives** when `localDataRoot` is absent; only whole-file replacements work with server streaming. R6 does **not** bypass this. The game must use locally downloaded game files in `Game files → A folder on this iPhone` for the GXT2 overlay approach to be usable.
- When text remains English, inspect `Documents/PGVI_Status.log` and `run.log` lines starting `Mods:`. An installer success `result=0` alone is not proof that the RPF overlay or GXT2 translation is active.
- GitHub Actions Linux iOS ARM64 build and R6 synthetic migration/symlink/ON/OFF tests: [run 45241169382](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/45241169382) — SUCCESS. IPA archive integrity (R5→R6): 324 ZIP entries, CRC PASS, only dylib changed. On-device test **not performed**.
- Do not upload or redistribute the proprietary IPA/NVP/RPF to this public repository. Release only after legal signing and Story Mode device tests.
