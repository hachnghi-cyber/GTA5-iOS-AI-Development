# Phase 13 — Signed iPhone device bring-up preflight

Target: original GTAV v13.3 with exact game, ScriptHookV and three SHA-pinned Phase12 probe binaries. Police RP and RAGE-authorized sender session are NOT implemented by this test.

## Solved integration blocker

The existing packaging script accepts ORIGINAL IPA + separate dylib, and refuses to operate if a probe is already embedded. All three Phase12 UNSIGNED diagnostic IPAs already contain one pre-integrated Frameworks/RBPProbe.shv.dylib. Passing those IPAs to the old script therefore fails.

New tools/verify_existing_probe_ipa.py verifies exact original SHA256, bundle metadata, the ORIGINAL 59 archive entries byte-for-byte, exactly one new .shv.dylib, exact per-stage SHA, rejection of duplicate ZIP entries, symlinks, path traversal and unexpected extras. Use original GTAV-v13.3.ipa as reference. No commercial game data or code-signing secrets in this repository.

New ios/sign_prepackaged_probe_macos.sh signs the verified pre-integrated IPA using an explicitly supplied Apple Development identity, decoded provisioning profile and entitlements. It requires com.macport.gtav app entitlement, one team identifier, get-task-allow true, profile expiry in future and a registered device. It signs nested frameworks and the app, validates signature/CRC, then checks original GTA5 UUID and __TEXT,__text using existing verify_code_preserved.py. It refuses ad-hoc signing or overwrites.

## macOS developer use

First check exact E0 IPA:

    python3 tools/verify_existing_probe_ipa.py --original /path/GTAV-v13.3.ipa --diagnostic /path/GTAV-v13.3-Phase12-E0-DIAGNOSTIC-UNSIGNED.ipa --stage 0

Then (replace placeholder values with PRIVATE paths; never upload private keys, profiles, UDIDs or entitlements):

    bash ios/sign_prepackaged_probe_macos.sh ORIGINAL.ipa E0-UNSIGNED.ipa 0 "Apple Development: Owner (TEAMID)" PRIVATE-entitlements.plist PRIVATE.mobileprovision E0-SIGNED.ipa OPTIONAL-DEVICE-UDID

Test E0 only, collect fresh ScriptHook posthook.log and Documents/RBPProbe.log from the same physical iPhone run, evaluate callback. Then local E1 HUD. Then opt-in LAN E3 with two trusted iPhones. PR #16 native RAGE sender/session proof and authoritative gameplay control still remain independent.

## Verification boundaries

Exact locally supplied E0, E1, E3 UNSIGNED IPA original entry comparison: PASS (59 unchanged entries each). Synthetic Python negative/positive safety tests and Bash syntax: PASS locally. This signing wrapper has NOT executed real codesign because the current runtime has no macOS Keychain certificate or user provisioning profile. CI performs only test fixture checks and NEVER signs or handles the original proprietary IPA.
