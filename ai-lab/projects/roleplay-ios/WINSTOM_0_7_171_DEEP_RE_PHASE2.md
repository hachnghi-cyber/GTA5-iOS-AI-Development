# WINSTOM 0.7.171 — Deep static inspection (phase 2)

**Source:** User-supplied authorized IPA, SHA-256 `9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126`. Only read-only inspection; no game binary is committed. `zipfile.testzip()`: PASS (2,120 entries).

## New verified findings

1. **Native entry points:** `lmx.dylib` Mach-O `__objc_classname` includes `LMXMessageProxy`, `WRTransport`, `WRCoreTransportDelegate`, `WRAccountTransport`, `WRAccountSession`. `__objc_methname` includes `userContentController:didReceiveScriptMessage:`, `handleAction:body:request:`, `addScriptMessageHandler:name:`, `isRPOnly`, `setRpLaunchAuthorized:`. These are metadata strings, not linked implementation signatures.

2. **Interaction RPC from actual JS:** `LemexiLauncher/rp.js` sends native `avenor` messages `{action:'interact', target:<id>, kind:'greet'|'documents'}`. Updates via `Avenor.update(state)` consume `state.player`, `players`, `events` and `connectionError`. Target `distance <= 4` is *client-side filtering*, not proof of server distance validation.

3. **Police/native evidence:** In `lmx.dylib` `__cstring`: `work` 0x3bd901, `cuffed` 0x3bd906, `follow` 0x3bd90d, `police: put in a car %@` 0x3c0487, `(no free seat nearby)` 0x3c049f, animation dictionary `mp_arresting` 0x3c04b5. ARM64 `ADRP+ADD` references to `mp_arresting` at 0x135efc/0x135f00 and 0x1361ac/0x1361b0. A code reference is confirmed; real in-game arrest is **NOT** confirmed.

4. **Server-centered combat:** Diagnostic strings include `the server did not grant interactions`, `coreVitals not applied (malformed or not ours)`, `alive by the server: resurrected in place`, `too many shots not yet acknowledged`. Event keys: `coreVitals`, `coreLifeStates`, `coreFire`, `coreHit`, `coreMeleeHit`, `coreNativeLoss`, `coreShot`. Direct ARM64 string xrefs include `coreFire` 0x2c9ee4, `coreHit` 0x2c9f04, `coreMeleeHit` 0x2c9f20, `coreNativeLoss` 0x2c9f18.

5. **OneSync diagnostic code xrefs:** `[westrayn-onesync] createIn` is referenced at ARM64 0x356d54/0x356d58; `changeOwner` at 0x3576ec/0x3576f0; `unsafe hook/runtime pair` at 0x3578e8/0x3578ec. These VM addresses belong **only to this exact lmx Mach-O UUID** `003F682B-D578-332C-840E-7B789CD594DC`, before ASLR. They must NOT be copied as GTA v13 hook offsets.

6. **Additional hooking surface:** `lmx.dylib` section `__DATA_CONST,__interpose` is 0x30 bytes long (three 16-byte entries under the usual interpose-pair layout); target symbols not resolved.

7. **No bundled GTA data:** The IPA has **zero .rpf files**. This may require external game data; actual launch/update path not established.

## WPK header format — verified over all 2,031 files

All 2031 WPK files satisfy:
- ASCII magic bytes `WSPK0001` at 0..7.
- Little-endian uint64 at offset 8 == 262144.
- Little-endian uint64 at offset 16 = L (declared length).
- 16 raw bytes at 24..39 == the 32-hex-digit WPK basename.
- Exact file-size equality (2031/2031):

```
file_size = 80 + L + 16 * ceil(L / 262144)
```

1,954 WPK files have one block; 45 have two; 7 have three; remaining have more. The 16-byte per-block overhead is **consistent with** chunk authentication, but encryption algorithm, key, nonce and payload semantics are **NOT** established. No decryption performed.

## Boundaries, risks, next step

- Static evidence supports a distinct authenticated network/core and metadata for police/combat/vehicle/animation handling; cannot prove the features operate over GTA online or that OneSync is enabled.
- Original v13 IPA bytes are not available alongside Winstom for baseline binary diff, despite user describing it as derived from v13.
- No iPhone gameplay test or real network packet capture; no server protocol reconstruction; do not claim Police RP finished.
- Highest-value next step: compare SHA256+UUID of v13 GTA5 and the Winstom executable, trace `LMXMessageProxy` → `WRTransport` → authenticated `core*` state with runtime logs from a lawful test session. Prototype greet/documents with proper authority and then police cuff/escort.

**Validation:** Whole IPA SHA-256 rechecked; ZIP CRC test PASS. xrefs confirmed via LLVM disassembly. GitHub CI status on PR #16 was failure with inaccessible step logs; not claimed as passing.
