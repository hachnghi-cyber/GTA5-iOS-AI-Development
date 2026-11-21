# WINSTOM 0.7.171 → GTA V iOS v13.3 — Phase 5 native dispatch and RP wire

**Scope:** Read-only ARM64 metadata / selector xrefs in user-supplied Winstom IPA; independently implemented C11 source-only interaction protocol. No IPA/game assets or proprietary binaries in this repository.

## Fingerprinted inputs

- Winstom IPA SHA256 `9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126`.
- Winstom `lmx.dylib` UUID `003F682B-D578-332C-840E-7B789CD594DC`, SHA256 `dd2a00535b4df1118ce5f94bab1434c052233de4d9a04e3d153f5707d0404ec5`.
- Original v13.3 `GTA5` UUID `EB122C35-96F4-307F-91C3-A2255DD9C685` with distinct executable hash, as in Phase 3.

## New high-confidence static findings

1. `LMXMessageProxy.userContentController:didReceiveScriptMessage:` IMP `0xe888`: the code first sends selector `target` (selref `0x409028`) and then invokes `userContentController:didReceiveScriptMessage:` (selref `0x409030`) on the returned receiver, using original WebKit handler arguments. This is a forwarding bridge, **not by itself an RP authentication gate**.
2. `AVPanel.userContentController:didReceiveScriptMessage:` IMP `0xb2358` compares a value with CFString `interact` at ARM64 `0xb8784`, using selector `isEqual:` (selref `0x408e48`). This confirms an action dispatch branch.
3. Independent function starting `0xba738` reads CFString `cuffed` at `0xbc2ec` and CFString `follow` at `0xbc63c` and `0xbc6b0` by `objectForKeyedSubscript:` (selref `0x408f50`). These are **reads of dictionary state**, not evidence that this function cuffs a real Online player or changes network ownership.
4. Original v13.3 and Winstom `GTA5` contain text references to `MacportOnlineUpdate`, `MacportJobSend`, `CScriptedGameEvent`, and `NetworkPlayerMgr`. Strings alone do not establish usable authenticated sender callbacks.

These addresses are virtual addresses **only in the exact Winstom lmx UUID**, not v13.3 hook offsets. No WSPK decryption, credentials or gameplay memory patches were involved.

## Source-only 40-byte diagnostic packet

- `rp_v133_wire.h/.c`: little-endian `PRP3` version 1; 8-byte header and 4 × uint64 fields (session, receiver, peer epoch, nonce).
- Reject unknown version, kind, magic, reserved flags, invalid IDs, zero nonce, short/long buffers.
- Sender identity and channel authentication are **never taken from the packet**, always from independent transport metadata supplied by a trusted engine adapter.
- `rp_v133_wire_deliver()` parses and then calls the existing fail-closed gate; it does not implement a carrier or native engine hook.
- Two-endpoint source-only simulator now carries byte packets and checks replay, malformed data, unauthenticated sender metadata, wrong sender, session epoch, proximity, and consent.

## Reproduced host evidence

Local 2026-11-16:
```
CC=gcc tools/run_host_tests.sh   PASS (3 test binaries, ASan + UBSan)
CC=clang tools/run_host_tests.sh PASS (3 test binaries, ASan + UBSan)
clang --target=arm64-apple-ios17.0 -ffreestanding -c rp_v133_wire.c PASS (Mach-O ARM64 object)
clang --target=arm64-apple-ios17.0 -ffreestanding -c rp_v133_interact_gate.c PASS (Mach-O ARM64 object)
```

**Not verified:** GitHub Actions green, native callback/game-thread binding, actual GTA Online packets, authenticated sender source, two-iPhone A→B interaction, RP cuff/escort, signed or playable IPA. GitHub Actions previously failed rapidly and job logs returned BlobNotFound, so a root cause is not established.

## Next P0 task

Locate a **real v13.3 engine-owned callback** delivering session ID, sender ID, authentication result and game thread context. Then test a read-only greet event between two authorized RP clients and correlate the same session/nonce. Until that evidence exists, no automatic real-player cuff, remote ped modification, or release.