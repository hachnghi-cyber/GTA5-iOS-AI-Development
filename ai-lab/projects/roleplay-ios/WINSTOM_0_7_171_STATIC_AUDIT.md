# WINSTOM 0.7.171 — Reverse Engineering evidence (STATIC ONLY)

> Scope: User-supplied Winstom-0.7.171.ipa, inspected 2026-11-16. No iPhone test, no source-code recovery, no packet capture. This repository does NOT contain the IPA or any extracted executable.

## 1. Verified input and app identity

| Evidence | Value |
|---|---|
| IPA length | 243580061 bytes |
| IPA SHA-256 | \`9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126\` |
| ZIP file entries | 2120 |
| ZIP total uncompressed | 305139496 bytes |
| CFBundleIdentifier | \`com.winstom.rp\` |
| CFBundleName | \`WINSTOM\` |
| CFBundleShortVersionString | \`0.7.171\` |
| CFBundleVersion | \`20261105.301\` |
| MinimumOSVersion | \`18.0\` |
| Executable | \`Payload/GTAV.app/GTA5\` |
| Architecture | Mach-O ARM64 |
| GTA5 LC_UUID | \`048DCEFF-A696-3E7A-9086-2A9953C909CD\` |
| GTA5 SHA-256 | \`df7427d0e19271b1b49f0132d8d6d3be0dd65a04b4c86991749b75ed9b15f0e4\` |
| GTA5 LC_ENCRYPTION_INFO_64 | \`cryptid=0\` |

Methods: Python zipfile, plistlib, SHA256, llvm-objdump --macho --private-headers, static strings review, direct HTML/JS review. All seven recognized Mach-O images report cryptid=0; this **does not** say resources or private content are decrypted.

## 2. ARM64 library inventory (exact UUID)

| Image | Bytes | UUID | cryptid |
|---|---:|---|---:|
| GTA5 | 59760048 | 048DCEFF-A696-3E7A-9086-2A9953C909CD | 0 |
| libgtacompat.dylib | 2941920 | A2BCB218-62D0-3A5C-91CF-679FFD93FBDD | 0 |
| libgtamsl.dylib | 2677248 | ACBA3FA5-1CEE-30E6-8C74-9FB4CCA96D1B | 0 |
| lmx.dylib | 4384624 | 003F682B-D578-332C-840E-7B789CD594DC | 0 |
| wf.dylib | 70224 | DF0BC8B9-42A9-34C3-8013-5F1DA23C9A38 | 0 |
| winemetal.dylib | 26660480 | E07434F7-F40D-336B-81D7-7B5C38A066B5 | 0 |
| wrcrypto.dylib | 97216 | 07D3AD81-D018-3270-837D-6D18DE5E4519 | 0 |

Load-command dependency relationships (direct evidence):
- \`GTA5\` -> \`libgtacompat\`, \`lmx\`, \`wf\`.
- \`lmx\` -> \`libgtacompat\`, \`wrcrypto\`, \`wf\`.
- \`libgtacompat\` -> \`wf\`.
- \`wf\` -> \`wrcrypto\`.
- \`lmx\` imports Apple WebKit/Network/Security frameworks, while \`wrcrypto\` imports CryptoKit.

## 3. Direct evidence of RP in JavaScript and native strings

\`LemexiLauncher/rp.html\` + \`rp.js\` are actual app resources. The RP view:
- Uses \`window.webkit.messageHandlers.avenor.postMessage\` as a JavaScript-to-native bridge.
- Receives \`Avenor.update(state)\`; uses character name, ID, balance, nearby player list, events, and connection error.
- Filters target players to distance <= 4 meters.
- Exposes \`interact\` actions: \`greet\` and \`documents\` with target player ID.
- Offers an appearance-editor action.
- Does **not** contain a cuff/escort/arrest action in these two inspected files; not proof they do not exist elsewhere.

\`lmx.dylib\` static diagnostic literals indicate:
- \`[westrayn-core] authenticated; independent on-foot transport\`
- \`[westrayn-core] remote entity created\`, \`handshake from id\`, \`socket closed\`, \`reconnect\`
- \`[westrayn-onesync] createIn\`, \`syncIn\`, \`cloneOut\`, \`changeOwner\`
- A guard: \`[westrayn-onesync] unsafe hook/runtime pair; startup stopped before probe writes\`
- \`[westrayn-stance]\`, \`[westrayn-outfit]\`, \`[westrayn-anim]\` diagnostics.
- Symbol/import references include \`NSURLSessionWebSocketMessage\` and \`_socket\`.

**Interpretation, not validated gameplay:** this looks like a Westrayn native multiplayer layer with its own on-foot transport, entity copies, outfit/animation syncing, and experimental OneSync-related hook path. The strings alone **cannot prove** which path is active or whether engine-level ownership migration is functional.

## 4. WestraynUI packs and contents not recovered

- 2031 files in \`Payload/GTAV.app/WestraynUI/\`, total 197797438 uncompressed bytes.
- All 2031 have 8-byte magic \`WSPK0001\`.
- \`wrcrypto.dylib\` contains \`WinstomSecurePack\` / \`SecurePackReader\` identifiers.
- No WPK payload decryption, unpacking, or reconstruction of content was performed.
- \`news-data.js\` describes an electrician job and in-game phone features, but news text is **not runtime verification**.

## 5. Engineering implications for GTA V iOS v13 Police RP

1. **High-priority seam:** \`avenor\` WebKit bridge -> native \`lmx\` -> RP action dispatch -> authenticated transport / state events. Trace callsites and message schemas before writing hooks.
2. **Network authority:** investigate identity/session/ownership handling; the \`onesync\` logs include owner migration but do not establish support.
3. **Safety gate:** \`unsafe hook/runtime pair\` is evidence that version-specific hook compatibility is checked; do not transplant offsets across different GTA5 UUIDs.
4. **Prototype:** implement greet/documents in existing GTA V iOS v13 RP adapter using independent code before police cuff/escort; test two iPhones to verify state synchronizes.
5. **Baseline diff blocked:** Original v13 IPA bytes are absent from the currently accessible analysis context. No function-level or binary diff against v13 has been performed.

## 6. Test evidence / restrictions

- VERIFIED: IPA ZIP listing, Info.plist inspection, seven Mach-O headers, per-binary SHA256/UUID, native diagnostics and included JS action model.
- NOT VERIFIED: OneSync actually enabled, working server authorization, RP backend protocol, native callgraph, phone/electrician gameplay, police detention, iPhone tests, binary compatibility with a particular v13 build.
- This report includes metadata and a few diagnostic strings only; no game data, IPs, credentials or IPA binary.
