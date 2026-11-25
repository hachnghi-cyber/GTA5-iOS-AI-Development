# GTA V iOS v13.3 Police RP — Phase 7 mailbox and authenticated sender blocker

Date: 2026-11-16. Changes are **clean-room source-only**, with regression tests on GitHub Actions; no GTA5 executable modifications.

## Why this step

- Source inspection of `police-rp/v1.4/Integration/prp_mailbox.{h,c}` found an existing v12 bounded 64-entry network→game-thread queue for **56-byte** packets.
- The separate v13.3 `PRP3` packet implemented in Phase 5 has **40 bytes**. Reusing v12's packet struct without a new serialization contract would be an ABI/wire mismatch.
- Winstom's `westrayn-core` diagnostics suggest a game-thread boundary, but this does not expose a verified sender callback in original v13.3.
- Phase 6 H5 device diagnostic sampled 8 Decide and 8 MPJ2 messages with `sender_auth=0`, `gameplay=0`. A hint/slot or pointer is not verified player identity.

## Implemented files

- `v133_interaction/include/rp_v133_mailbox.h` — 64-slot bounded C11 queue, 8 events per frame. Contains a trusted-transport metadata record and a fixed 40-byte `PRP3` copy.
- `v133_interaction/src/rp_v133_mailbox.c` — atomic_flag guarded nonblocking enqueue, bounded pop + game-thread drain; invalid/full/contended traffic drops; session/epoch replay rejected by the existing gate, and stored item buffers cleared on pop/reset.
- `v133_interaction/tests/test_v133_mailbox.c` — deterministic invalid input, missing transport auth, no game-thread processing, replay, capacity, frame budget, host migration, revoke-under-callback.
- `v133_interaction/tests/test_v133_mailbox_threads.c` — four concurrent pthread producers, 500 synthetic events each, while main thread pumps no more than eight per frame.
- `v133_interaction/tools/run_host_tests.sh` — local test command for all five C11 binaries.

**Trust boundary**: A copied `rp_v133_delivery` struct is not cryptographic evidence of anything. The integrator is responsible for proving that `transport_sender`, `transport_session`, `transport_epoch`, and `authenticated` originate from the actual GTA v13.3 native authenticated transport. No test fixture may set these values in a released gameplay path.

**No behavior mutation**: On receipt the gate calls `observe_interaction` only for greet/documents, never modifies another player's ped or enables cuff/escort. An invalid packet is rejected. We do not hook or modify `CNetGamePlayer` pointers without exact runtime evidence.

## GitHub Actions evidence

Run: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43786558200

- Python source analyzer / RP trace tests: **SUCCESS**.
- C11 v13.3 job: **SUCCESS** with GCC ASan/UBSan and Clang.
- Deterministic mailbox: **PASS** on both toolchains.
- Concurrent test: GCC accepted 1,120 queued events; Clang accepted 267. Both ran successfully. Differences reflect **bounded lossy queue** and scheduling, not measured iPhone network throughput. Four producers attempted 2,000 packets in each run; no transport performance claim is made.
- Existing P0/P1 gate, packet encode/decode and Python trace tests also passed in the same job.

## What is NOT established

- A verified RVA/hook to original v13.3 RAGE game-thread callback, network parser, or authenticated player sender.
- A trusted GTA network carrier for 40-byte PRP3 messages.
- Actual GTA Online handshake or native sender provenance; remote 4m authoritative distance validation.
- One greet A→B between real iPhones, or police cuff/escort gameplay.
- Signed IPA, SDK link, user-device crash testing, or Winstom WSPK decryption.
- ThreadSanitizer result. ASan+UBSan are not data-race detectors.

## Phase 8 admission criteria

1. Obtain **actual** game-thread callback address and calling convention for the original v13.3 `GTA5` fingerprint, with safe lifetime proof.
2. Identify transport code that gives authenticated sender/session metadata (not `slot_hint`, `MPJ2`, raw socket, or client JSON).
3. Instrument a **read-only** event trace, separate untrusted logs from trusted engine attestations, and correlate identical nonce/session/sender between two user-controlled devices.
4. Only then implement opt-in, host-authoritative cuff/escort and rollback, without modifying uninvolved Online players.

Current deliverable: source-only mailbox and tested **multi-threaded simulation**, not a playable Police RP IPA.
