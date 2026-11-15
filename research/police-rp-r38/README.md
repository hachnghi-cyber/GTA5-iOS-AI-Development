# Police Roleplay v13.3 R38 — GitHub Actions iPhoneOS build

This is **source code only** for an **unsigned ARM64 iPhoneOS dylib**, not a GTA V IPA.

- Source: R38 provided in the current project; 28 core C modules, 6 iOS adapter/bootstrap C modules and required headers/tools.
- Source packaging: `r38-ios-source.tar.xz`, SHA-256 `03d13f1848443ec7e7d23f0f7eedad6e922e79ec5e36b4d358e4d04642ce1810`.
- Build workflow: `.github/workflows/police-rp-r38-macos.yml` runs on `macos-15`, uses Apple iPhoneOS SDK with `xcrun`, invokes `ios/build_r38.sh` and validates `MH_DYLIB`, ARM64, iOS platform, install name and required exported symbols.
- Successful builds publish an artifact with the unsigned library and Mach-O evidence.
- No GTA executable, commercial assets, `.ipa`, signing credentials or private keys are included.

**Not proven:** iPhone dyld load, RAGE callback authentication, Online P2P integration, cuff/escort/jail gameplay, or device testing. Do not integrate into game before those steps are independently verified.
