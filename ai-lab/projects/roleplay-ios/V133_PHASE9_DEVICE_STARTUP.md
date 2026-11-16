# Phase 9 device checkpoint

User-supplied startup file and run log, 2026-11-16. Evidence is limited to one
iPhone14,3 on iOS 18.6 (22G86). The startup payload matches across the two files:
`source_revision=phase9-carrier-unbound`, `gta5_uuid_matches=1`, and the expected
UUID from `baselines/phase9-v133-engine.json`. Thread, sender and network flags
printed by the startup probe remain zero. The signed package digest was not
measured on the device.

| Time in game log | Observation | Scope |
| --- | --- | --- |
| 19.80–22.54 s | Macport Sandbox selected; scene loaded | Story Mode was not tested in this log |
| 22.59, 23.47 s | `CGame::Update` > `CTheScripts::Process` > `InternalProcess` > `scrThread::UpdateAll` > `GtaThread::Update` > `scrThread::Run` > `MacportOnlineUpdate` | VM execution in the game loop observed twice; OS thread identity, cadence and hook ABI remain open |
| 28.40, 83.33 s | `CNetwork::Update` > connection dispatch > `OnNetEvent` > `ReceivedMessageData` delegate > `netObjectMgrMessageHandler` > clone creation | Stock replication path observed; no scripted RP event or authentication attestation |
| 29.11–29.98 s | Stock session joined with three players at join; script session reaches participant | No PRP3 peer delivery demonstrated |
| 99.5 s | App goes to background | The supplied current-run log ends here without a recorded crash |

The symbol addresses minus their frame offsets agree with the exact-build static
baseline at a single page-aligned Mach-O slide for 11 symbols. The abbreviated
stacks omit frames. The two game-loop paths do not establish that the
connection-to-sender binding is cryptographically authenticated for the scripted
event, or that a session generation survives dispatch. Keep PRP3 unbound until
that provenance and the pump context are verified.

Raw logs remain local. This checkpoint intentionally omits session invitations,
player names, identifiers and runtime addresses.

## Windows USB retest

Windows found the GTA installation under its signing-suffixed bundle ID,
started it over USB without terminating an existing instance, and downloaded
only GTA diagnostic files over File Sharing. A new Phase 9 launch marker at
08:42:53 UTC confirms the expected UUID. The stock Sandbox scene loaded at
79.53 s and logged another `MacportOnlineUpdate` stack at 79.55 s. The sampled
log contains no `CScriptedGameEvent` or `ProcessEventData` frames.

The installed app reports `get-task-allow=true`. With Developer Mode
already enabled, a personalized DeveloperDiskImage mounted successfully
and the loopback debugproxy answered the debugger capability query. No
debugger attached to GTA in this retest. RP sender/session and two-device
delivery remain unverified.
