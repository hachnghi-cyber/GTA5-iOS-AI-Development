# Phase 9 — exact v13.3 sender path and carrier collision

2026-11-16, continuing PR #16 at `59d46193fd71dc995e283ea1fafebc7485e451de`.
Status: **static evidence and source integration; engine transport UNBOUND**.
User has one iPhone. No device test has been performed in this session.

## Inputs independently inspected

| Input | IPA SHA-256 | Main executable SHA-256 / UUID |
| --- | --- | --- |
| GTAV-v13.3.ipa, 58,455,384 bytes | `7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7` | `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc` / `EB122C35-96F4-307F-91C3-A2255DD9C685` |
| Winstom-0.7.177.ipa, 243,710,841 bytes | `eba3b6e29ce31c3667974892f5f650bc526df805f072111b95fc3c041b364641` | `df7427d0e19271b1b49f0132d8d6d3be0dd65a04b4c86991749b75ed9b15f0e4` / `048DCEFF-A696-3E7A-9086-2A9953C909CD` |

Both full ZIP CRC checks passed (59 / 2,125 entries, including directories).
GTA has 16 recognized ARM64 Mach-O images; Winstom has 7; all report cryptid=0.
This flag and presence of LC_CODE_SIGNATURE do not establish valid code signing.
No keys, provisioning profiles or game assets were published or used for signing.

GTA bundle remains `com.macport.gtav`, minimum iOS 16.3. Its main executable
exactly matches the Phase 8 recorded hash. Archive hash differs; we have not
reconstructed the archive-level difference against the absent older IPA.
The packer now explicitly permits this second audited archive hash while still
requiring the same executable hash. It has no force/ignore-hash option.

Winstom bundle is `com.winstom.rp`, version 0.7.177/build 20261105.307, iOS 18.0.
Its main hash matches the **recorded** 0.7.171 hash, but `lmx.dylib` changes to
SHA `206037a1eaeea734e44886e050558421d1df965c8fd4bd3c078c317ca300906a`, UUID
`98E34282-7C4D-3E7B-81C2-11A9803C8108`. Do not reuse the 0.7.171 lmx addresses.

Machine-readable metadata is in `baselines/phase9-*.json`. No binary bytes are
included apart from selected instruction words necessary to reproduce assertions.

## Exact game-thread candidate

These are **unslid VAs** in the fingerprinted GTA5 image, not live pointers:

| Function | VA | Evidence |
| --- | --- | --- |
| CTheScripts::LaunchStartupScript | `0x100e33818` | Sandbox guard at +0x1c; call to program at +0x20 |
| MacportSandboxProgram | `0x10003b2d8` | ADRP/ADD constructs callback; RegisterCommand call at +0x34 |
| MacportSandboxNative | `0x10003b384` | Single tail branch to online update |
| MacportOnlineUpdate | `0x1000e16f8` | Calls jobs at `0x1000e66e0` |
| MacportJobsUpdate | `0x1000eb57c` | Stock 0xAE / 244-byte MPJ2 receive logic |
| rage::scrThread::RegisterCommand | `0x101fad4d4` | Symbol plus direct branch target |

This corrects v12 addresses; it does **not** prove a callback executes every frame
or establish OS thread identity, script context, safe instruction relocation, or
hook installation. Sandbox registration is conditional. No callback is patched.

## Sender provenance: stronger static evidence, authentication still open

1. `netPlayerMgrBase::OnNetEvent` (`0x102024914`) checks event type 4, searches its
   player list for a connection ID matching the engine event, and requires a local
   player. At `0x1020249a8` it writes source/destination player pointers to
   `ReceivedMessageData +0x10/+0x18`, then dispatches at `0x1020249b8`.
2. `netEventMgr::OnMessageReceived` (`0x10200a78c`) calls
   `HandlePackedEventsMsg` (`0x10200be0c`); that forwards the pointers into
   `ProcessPackedEvents` (`0x10200c158`) and `ProcessEventData` (`0x10200d9ec`).
   Event-handler table selection remains an indirect boundary to validate at runtime.
3. `CScriptedGameEvent::EventHandler` (`0x10191259c`) forwards source/destination
   references into `HandleEvent`. `Decide` (`0x101912c44`) forwards its first
   netPlayer reference as x3 to `CEventNetworkScriptEvent`'s constructor.
4. The group-event constructor (`0x1006ad850`) calls `netPlayer::IsValid`, checks
   the slot byte at player+0x21 against 0xff, and can normalize the payload slot.

Important exceptions: `netPlayerMgrBase::SendBuffer` also reaches the same
delegate dispatch for a local path. Observing a dispatch alone is not evidence of
remote receipt. `netConnectionManager::HandleReceivedPacket` has a call to
`P2pDecrypt` (`0x101cd5ea4`) but also a conditional path around it. The presence
of this function does not prove authentication for a particular packet/session.
Do not set `authenticated=1` from pointer existence, an IsValid result, a slot,
or the fact that a constructor ran.

`CNetworkSession::SetSessionState` is identified at `0x1017e9de4`; a trustworthy
session ID/generation, disconnect lifetime and migration invalidation are still
unbound. Carry copied validated identifiers/generation into the mailbox, never
retain a CNetGamePlayer pointer past its native callback lifetime.

## Newly found payload collision

At `0x1006ad8cc` the constructor reads payload byte +8; when it differs from the
valid engine player slot, `0x1006ad8dc` stores a 32-bit slot at payload +8. The
PRP3 v1 codec places its 64-bit session_id at precisely +8. Bare PRP3 therefore
**can be corrupted** if used directly as this native event payload.

This is a prospective integration defect, **not a claim that a live PRP3 packet
was previously sent or lost**. The Phase 8 implementation has no real emitter or
receiver bound at all; that absence is the demonstrated source-level delivery
blocker. Previous explanations that the jobs slot is simply self-asserted were
incomplete: it may have been normalized upstream. Its value alone still cannot
establish the required trusted delivery metadata.

New clean-room candidate envelope (`rp_v133_carrier.{h,c}`):

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | Experimental marker `PRP3EV01` |
| 8 | 4 | Native scratch slot; ignored for authorization |
| 12 | 4 | Must be zero |
| 16 | 40 | Unchanged Phase 5 PRP3 frame |

Encoder + strict receiver enqueue into the Phase 7 mailbox, preserving Phase 5–8
session/epoch, replay, proximity and consent gates. Other event namespaces, including
MPJ2, are not consumed or modified. The observer does not suppress native events.
There is no runtime route registration, sender attestation, or automatic socket fallback.
The experimental namespace and native event handling still require collision and
runtime compatibility checks before emission.

## Winstom 0.7.177 transport evidence

Dependency graph: GTA5 links lmx/wf/libgtacompat; lmx links wf/wrcrypto/libgtacompat;
libgtacompat links wf. Winstom adds 3 images, removes 12 from the original package,
changes 3 shared images, and matches libgtamsl exactly. It is not a drop-in dylib.

The updated fingerprint-guarded ObjC mapper resolves 26 classes / 368 class-linked
methods (previously recorded 357). LMXMessageProxy handler is now `0xe8a4`,
AVPanel handler `0xb6538`. WRTransport still exposes URLSession HTTP delegates,
and WRAccountSession exposes token lifecycle methods. lmx imports
NSURLSessionWebSocketMessage and includes webSocketTaskWithURL,
sendMessage:completionHandler: and receiveMessageWithCompletionHandler selectors.
Its diagnostics describe an authenticated independent on-foot transport and a
game-thread check. These are static hints toward a separate gameplay channel,
not proof of an active WebSocket, backend schema, accepted credentials, or RP sync.
No Winstom endpoints were contacted and no accounts/tokens were extracted.

## Validation and reproduction

- Local Windows Python 3.15: 32 AI Lab, 24 v133 Python, 9 packer tests passed.
- `inspect_v133_engine.py` verified 24 symbols, 13 direct branches and 13 selected
  instructions against the actual private executable; SHA/UUID mismatch is rejected.
- Actual audited IPA passed packer inspect-only; 80-byte load command fits
  12,168-byte padding without moving code.
- Seven C host test programs are configured for GCC/Clang ASan+UBSan: prior tests,
  new slot-mutation/isolation regression, and carrier+mailbox+gate synthetic endpoints.
  CI results and iPhoneOS artifact are recorded after the corresponding run below.
- The Mac workflow builds all four C modules as ARM64 objects and links them into
  the startup-only dylib, with Clang static analysis. Modules are dormant/unbound.
- No ThreadSanitizer or real-device memory/lifetime test has run.

Commands from repository root:

```sh
python ai-lab/projects/roleplay-ios/v133_interaction/tools/inspect_v133_engine.py PRIVATE.ipa --output evidence.json
python -m unittest discover -s ai-lab/tests -v
python -m unittest discover -s ai-lab/projects/roleplay-ios/v133_interaction/tests -v
python -m unittest discover -s ai-lab/projects/roleplay-ios/v133_interaction/ios -v
cd ai-lab/projects/roleplay-ios/v133_interaction
CC=gcc bash tools/run_host_tests.sh
CC=clang bash tools/run_host_tests.sh
```

Mach-O layout reference: [Apple loader.h](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h),
read 2026-11-16. Local disassembly used Capstone reporting 5.0.7; automated
instruction checks use Python struct only. Game conclusions above come from the
user's exact local binaries, not documentation examples.

## Remaining gates and next action

1. Re-sign the verified local unsigned diagnostic IPA (app and embedded dylibs),
   install on the available iPhone and
   return `Documents/PoliceRP-v13.3-Phase8.txt` plus any crash log. This is a boot
   probe only, with network and police flags staying zero.
2. Establish runtime callback context and remote connection authentication, then
   session generation/lifetime before implementing and enabling the native adapter.
3. A second iPhone is needed for actual A→B PRP3 tests; simulated endpoints cannot
   meet this acceptance criterion. Cuff/escort/jail remain disabled.

Rollback: reinstall the untouched original IPA; no original file is overwritten.
Revert this change for source rollback. No merge is performed.

CI for implementation commit `dafc8c55775542d2ecd29dde8570d92e2da7ff77`:
[Winstom RP source checks](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43797954365)
passed, including all seven C programs under GCC and Clang ASan/UBSan. The optional
private-IPA analysis job was skipped; the actual IPA checks above ran locally.
[First iOS build](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43797946300)
failed at linking because the inherited `-x objective-c` also applied to the newly
added object files. All C compilation and static-analysis commands before that
step completed. The follow-up removes the forced source language so `.m` is
compiled as Objective-C and `.o` files are linked as objects.

[macOS iPhoneOS build](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43798387409)
and [GCC/Clang sanitizer and Python checks](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43798392324)
passed on `d56278d7af125dad0a717fdcda9534db4821c092`. The artifact's ZIP digest matched GitHub.
The dylib is ARM64 iPhoneOS 16.3 (SDK 18.5), with only system dylib/framework imports.
The four ARM64 Clang analysis plists contain zero diagnostics.

Local `GTAV-v13.3-Phase9-Diagnostic-UNSIGNED.ipa` passed ZIP CRC. The only changed
original entry is GTA5: one 80-byte load command plus the two header counters,
with no code/section displacement. The other 58 entries, including the original
Info.plist with File Sharing enabled, match byte for byte. The added dylib matches
the CI artifact. Output SHA-256 `287dc4d6cb40cca713c26d983d044bbd257a3a3252e7c015f7345619c00c0a40`.
The package remains local and requires re-signing and a hardware startup test.
