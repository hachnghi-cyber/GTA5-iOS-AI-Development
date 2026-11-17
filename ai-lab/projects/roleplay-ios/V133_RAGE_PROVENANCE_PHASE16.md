# RAGE sender/session provenance: exact-build hard boundary (Phase 16)

Status: **STATIC+HOST TESTS; NOT LIVE INSTRUMENTED.** No native hook,
game action, packet acceptance, player identity or RAGE-authentication is
claimed here. This code is deliberately not linked into a game installer.

## Direct static evidence, GTA5 SHA256 f4b5e98e...dca2
Source executable: user-owned \`GTAV-v13.3.ipa\`, Mach-O UUID
\`EB122C35-96F4-307F-91C3-A2255DD9C685\`. Addresses below are
**unslid**; never use them as runtime pointers without dyld slide.

- \`netPlayerMgrBase::OnNetEvent\` @ \`0x102024914\`: \`ldr w10,[x20,#0x3c]\`
  at \`0x102024954\`; \`ldr w11,[x9,#0x18]\` at \`0x10202496c\`,
  \`cmp w11,w10\` at \`0x102024970\`, and \`stp x9,x10,[sp,#0x10]\`
  at \`0x1020249a8\`. Remote-event path looks up a **connection ID**
  and forwards sender/local pointers, but does not independently attest
  cryptographic origin, session membership or reconnect generation.
- \`netPlayerMgrBase::SendBuffer\` @ \`0x101ffee34\` also calls the
  same \`atDelegator<ReceivedMessageData>::Dispatch\` at \`0x101ffeecc\`
  on a **locally initiated** path. Observing that delegate alone is not
  proof of remote delivery.
- \`snSession::GetPeerCxn\` @ \`0x1019d62d4\` compares the supplied
  64-bit peer ID against \`rlPeerInfo::GetPeerId\`, returns a 32-bit
  connection value, and uses \`-1\` when not found.
- \`snSession::GetPeerEndpointId\` @ \`0x1019d30d4\` follows the same
  peer-ID lookup but reads an endpoint ID. **Do not assume endpoint equals
  connection**; it is an independent field.
- \`snSession::GetSessionId\` @ \`0x1019d255c\` adds \`0xa8\` to the
  session pointer and tail-calls \`rlSession::GetId\` @ \`0x101d6b2b8\`;
  the latter reads a 64-bit value at \`rlSession + 0x520\`. The ID is
  not a generation counter.
- \`netConnectionManager::HandleReceivedPacket\` @ \`0x101cd7690\`
  branches around \`P2pDecrypt\` in some cases and passes a separate
  out-byte to \`Unpack\`. Decrypt invocation and presence of a
  \`netPlayer\` pointer do **not** demonstrate an authenticated channel.

## New source-only defensive observer

\`rp_v133_rage_provenance.{h,c}\` is a **serialized read-only correlator**.
It requires the future trusted callback adapter to supply the exact current
session ID, a locally minted generation (increment on join/leave/migrate),
remote OnNetEvent origin, independently read peer ID/connection/endpoint,
valid current netPlayer and session membership plus time of observation.

It rejects SendBuffer/local path, invalid session connection -1, mismatch
between event/peer/netPlayer connection IDs, missing membership, stale (>250ms)
or future samples, mismatched generations, and peer ID↔connection/slot/endpoint
collisions. A remap or non-monotonic clock quarantines the current scope.
It does not store raw engine pointers, session key bytes, addresses or gamer IDs.

**A passing candidate is NEVER AUTHENTICATED.** The module cannot emit
\`rp_v133_delivery.authenticated=1\`; Police dispatch stays unreachable.
Passing a synthetic sample in a unit test does not verify native callbacks.

## Hardware acceptance gates still open

1. Identify the actual read-only callback point with reliable remote-vs-local
   path and reproduce with the exact iPhone binary; validate attach/detach,
   OS/script thread and binary fingerprint. Do not patch undocumented ABI.
2. Correlate connection ID, \`netPlayer\`, \`snSession\` peer ID,
   \`GetPeerCxn\`, \`GetPeerEndpointId\`, \`IsMember\` and
   \`GetSessionId\` in one native lifetime without carrying pointers.
3. Prove connection belongs to authenticated RAGE transport using observed
   provenance across decrypt/dispatch. It is currently **UNVERIFIED**.
4. Force disconnect/rejoin and session migration on at least two devices.
   Verify generation invalidates all stale receipts, bindings, custody.
5. Only after that: construct game-thread-safe and consent-gated police
   operation adapter, with independent visual and peer confirmation.

Host CI: compile with GCC and Clang, ASan/UBSan, source-only fixtures. Exact
ARM64 disassembly above is read-only local evidence from the fingerprinted
private executable, not published in GitHub.
