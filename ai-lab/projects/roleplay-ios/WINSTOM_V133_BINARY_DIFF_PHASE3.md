# Winstom 0.7.171 vs. original GTA V iOS v13.3 — PHASE 3 (read-only)

Date: 2026-11-16. **Input files verified directly**; do not infer game behavior from a compiled binary. No IPA is committed to this repository.

## Exact input baselines

| Property | Original v13.3 | Winstom |
|---|---|---|
| Filename | `GTAV-v13.3.ipa` | `Winstom-0.7.171.ipa` |
| IPA size | 58,346,051 bytes | 243,580,061 bytes |
| IPA SHA256 | `7a5e23358e4a72a03322fe016ea08adde1ee6189b0c66f86e656a48649057b89` | `9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126` |
| Bundle ID | `com.macport.gtav` | `com.winstom.rp` |
| iOS min | 16.3 | 18.0 |
| GTA5 UUID | `EB122C35-96F4-307F-91C3-A2255DD9C685` | `048DCEFF-A696-3E7A-9086-2A9953C909CD` |
| GTA5 SHA256 | `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc` | `df7427d0e19271b1b49f0132d8d6d3be0dd65a04b4c86991749b75ed9b15f0e4` |
| Mach-O images | 16 | 7 |

## Verified linked dependency graph (LC_LOAD_DYLIB)

- GTA5 Winstom directly adds `@rpath/lmx.dylib` and `@rpath/wf.dylib` on top of the original v13.3 linked system/game compatibility dependencies.
- Winstom `libgtacompat.dylib` additionally links `@rpath/wf.dylib`.
- Winstom `lmx.dylib` depends on `libgtacompat`, `wf`, `wrcrypto`, and Apple WebKit/Network/Security frameworks (from prior direct linked inventory).
- Winstom does **not** package v13.3 Menyoo, ScriptHookV, Mono or d3d11/dxgi dylibs. Do not assume all mods survive direct binary replacement.
- `libgtamsl.dylib` is **bit-identical** across the two IPA: SHA256 `a23bc3e5dc6615a0457a97daad2319d782af99c8b01dc13df16fc732b6140b3b`.
- `winemetal.dylib` has the **same byte length** but a different SHA256/UUID; not interchangeable.
- Winstom `GTA5` 59,760,048 B vs v13.3 59,798,512 B; `__TEXT,__text` 37,004,984 B vs 37,026,480 B. Different UUID, section hash and layout.
- Both `GTA5` images expose `cryptid=0` in LC_ENCRYPTION_INFO_64; separate protected assets may exist.

## Objective-C implementation mapping: Winstom lmx.dylib

`lmx` SHA256 `dd2a00535b4df1118ce5f94bab1434c052233de4d9a04e3d153f5707d0404ec5`, UUID `003F682B-D578-332C-840E-7B789CD594DC`.

Read-only Mach-O classlist/relative-method parser resolves 26 ObjC class entries with 357 directly class-linked methods (437 method entries across all `__objc_methlist` lists). Selected method implementation VM addresses **in Winstom lmx only**, before ASLR:

| Class | Selector | lmx IMP VA |
|---|---|---|
| LMXMessageProxy | `userContentController:didReceiveScriptMessage:` | `0xe888` |
| LMXLauncher | `userContentController:didReceiveScriptMessage:` | `0x11124` |
| LMXLauncher | `handleAction:body:request:` | `0x11ab8` |
| AVPanel | `userContentController:didReceiveScriptMessage:` | `0xb2358` |
| AVCreator | `userContentController:didReceiveScriptMessage:` | `0x3498bc` |
| WRCharacterSelector | `userContentController:didReceiveScriptMessage:` | `0x34fe74` |

These are resolved **IMP locations** from Objective-C metadata, not just string matches. However, ownership of the gameplay `avenor` message routing among these classes still needs call-graph verification, and none is a valid v13.3 hook address.

## Practical development result and blockers

- v13.3 clean-room `v133_interaction` source from this PR remains the only developed gate in scope. Re-ran GCC+ASan/UBSan and Clang Linux host tests: both **PASS** (`denied=19, emitted=6, observed=4`), synthetic input only.
- Winstom `westrayn-core` and `westrayn-onesync` diagnostic strings are static proof of compiled diagnostics, **not** proof of active OneSync/cuff/vehicle state sync.
- v13.3 game thread callback and authenticated sender metadata: **NOT VERIFIED**. A source-only gate cannot itself deliver packets to another iPhone.
- Needed next: capture real runtime authenticated transport metadata, then test one read-only `greet` A→B event across two iPhones before activating police/arrest actions.
- GitHub Actions on prior PR commits failed with unavailable job logs; no Actions success is claimed.
