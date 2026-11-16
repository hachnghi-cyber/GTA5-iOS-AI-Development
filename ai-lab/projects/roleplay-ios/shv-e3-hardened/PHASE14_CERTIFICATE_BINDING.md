# Phase 14 — Development signing identity/profile binding (v13.3)

Exact Phase12 E0/E1/E3 iPhoneOS ARM64 modules were already built in Xcode; these remain unsigned until the user's own Apple Development signing inputs are supplied.

**Root cause found:** Phase13 checked Team ID, bundle ID, debugging entitlements and provisioning device list but never verified that the *specific* Keychain signing certificate was present in the provisioning profile's `DeveloperCertificates`. An app may receive a mathematically valid signature yet fail device installation for mismatched signer/profile.

**Implemented:**
1. Parse `security find-identity -v -p codesigning`; resolve an exact `Apple Development: …` label or 40-digit SHA-1 **uniquely**. Never silently sign with multiple matching identities or Apple Distribution.
2. Compare selected identity's SHA-1 against every DER certificate embedded in `DeveloperCertificates` of the decoded development provisioning profile, before signing any dylib.
3. Sign all nested dylibs and the app by the resolved fingerprint, not a potentially ambiguous label.
4. Decode **actual signed-app entitlements** via `codesign --display --entitlements :-` and revalidate them against the same profile, certificate and optional device UDID.
5. Preserve exact original GTA5 `LC_UUID` and `__TEXT,__text` per existing code-diff gate. Neither original game nor unsigned IPA is modified.
6. Add 16 fixture-only tests, plus Bash syntax checking. No private keys, profiles, IDs, IPA or purchased game data enter public GitHub CI.

**Locally verified:** Phase13+14 Python tests 34/34 PASS (including 16 new tests); `bash -n` PASS. **Not verified:** real Keychain identity, Apple certificate, iPhone installation, E0 callback, E1 HUD, E3 on two devices or RAGE-authenticated sender/session. Fails closed when fingerprint does not match a profile certificate.

Signing runbook remains in `PHASE13_SIGNING_PREFLIGHT_VI.md`. Prefer signing **E0 first** and collect fresh `posthook.log` + `RBPProbe.log` from the same run; do not attempt E3/PoliceRP until E0 passes.

## Additional security regression

The SHA-1 selector path now also validates the **resolved identity type**, rejecting Apple Distribution even when the caller supplies a correct 40-hex fingerprint. Exact label selection and fingerprint selection both require Apple Development. Local fixture tests 35/35 PASS; no real Keychain identity used.
