# GTA5Port RP v1.0 - CI bootstrap (subset)

This directory intentionally contains **only the pose 48-byte codec / pose consumer and welcome handshake gate**, copied from the locally tested GTA5Port Roleplay Bridge v1.0 source (minor comment cleanup). It is NOT the complete Swift host, GTA V app, RAGE Engine, private RP server, or a game IPA.

Run on Linux: `swift test -c release`.
Tests: 48-byte pose decode and FNV1a verification, corrupt CRC rejection, handshake guard, pose sequence deduplication.

Source of truth for complete v1.0 remains the separately handed-off GTA5Port-RP-Bridge-v1.0 package. This GitHub CI seed has a deliberately small, verifiable scope. No proprietary game binary or signing credentials are committed.

**Unverified:** iOS SDK build, ASI loader, iPhone runtime, two-phone networking, remote PEDs, signed IPA.
