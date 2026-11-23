# GTA5Port v2.0.0 – Mugoat Vietnamese native integration (experimental)

**Status:** Automated source CI only. Not an installable, signed IPA. Game launch, fonts, RPF overlay and Five Star Online are **unverified**.

This directory contains a C++17 NOVAPAK1 importer, an Objective-C++ constructor, a hash-pinned Mach-O IPA patcher, and synthetic unit tests. These files are independently authored source, not GTA or Mugoat game assets.

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

The patcher emits an **unsigned** archive. Sign both the app and the embedded dylib before attempting to install it. On-device functionality has not been tested. Five Star Online may reject patched apps; this project does **not** circumvent integrity protections. Loose .gxt2 resources have **not** been confirmed to override streamed RPF data.

## Review/release gates

1. Linux importer and synthetic Mach-O tests pass.
2. ARM64 dylib compiles in Xcode and validates as MH_DYLIB.
3. A privately built IPA passes ZIP checks and signing (not provided in source CI).
4. Test Story Mode, Vietnamese font rendering and RPF resolution on an iPhone.
5. Test Online integrity independently; do not release until behavior is understood.

Do not merge/release based only on a green CI.
