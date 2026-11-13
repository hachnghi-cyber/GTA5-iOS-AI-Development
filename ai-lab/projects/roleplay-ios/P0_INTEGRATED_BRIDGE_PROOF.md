# P0 — Integrated Police RP Engine Bridge: Host + iPhoneOS Proof

**Date:** 2026-11-13 · **Scope:** source-only, independent module build, PR #10.  
**Do not equate this document with a GTA V iOS gameplay test or a signed IPA.**

## Why this was required

Prior PR #4 built the P2P/NativeBridge C sources as an iPhoneOS ARM64 dylib.
PR #9 added the synthetic GTA engine bridge and bounded mailbox. A green
Linux-host bridge simulator plus a green core-only ARM64 build did **not**
establish that the two modules would compile/link *together* against Apple
iPhoneOS SDK. This P0 work closes that narrow source-integration gap.

## 1. Combined host regression

Sources:
- `police-rp/v1.4/Integration/test_p0_combined_selection.c`
- `ai-lab/tests/test_p0_combined_target_bridge.py`

Real C sources compiled together (no mocks of the C implementation):
`police_rp_only.c`, `police_rp_adapter.c`, `prp_p2p.c`,
`prp_runtime.c`, `prp_mailbox.c`, `prp_engine_binding.c`.

The synthetic game/transport adapters test:
1. Three unique, connected game-attested peer identities; host ID 1 is on police duty.
2. Guest IDs 2 and 3 explicitly opt in and transmit consent with trusted sender metadata.
3. The host target selector chooses ID 2 (equal distance, lowest ID), independent of peer array order.
4. A newly verified position places ID 2 out of range. Host rejects cuff on that ID;
   the next eligible target becomes ID 3.
5. Host confirms ID 3 cuffed, produces a versioned STATE heartbeat, and the
   guest-side adapter applies **local-only** cuff/controls changes to ID 3.
6. ID 3 revokes consent. The guest's controls are released immediately;
   host applies revocation on next authenticated frame and no longer suggests ID 3.

**Evidence:** [GTA AI Lab CI 43399382390](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43399382390), 104 Python tests
including combined C scenario both standard host and Clang ASan+UBSan; the
seven pre-existing host C executables pass in normal, UBSan and ASan+UBSan.
The test uses fake engine callbacks and a fake authenticated packet carrier.
No iPhone was contacted.

## 2. Apple SDK integrated dylib

Workflow: `.github/workflows/gta-rp-ios-arm64-bridge.yml`.  
**Evidence:** [run 43399591380](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43399591380), **SUCCESS**, input commit
`83de437731ea011fa7055e71c0cdfef1b6ea9aaf`.

| Property | Verified output |
|---|---|
| Output | `libPoliceRPBridge.dylib` (source-only, unsigned) |
| SHA-256 of dylib (not its ZIP) | `5da9aabdf9dc1ce0ddc6df83afeff4e13eec1cb0f01c5a2971b6abe79eff3381` |
| Mach-O | `MH_MAGIC_64 ARM64 DYLIB`, thin arm64 |
| Build platform | `LC_BUILD_VERSION platform IOS` |
| Minimum OS | `16.3` |
| SDK | `18.5` |
| Dynamic dependencies | `@rpath/libPoliceRPBridge.dylib`, `/usr/lib/libSystem.B.dylib` (observed in `otool -L`) |
| Exported symbols checked | `_prp_bridge_frame`, `_prp_bridge_receive`, `_prp_bridge_enqueue`, `_prp_bridge_arrest`, `_prp_bridge_stop`, `_prp_host_find_nearest_cuff_target`, `_prp_inbox_push`, `_prp_runtime_tick` |
| GitHub Actions artifact | `GTA-RP-iPhoneOS-ARM64-BRIDGE-UNSIGNED-NOT-IPA`, ID `14023549233` |

Build uses Apple `xcrun --sdk iphoneos clang -arch arm64`,
`-miphoneos-version-min=16.3`, `-std=c11`,
`-Wall -Wextra -Werror`, `-fstack-protector-strong`, `-dynamiclib`.
Workflow archives `SOURCE_SHA256.txt`, `FILE.txt`, `ARCH.txt`,
`MACHO_HEADER.txt`, `DEPENDENCIES.txt`, `BUILD_VERSION.txt`,
`EXPORTS.txt`, `SHA256.txt`, Xcode/SDK versions and `README.txt`.
Artifacts expire according to Actions retention; source remains in Git.

## Reproduce

Run the two host tests in a C11/GCC and Clang-capable host environment:

```sh
python -m unittest discover -s ai-lab/tests -p test_p0_combined_target_bridge.py -v
```

The GitHub Actions workflow compiles with Apple SDK; on a Mac with
Xcode/SDK installed, follow
`.github/workflows/gta-rp-ios-arm64-bridge.yml`.
The SHA-256 is per exact source/toolchain build and should not be
assumed to match a rebuild.

## Constraints and remaining risk

- No RAGE engine entry point, game-frame hook, real position/role attestation
  or authenticated Online carrier is connected to the library.
- No code signing, entitlement verification, IPA modification/installation,
  GPU, memory or thermal performance validation was performed.
- The user-facing Police RP interactions (touch HUD, animation, jail) were
  not tested in an actual GTA Online session.
- The trusted transport needs a per-connection membership/identity epoch
  to make reuse of a numeric player ID unambiguous after disconnect.
  The current source model has `player_id` but not verified connection epoch.
  Do **not** infer peer identity continuity from `player_id` alone.
- The source-only PR #10 review remains pending; P0 is **in-progress**.

## Next gate

P0 must obtain independent code review, choose a non-duplicating integration
strategy for #7/#4/#9/#8, and pass CI on the final merged tip.
**After that**, P1 requires evidence of actual GTA v12 game-thread/native
callbacks and authenticated session metadata from an authorized device.
