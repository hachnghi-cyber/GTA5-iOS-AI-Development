# GTA5Port RP v1.9 - SINGLE LOCAL PED Proof, Story only (experimental)

## Scope and current evidence
Uses v1.8 RPR1 guest decoder and v1.6 host RPR1 mailbox. Creates at most ONE **local, non-networked, frozen** NPC near the current Story player's RPF8 pose. Remote peer data merely authorizes a proof-of-concept spawn; it is NOT used to drive remote movement. This is not synchronized multiplayer or a FiveM replacement.
v1.8 guest mailbox has NOT YET BEEN VERIFIED on real iPhone v2.0.0. Do NOT enable v1.9 until v1.8 console log proves `RP18 MAILBOX_VALID count=1` and then count=0 when peer leaves.

## Runtime safety gates
- Explicit marker file: put `RP19_STORY_TEST.txt` in same Mods child folder as the existing RPPoseToFile-v0.8-E.asi. Exact bytes (including newline): `RP19_STORY_TEST=1\n`.
- Explicit F11 press for each new launch; F11 toggles arm/disarm (use on-screen Mod keys or physical keyboard). Nothing spawns merely from installing the ASI.
- NETWORK_IS_SESSION_ACTIVE and NETWORK_IS_GAME_IN_PROGRESS both must return false. Because v2.0.0 host is closed-source, these are **not a cryptographically reliable positive Story-mode attestation**; operator MUST only test while in Story Mode, never Online.
- Exact CRC-validated RPF8 local pose and RPR1 mailbox with exactly **one** remote peer. Missing, malformed, empty or 2+ peers means no spawn.
- Fresh mailbox epoch/generation within 16 ticks (4s). No new frames, disarm, removal of marker, loss of remote or network-mode change forces cleanup.
- Model a_m_m_business_01 must be valid, a ped, and loaded (4s timeout) before spawning. All native calls occur on the cooperative ScriptHookV script thread.
- Spawn location is next to the local player (+3m X, +2m Y); does NOT apply remote XYZ, attach, assign tasks, control player, perform police interactions or affect Online.
- Only one ped handle, frozen. On teardown, DELETE_PED is called only if DOES_ENTITY_EXIST says true. No network flags or game binary patch.
- Before opt-in file exists AND F11 is pressed, **no RAGE native calls** are made by this mod.

## Build
GitHub Actions workflow: `.github/workflows/build-gta5port-rp-v19-ped.yml`.
The Win64 x86-64 PE32+ .asi is compiled using Clang MSVC target and pinned MIT-port reference PE linker at upstream commit `9357c182`. C11 mock/pure tests cover local and remote checksum, count validation, model joaat, explicit gate. No game files, signing identity or original executable are needed for CI.

## Device installation (only AFTER v1.8 guest mailbox proof!)
1. Back up game and mod data; keep the working v2.0.0 IPA and v1.6 ARM64 host bridge. Do NOT install an older compiled 1.5.2 source app in place of v2.0.0.
2. Put `RPStoryPedProbeV19.asi` in the SAME Mods subfolder as RPPoseToFile-v0.8-E.asi and v1.8 reader. Start Story Mode (not Online).
3. Place exact marker file `RP19_STORY_TEST.txt`; use the attached template. Connect a single simulated laptop peer through your private LAN RP server and make sure v1.8 reads `count=1`.
4. Press F11 on your iPhone through Mod keys. Expected in native-port.log: `ASI console: RP19 ARM_REQUEST`, `RP19 MODEL_REQUESTED`, `RP19 PED_CREATED_SINGLE_LOCAL_PROTOTYPE`. An NPC may appear near your player if native compatibility is present.
5. Press F11 again or REMOVE the marker: expect `RP19 DISARM`, `RP19 PED_CLEANUP`. End the laptop peer to test automatic cleanup. If a crash occurs, remove the ASI and marker and revert.
6. Never enable this diagnostic in an Online session. Even with network guards, source-level mode attestation on v2.0.0 is unverified.

## Important release caveats
- Real-device CREATE_PED, model loading, cleanup, and v1.9 ScriptHookV imports are UNVERIFIED. Only CI GCC/Clang, pure validation tests and PE64 artifact creation have been proven.
- Plaintext RP TCP is private LAN diagnostic only. No port forward and no public server.
- RAGE original hashes were cross-checked with community native references. Their availability on GTA5Port v2.0.0 is not guaranteed.
- Never merge the Draft PR or claim Online RP complete based only on these tests.
