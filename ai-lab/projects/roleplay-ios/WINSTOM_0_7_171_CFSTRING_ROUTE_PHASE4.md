# Winstom 0.7.171 lmx CFString routes — phase 4 (STATIC ONLY)

Input: exact `lmx.dylib` SHA256 `dd2a00535b4df1118ce5f94bab1434c052233de4d9a04e3d153f5707d0404ec5`, UUID `003F682B-D578-332C-840E-7B789CD594DC`.

Procedure: parse `__DATA_CONST,__cfstring` 32-byte constant-object records, follow DYLD_CHAINED_PTR_64_OFFSET pointer at record+16 to `__TEXT,__cstring`, then locate ARM64 `ADRP + ADD` references to the **CFString record itself**. Identify containing function by Mach-O LC_FUNCTION_STARTS. This is stronger than scanning plain text; not a full decompilation or call graph.

| Constant | CFString virtual address | Function(s) containing code reference |
|---|---|---|
| `rp` | `0x3F31C8` | `0xB2358` (ObjC `AVPanel.userContentController:didReceiveScriptMessage:`) |
| `interact` | `0x3F3228` | `0xB2358`, `0x112214` |
| `target` | `0x3F32E8` | `0xB2358`, `0xBA738`, `0x112214`, other functions |
| `cuffed` | `0x3F42A8` | `0xBA738` |
| `follow` | `0x3F42C8` | `0xBA738` |
| `greet`, `documents`, `documents_accept`, `greet_accept` | `0x3F3248`, `0x3F3268`, `0x3F3288`, `0x3F32C8` | No **direct** ADRP+ADD CFString reference found; other access patterns still possible |

### New narrow technical finding

- There is a confirmed code reference from `AVPanel`'s script-message handler to the `rp` and `interact` CFString objects.
- `cuffed` and `follow` are referenced in the **same distinct function** starting at `0xBA738` in `lmx` (not merely adjacent strings).
- This supports targeting `AVPanel` dispatch plus `0xBA738` state processing for **further reverse engineering**, but does not prove the latter function writes state or that multiplayer arrest works.
- These virtual addresses belong only to this exact Winstom `lmx` build; do not copy them into v13.3 `GTA5`.

### Implications

Review `AVPanel` JS dictionary validation and native transport dispatch, then trace if `0xBA738` reads or writes state. For v13.3 source-only integration, preserve the existing security boundary: target/session/sender/distance obtained from authenticated engine metadata, not client `rp.js` parameters.

**NOT TESTED:** iOS gameplay, RPC packet schema, server-authorized arrest, real engine transport. No WSPK decryption performed.
