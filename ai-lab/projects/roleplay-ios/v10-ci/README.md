# GTA5Port Roleplay — Native Host Bridge CI (v1.1)

**Scope:** This directory contains a small, reviewable Swift Foundation subset of the separately provided GTA5Port Roleplay v1.0 source, plus focused safety fixes and tests. It is **not** the complete GTA V iOS application or a working RP IPA.

## Included, testable components

- `RPFilePoseCodec`: decode 48-byte `RPF8` producer frames; reject invalid length, magic, version, CRC, and invalid coordinates.
- `RPFilePoseConsumer`: read stable frames, deduplicate sequence, reject stale files; polling is allowed only after server session establishment.
- `RPSessionGateV09`: distinguish TCP transport-ready from the `welcome` handshake.
- `RPFileDiscoveryV10` and `RPLivePoseProofV10`: bounded sandbox-only directory search, no symlink traversal, require **two increasing sequences** before reporting a live producer.
- `RPRemoteMailboxCodecV10`: create bounded 764-byte `RPR1` remote roster frames (up to 31 peers) with FNV-1a.
- `RPRemoteRosterV10`: reject remote packets before the `welcome` handshake, clear roster when disconnected.
- `RPRemoteMailboxWriterV10`: write atomically on a background queue, at most 4 Hz, using random per-process epoch.

## Verification

Linux with Swift: `swift build -c release && swift test -c release`.

GitHub Actions:
- `build-gta5port-rp-v10.yml`: Linux compilation and XCTest.
- `build-gta5port-rp-ios-arm64-v11.yml`: compile-only using Apple's iPhoneOS SDK and a macOS runner; produces **ARM64 object and Swift module**, not an IPA.

The source from which this was adapted was also locally checked by running `tests/run_v10.sh`, including Win64 ASI build and previous tests. Those Win64 binaries and game assets are **not included in this CI subset**.

## Not yet verified

Native GTA5Port iOS target integration, host Swift reading the exact Blink guest file on a device, ASI loading both directions, private server coordinates from a real device, remote PED visibility, iPhone runtime stability and IPA signing.

Do not claim that CI passing establishes any of these. Do not push proprietary game files, IPA, signing keys or auth tokens to this public repository.

## Next decisive device proof

Load a known `RPV08_pose.bin` written by ASI from **inside the real host app process** and observe two increasing sequence values; verify the host can read `RPV10_remote.bin` back from the guest before creating PEDs or enabling Online RP.
