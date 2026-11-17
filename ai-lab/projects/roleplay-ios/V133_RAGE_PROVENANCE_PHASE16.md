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

## One-shot external LLDB connection-candidate scanner

The source-only LLDB observer `observe_v133_lldb.py` now performs an optional bounded read when a hardware breakpoint hits OnNetEvent ENTRY on the exact iPhone build. From the stopped x0 and x2 registers, it scans event+0x3c, manager+0x128, netPlayer+0x18 and linked-list next+0x38, maximum 32 nodes. It reports only match/ambiguity/count/status, never raw addresses, gamer IDs or connection IDs. A match is **CANDIDATE ONLY**, not cryptographic authentication, RAGE membership, or session generation. The same script still refuses incorrect Mach-O UUID/opcode, and only takes a one-shot hardware breakpoint. No hardware run has yet validated this new memory scanner. The existing user device data belongs to E0/E1/E3 direct UDP, not RAGE provenance.

## A stronger engine-internal member/endpoint validation chain (STATIC)

CNetworkSession::GetSessionNetEndpointId at unslid VA 0x1018046e8 first
initializes the output to -1, obtains the active snSession pointer at
CNetworkSession+0x20, calls rlGamerInfo::GetGamerId and snSession::IsMember,
and rejects a non-member. For a member it obtains the peer ID via
GetPeerInfo/GetPeerId, calls snSession::GetPeerCxn and GetPeerEndpointId,
rejects a negative connection and invalid endpoint conditions, writes
the endpoint output and returns true. Sixteen additional machine
instructions from the exact supplied GTA5 executable are pinned.
This internal member check is NOT proof that rlGamerInfo corresponds
to the actual network packet sender. The missing link remains the
authenticated connection -> gamer info -> current session generation
association; no PoliceRP action is enabled.

## Phase 17 — Guarded OnNetEvent pre-dispatch probe

An exact original GTA5 disassembly confirms that unslid VA `0x1020249a8` is reached AFTER type-4 event selection, payload and active-player checks, sender connection-ID match, and local-player existence, immediately before `ReceivedMessageData::Dispatch`. The pending hardware one-shot breakpoint uses `x19` manager, `x20` event, `x9` selected sender and `x10` local netPlayer and scans at most 32 linked players. All reports redact addresses and connection identifiers, label matches CANDIDATE ONLY, and explicitly set authenticated RAGE sender/session flags to false. Seventeen uniquely new ARM64 guard instructions (total 84) were checked against the original exact SHA256-pinned executable. This is strictly static/host evidence, not a hardware capture or proven authenticated peer.

## Phase 17b — Selected netPlayer to peer ID without invoking engine code

Static disassembly of exact GTA5 identifies CNetGamePlayer::GetGamerInfo at unslid `0x1018d92e8`: read `[netPlayer+0xa0]` (`CPlayerInfo*`) and add `0x20` to reach `rlGamerInfo`. `rlGamerInfo::GetPeerInfo` is a no-op return of the same pointer; `rlPeerInfo::GetPeerId` at `0x101d64b9c` reads `rlGamerInfo+0x1d0`. LLDB now verifies the stopped player's vtable `+0x38` is the exact loaded native getter, then performs these reads only after a unique OnNetEvent pre-dispatch candidate. The report exposes **peer ID present** only, never IDs, gamer data or pointers. Mismatched native getter instructions, subclass/vtable layouts, missing CPlayerInfo and invalid IDs fail closed. Peer ID presence does not prove RAGE membership, transport authentication or current session generation. This remains untested on iPhone hardware.

## Phase 17c — netPlayer ↔ snSession peer mapping checker (SOURCE-ONLY)

Original unslid ARM64 confirms `CNetGamePlayer::GetGamerInfo` at `0x1018d92e8` reads player+0xa0 then adds 0x20, and `rlPeerInfo::GetPeerId` at `0x101d64b9c` reads gamer info+0x1d0. Independently, `snSession::GetPeerIdByCxn` at `0x1019dc870` scans remote peers at session+0xb930 (count+0xba30, maximum 32 in diagnostic) for the connection ID at peer+0 and returns peer ID at peer+0x1d8, or -1. The pure Python `check_v133_peer_session_map.py` compares these two sources with independently supplied *same-stop* pointers, requires a single connection match and no peer aliases, and never emits raw IDs or addresses. **It is not wired into the iPhone LLDB observer yet**: an independently verified current `snSession` pointer and generation are still unavailable at the selected OnNetEvent stop. A synthetic result is not authentication of sender, membership or RAGE transport. Adds 20 opcode pins to the prior 84, total 104 static exact-build words, and 7 negative/positive snapshot tests.
