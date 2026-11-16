# RAGE Source Hunter — verified source-level links and v13.3 integration gate

Date: 2026-11-16. Scope: GTA V iOS v13.3, Roleplay Online.
Status: code research + existing project review; **not** a two-iPhone gameplay validation.
The current implementation checkpoint is PR #16 on
`feature/winstom-rp-ipa-audit-20261116`.

## Public source references and actual usefulness

| Source | Exact file / relevant API | License constraint | Integration decision |
| --- | --- | --- | --- |
| CitizenFX/FiveM | [NetLibrary.h](https://github.com/citizenfx/fivem/blob/master/code/components/net/include/NetLibrary.h): `SendNetEvent`, reliable handlers; [ServerEventPacketHandler.cpp](https://github.com/citizenfx/fivem/blob/master/code/components/citizen-server-impl/src/packethandlers/ServerEventPacketHandler.cpp): rate-limited event handling; [netGameEvent.h](https://github.com/citizenfx/fivem/blob/master/code/components/gta-net-five/include/netGameEvent.h): event dispatch types | [Repository license is NOT blanket MIT](https://github.com/citizenfx/fivem/blob/master/LICENSE); check each directory before copying | LEVEL 3 architecture reference. FiveM Windows runtime is not an ARM64 iOS bridge. |
| QBCore police | [client/main.lua](https://github.com/qbcore-fivem/qb-policejob/blob/main/client/main.lua), [server/main.lua](https://github.com/qbcore-fivem/qb-policejob/blob/main/server/main.lua): police net events and state validation | GPL-3.0-or-later | LEVEL 3 logic reference only; reimplement in C11, do not copy Lua into unrelated code without reviewing license. |
| ScriptHookVDotNet | [NativeFunc.cs](https://github.com/scripthookvdotnet/scripthookvdotnet/blob/main/source/core/Game/NativeFunc.cs), [Native.cs](https://github.com/scripthookvdotnet/scripthookvdotnet/blob/main/source/scripting_v2/GTA.Native/Native.cs): invocation/main-thread contract | zlib project, Windows/ScriptHookV/.NET dependencies | LEVEL 3: main-thread native ABI design, not a buildable iOS online module. |
| GTA NativeDB | [natives.json](https://github.com/alloc8or/gta5-nativedb-data/blob/master/natives.json) | Data redistribution rights not established here | LEVEL 3 signatures/reference, no claim of compatibility of any specific native hash on v13.3. |
| ENet | [host.c](https://github.com/lsalzman/enet/blob/master/host.c), [protocol.c](https://github.com/lsalzman/enet/blob/master/protocol.c): reliable UDP | MIT | LEVEL 2 if a new overlay is required. Do not introduce until the existing transport is proven inadequate. |
| GameNetworkingSockets | [isteamnetworkingsockets.h](https://github.com/ValveSoftware/GameNetworkingSockets/blob/master/include/steam/isteamnetworkingsockets.h): reliable delivery, encryption, connection API | BSD-3-Clause | LEVEL 2 optional side-channel; larger porting surface than ENet. |
| alt:V / RAGE MP | [alt:V FAQ](https://docs.altv.mp/articles/faq.html), [RAGE MP GitHub](https://github.com/ragemultiplayer) | Some SDK/API code public; core transport is not proven open | LEVEL 3/4; architecture reference, not a drop-in engine. |

## What already exists in this project's PR #16

- Source-only PRP3 versioned codec, nonce/state checks, bounded mailbox and
  Police RP authority rules. See `v133_interaction/include`, `src`, and `tests`.
- A direct, authenticated TLS diagnostic route demonstrated between one
  development-signed iPhone and a Windows host. Evidence is in
  `baselines/phase10-iphone-windows-tls.json`.
- Static ARM64 function/branch table pinned to GTA5 Mach-O UUID
  `EB122C35-96F4-307F-91C3-A2255DD9C685` in
  `baselines/phase9-v133-engine.json`.
- A fail-closed game/RP identity bridge with synthetic tests;
  **no verified mapping to the actual engine peer for a gameplay event**.

## Root blocker and minimal falsifiable experiment

Do not conflate three different facts:
1. `on_net_event` / `script_event_handler` actually ran on one device.
2. A message originated from the expected *remote engine peer* and belongs to
   the current game session incarnation.
3. The matched peer's roleplay state was applied and observed on both devices.

Only (1) is directly approachable with the current read-only USB observer.
The Windows observer can sample `--site on_net_event` and
`--site script_event_handler` on a dev-signed GTA v13.3 build. It records
a validated PC stop with exact-build guards, **not** sender/auth provenance.
For (2), obtain a receive stack and a consistent authenticated
connection-to-engine-player mapping across join/leave/migration. For (3),
enable gameplay only after (2), and test A/B plus a third observer when
available, with event ID, ack stage, state revision and duplicate/replay cases.

The desired data flow remains:

```text
engine-owned session/peer identity (UNVERIFIED)
 -> validated transport adapter
 -> bounded RP event codec / replay guard (HOST TESTED)
 -> game-thread mailbox (HOST TESTED)
 -> authenticated game-player binding (HOST TESTED WITH MOCK SNAPSHOTS)
 -> Police RP semantic state (HOST TESTED)
 -> engine native gameplay mutation (NOT CONNECTED)
 -> two-device replicated state (NOT TESTED)
```

**Release gate:** No claim of functioning online handcuff until two devices
agree on the same identified target, session generation and cuff state, and
the state survives engine sync ticks. Do not repurpose stock event type IDs
or patch unverified offsets. Do not ship proprietary IPA assets via GitHub.
