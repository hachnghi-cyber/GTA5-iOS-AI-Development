# v13.3 — Exact connection handle / P2P decrypt chain (read-only)

**Grounding:** User-provided GTAV-v13.3.ipa. GTA5 SHA256
`f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`,
Mach-O UUID `EB122C35-96F4-307F-91C3-A2255DD9C685`. Do not reuse
v13(4), v12 or Winstom offsets. This is original-machine-code analysis,
not source-level documentation and not an iOS runtime observation.

## Static call chain and lifecycle

- `netConnectionManager::CreateConnection` at `0x101CD0608`: a process-local
  allocation counter is loaded/incremented/stored at `0x101CD0794..079C`.
  Marker shift to upper 16 bits is visible at `0x101CD07C4`, combined
  with a selected low-half slot at `0x101CD0854`, and written to
  `Cxn+0x10` at `0x101CD0938`. This resembles a generation-tagged
  numeric handle, but high16 can wrap and is not a session/auth token.
- `CloseConnection(int,...)` at `0x101CD12F4` uses low16 for slot
  lookup at `0x101CD131C` and compares the complete candidate ID
  against `Cxn+0x10` at `0x101CD134C..1354`. That path rejects an
  ID differing in high bits.
- `netPlayerMgrBase::OnNetEvent` at `0x102024914` reads event+0x3c,
  walks its peer list, and compares full 32-bit values to
  `netPlayer+0x18` (`0x10202496C..974`). This is engine-internal
  event→peer matching; **not** proof of a cryptographically authenticated peer.
- `HandleReceivedPacket` at `0x101CD7690` calls `P2pDecrypt`
  (`0x101CD770C`), drops failure (`0x101CD7710`), and passes an
  output byte to `Unpack` (`0x101CD7794..77A8`). On the confirmed
  tunneling branch, `P2pDecrypt` stores 0 into that output byte
  (`0x101CD6128..612C`) and returns success (`0x101CD6130`).
  **Do not use the output byte as authenticated=true.**

The analyzer validates SHA256, UUID, and **26 exact ARM64 words**. Local
verification on the actual user IPA: PASS, six Python tests PASS (real
binary + 5 positive/negative assertions). GitHub CI has only synthetic
contracts because neither IPA nor proprietary GTA5 is stored in the repo.

## Hard blockers

Exact same-event source association on a development-signed iPhone, transport
connection cryptographic identity, game session membership/lifetime, and
disconnect/reconnect/migration behavior are still UNVERIFIED. Numeric high16
markers do not establish stable authentication after reuse/wrap/reconnect.
No Roleplay game-thread hook, native execution or two-device cuff can be enabled.

Reproduce locally (does not alter the IPA):

`python3 ai-lab/projects/roleplay-ios/v133_interaction/tools/audit_v133_connection_chain.py /path/to/GTAV-v13.3.ipa`

Next evidence experiment remains one real iPhone `script_event_handler --receive-context`
sample in a controlled stock online session with a cooperating peer; validate
the changed call-chain/source-association split first, then trace authoritative
session incarnation. No remote player interactions are enabled by this audit.
