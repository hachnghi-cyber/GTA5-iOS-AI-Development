# Phase 12 — Cached native-invocation receipt recovery (diagnostic only)

Target: user-provided GTA V iOS v13.3, pinned UUID/SHA unchanged. Original GTA5 and IPA untouched.

## Actual code changes
- Receiver caches the sequence, nonce, and time ONLY after a game-thread native adapter returns success. Cache lives on UDP worker, bounded to 12 seconds, checked against HMAC-verified committed action.
- Sender, after verified queue ACK, retries the EXACT originally signed diagnostic PING up to four times within an existing bounded receive window if native report is absent. Receiver classifies duplicate but does not enqueue a second action; it sends cached native receipt again.
- Host regression drops FIRST native receipt intentionally using compile-time `RBP_TEST_DROP_INITIAL_NATIVE_REPORT`; never build this flag for iPhoneOS. Test requires recovery and proves native mock counters did not increase.
- New atomic sender status flag is read only in host tests to confirm receipt; no unsafe read of receiver worker state.
- New `SOURCE_CHECKPOINT=phase12-e3-receipt-retry` runtime marker; log evaluator rejects stale Phase11 and detects duplicate native invocations.
- The device-log evaluator permits a verified retry report in place of first send, but still requires every other same-sequence condition and separately reported manual screen evidence.

## Verification
- Original user IPA SHA256 baseline unchanged.
- Local Clang and GCC full host test scripts: PASS (49/49 Python tests each, C ASan/UBSan, shared mock SHV E0/1/3, 2 independent host processes with UDP, ARM64 freestanding Mach-O objects).
- Both compilers: injected first native-report loss recovered with duplicate packet/ACK, native invoked exactly once.
- Production-style host E3 shared library does NOT contain injected loss marker. No iPhoneOS SDK link in local Linux; ld64.lld explicitly rejects iOS platform.
- iPhoneOS macOS runner 43923116112 was CANCELLED before linking; no dylib produced. No hardware E0/E1/E3, no signed IPA, no RAGE sender/session ownership or cross-iPhone PoliceRP.

**Important:** This direct UDP channel is an isolated, opt-in test, not RAGE multiplayer replication. A native report proves at most the adapter call path in a genuine device session, not visible HUD or changes to other players.

## Apple conditional-branch syntax gate

Linux host CI now syntax-checks E0/E1/E3 Apple branches using explicitly fake mach-o/mach/CommonCrypto declarations with both Clang and GCC. This is NOT an iPhoneOS SDK link, signed dylib, or device test. The original IPA already has NSLocalNetworkUsageDescription, NSBonjourServices (_gtavmp._udp), and UIFileSharingEnabled=true; no Info.plist modifications needed.
