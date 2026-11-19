# GTA5Port RP v1.7 — Source-based Native Host Integration

## Purpose
Migrate the proven RP file/socket bridge from repeated Mach-O IPA injection to a **source-level native C module** in GTA5Port. This is a diagnostic integration, **not a functional GTA Online Roleplay game**.

## Version provenance: DO NOT assume public upstream = user's v2.0.0
- Pinned **public upstream**: [kevinerikjs/gta5-ios-port](https://github.com/kevinerikjs/gta5-ios-port), commit `9357c182b5cddd58e16dee684ea07ebc18a97a5d`.
- Public upstream Info.plist: **1.5.2 build 20**, its GameMode.swift contains **Story/Sandbox only**.
- User's actual existing GTA5Port **2.0.0 build 45** IPA contains Online and a different executable name **PlayGTA5NativeEngine**. Its matching full source has **not** been verified.
- **Do not replace or distribute v2.0.0 with a recompiled public v1.5.2 app.** Preserve the existing IPA, Online modes, launcher, Vietnamese strings, and mods. Never commit game binary/files or signing assets.

## Integration method
`tools/source_from_v16.py` loads the source bundle in `../native-bridge-v16/source_bundle.tar.xz.b64`, verifies the bundle's SHA256 and exact C source SHA256, then reconstructs **four original source/header files**:
- `app/Source/NativeRPBridge.c` (C11 ARM64 host bridge; SHA256 `80c1e6e42b43617570e07a55548be6f98400f4163a7fc00d9b0dd99802b5e7af`)
- `app/Source/NativeRPBridge.h`
- `app/Source/rp16_json.c`, `rp16_json.h`

It makes two guarded source edits:
- `app/Source/Native-Bridging-Header.h` imports `NativeRPBridge.h`.
- `app/App/NativePortViewController.swift` invokes `PGRPBridgeStart(NSHomeDirectory())` only on `WORLD_READY` in **Story Mode** when mods are active, and `PGRPBridgeStop()` on app leave.

**No constructor auto-connects**. In addition, the bridge needs the user's `Documents/RPBridgeNetwork_v15.conf` with `enabled=1` before any LAN connection. The bridge is diagnostic, uses a bounded RFC1918-only/plaintext TCP connection and RPF8/RPR1 file mailboxes. It does not invoke RAGE/gameplay natives or alter Online networking. Sensitive keys must not be committed. Never port-forward this plaintext server.

## Reproducible upstream test
From the repository root, with a licensed source checkout of GTA5Port at the pinned commit in `upstream/`:
```bash
python3 ai-lab/projects/roleplay-ios/source-port-v17/tools/source_from_v16.py upstream \
 --payload ai-lab/projects/roleplay-ios/native-bridge-v16/source_bundle.tar.xz.b64 --check

python3 ai-lab/projects/roleplay-ios/source-port-v17/tools/source_from_v16.py upstream \
 --payload ai-lab/projects/roleplay-ios/native-bridge-v16/source_bundle.tar.xz.b64
```
The script refuses incompatible source anchors and conflicts, stores backups under `upstream/.rp-source-bridge-v17-backup/`, and is idempotent. A separate **full-source ZIP** delivered to the project owner contains a reversible `--revert` tool, plain-text C sources, 12 local regression tests and binary hashes.

CI: [Source Integration workflow](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/workflows/build-gta5port-rp-v17-source.yml). It checks out the exact public upstream, applies the overlay, runs true two-client TCP regression, compiles GCC/Clang and validates iPhoneOS ARM64 C + Swift syntax. **It cannot build or sign the full engine/game without the owner's lawful game inputs.**

## Verified vs unverified
**Verified:** v1.4 ASI->host RPF8 on iPhone (`POSE_LIVE`); v1.6 two-way localhost test; v1.7 C/Swift source overlay on pinned public upstream; CI Linux/macOS syntax.

**Unverified:** source correspondence to v2.0.0, building the full port with this overlay, v1.7 iPhone device run, 2-iPhone RP, ScriptHookV F mailbox consumer, remote PED spawn/animation, vehicle sync and policing RP.

Public source MIT license applies only to code from the original port, not Rockstar assets or third-party components. Keep PR draft until device and version-gating evidence exists.
