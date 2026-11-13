# GTA V iOS v13 — Police RP binary baseline and compatibility gate

**Source:** user-provided `GTAV-v13(4).ipa` (13 November 2026).  
**Workstream:** separate P0 binary-identity research for **v13**, independent of
unmerged v12 Police RP integration PR #10. NO commercial IPA or game binaries
are committed to this repository.

## Reproducible v13 identity

| Evidence | Measured result |
|---|---|
| IPA SHA256 | `cb1dd746c1fdc2faeb251aaaad9b7eedf4e46876b40a71b71d5b1180f4933361` |
| IPA size | 57,616,405 bytes |
| Archive CRC | all members passed |
| Extracted non-directory members | 53 |
| Mach-O binaries | 14 arm64 images |
| GTA5 executable SHA256 | `51b9a52ca00b8bbbd21ed901f636a30ee784dd10e8cfcd201f68756f0ff3333c` |
| GTA5 LC_UUID | `DBF9CECA-C973-3AFD-BFA0-435F453DDFCF` |
| libgtacompat LC_UUID | `8FBCB3AA-625B-316C-A5D2-64DA46C6CEFC` |
| iOS minimum | 16.3 |
| Bundle ID | `com.macport.gtav` |
| Build date (plist) | `20261113` |
| Static encryption LC_ENCRYPTION_INFO_64 | `cryptid=0` |
| Verification | Static metadata only; code-signature trust not verified |

The v13 game executable UUID is **not the recorded v12 UUID**:
`6A498E32-E70C-334C-BCA3-AFFD35E8D171`. Do not transplant v12
binary offsets, callbacks or instruction patches by numeric address.

## Relevant structural observations

The main `GTA5` executable links `@rpath/libgtacompat.dylib`; this
compatibility library exposes named `online_*` / `p2p_*` and
`compat_Online*` functions. Relevant **symbol NAME leads** include:

- `online_job_status()`, `online_work_status()`, `online_in_session()`;
- `p2p_current_session(bool*)`, `p2p_game_session(...)`;
- `compat_OnlineServerPlayerId`, `compat_OnlineHostProof`,
  `compat_OnlineJoinProof`, `compat_OnlineSetWorkStatus`.

These names are from Mach-O's export trie. **No C return types, ownership,
calling thread or authenticated identity semantics have been verified.**
Do not invoke them by guessed signature and do not treat host/join proof
labels as cryptographic proof. Any numeric relative symbol addresses are
diagnostic ONLY, not patch instructions.

`Menyoo.shv.dylib` links `MenyooKeyboardBridge.dylib`; the bridge
links UIKit and contains `UIAlertController`/text field references.
This establishes a static dependency, not that any keyboard is visible at
runtime. Keep Menyoo/ScriptHook **Story-only** in later roleplay designs.

`Info.plist` reports `DTSDKName=iphoneos27.0`, whereas GTA5's
`LC_BUILD_VERSION` records SDK 27.2. This is a metadata discrepancy
to review, not evidence of crash or incompatibility.

## Source now provided

`police-rp/v13/rp_v13_identity_gate.h/.c` and
`test_rp_v13_identity_gate.c` verify exact **trusted-loader** GTA5 and
libgtacompat UUIDs, reject missing/incorrect evidence and reject v12.
The result `RP_V13_IDENTITY_MATCH` means **binary UUID identity ONLY**.
It never enables arrests, network hooks or local-ped restrictions.

### Required architecture before gameplay

1. Match the v13 executable and `libgtacompat` source hashes and UUID
   on the actual installed device; evidence from the loader must be
   read-only and never accepted from a remote packet.
2. Establish a safe GTA v13 game-thread frame callback, with crash and
   reentrancy diagnostics and an explicit rollback.
3. Verify game-sourced Online `session_id`, local/host actor ID,
   authoritative roster (up to 32), and **connection-generation/epoch**.
4. Establish authenticated P2P carrier and receiver routing. This is NOT
   necessarily a standard GTA/FiveM packet or a standalone server.
5. Only then adapt the source-only Police RP C core (PR #10 pending
   review). Carry forward the consent, replay, safe opt-out and jail
   authority fixes; implement native player interactions only after
   the above evidence passes, then test on two actual iPhones.

## Not yet verified

No v13 game-frame hook, RAGE Engine ABI, signed IPA, deployed dylib,
authenticated peer state, 2-iPhone Police RP, or original C++ game source
has been recovered or tested. This PR must remain **DRAFT** until the
review, hardware evidence and dependent PR status are resolved.

Evidence archive and machine-readable static inventory were generated
locally, but only nonproprietary independently authored source and
metadata are committed here.
