# V13 — Loaded Mach-O identity from dyld (source-only)

Date: 2026-11-13. Scope: draft PR #14 stacked on draft PR #12. No GTA V commercial content in this change.

## Verified source and threat boundary

The existing gate compared the expected v13 `GTA5` and `libgtacompat.dylib` UUIDs but depended on two loader-verification flags supplied by an undefined adapter. This change implements a *possible* on-device, read-only source for image metadata: `rp_v13_dyld_collect_identity()` walks dyld loaded images and parses native ARM64 Mach-O `LC_UUID` in a bounded manner. The portable `rp_v13_collect_image_candidates()` is intentionally **not trusted**: it always leaves both `*_verified_by_loader` flags at zero. Only the Apple implementation marks those flags, after exact UUID comparison succeeds. Even then, it does not authenticate code signing or session network origin.

Candidate selection requires one `/GTAV.app/GTA5` executable (MH_EXECUTE) and one `/GTAV.app/Frameworks/libgtacompat.dylib` (MH_DYLIB) sharing the same absolute app path prefix. Duplicates, missing files, bad CPU/filetype, oversized/misaligned/truncated Mach-O commands, duplicate/missing LC_UUID and mismatched expected UUIDs fail closed.

### Test evidence
Environment: Debian GCC 14.2.0 and Clang 17.0.0, 2026-11-13T15:37:21Z.

- Portable parser GCC: **46 assertions PASS**, 12,000 bounded deterministic header mutations.
- Portable parser Clang ASan+UBSan: **46 assertions PASS**, 12,000 mutations.
- Synthetic Apple provider using stub `mach-o/dyld.h`, GCC: **14 assertions PASS**.
- Synthetic Apple provider, Clang ASan+UBSan: **14 assertions PASS**.
- Each compiler configuration covers 60 assertions total. No sanitizer error appeared in exercised paths.
- Exact source Git blob SHA-1 values were checked against local files used in these tests.

Source-only C test commands and stdout are recorded in host log: `RP_V13_DYLD_HOST_TESTS_20261113.log` (distributed separately, not a device test).

## Reproduce without IPA
```bash
cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
  police-rp/v13/rp_v13_identity_gate.c \
  police-rp/v13/rp_v13_dyld_identity.c \
  police-rp/v13/test_rp_v13_dyld_identity.c -o /tmp/v13_dyld_parser
/tmp/v13_dyld_parser

cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
  -D__APPLE__ -Ipolice-rp/v13/tests/fixtures -Ipolice-rp/v13 \
  police-rp/v13/rp_v13_identity_gate.c \
  police-rp/v13/rp_v13_dyld_identity.c \
  police-rp/v13/tests/test_rp_v13_dyld_shim.c -o /tmp/v13_dyld_fake
/tmp/v13_dyld_fake
```
CI workflow includes equivalent Clang ASan/UBSan commands and, when macOS runners become available, an unsigned Apple iPhoneOS ARM64 dylib compile with exported `_rp_v13_dyld_collect_identity`. That Apple compile **has not been confirmed**.

## Engineering limitations and risks

1. Apple documents that iterating `_dyld_image_count` and associated image queries is **not thread-safe** during image load/unload. Only call this at a controlled lifecycle point; investigate using the dyld callback/registration API for stronger guarantees before any production hook.
2. Apple SDK compilation and actual dyld behavior on iOS 16.3+/v13 are **not validated**. Fake Apple headers on Linux are not an iPhoneOS build.
3. The in-memory Mach-O header's load-command bound is derived from dyld's mapped header; it is not an arbitrary-pointer-safe memory probe. This API must never accept player-supplied memory pointers.
4. A UUID identifies a build, not a cryptographic code-signing verification. No measured code hash, approved entitlements or genuine peer/session authentication is provided.
5. Hardcoded `GTAV.app` paths and v13 UUIDs are intentionally version-scoped. If the actual running app is renamed or re-signed with changed binaries, fail closed and require a new verified baseline.
6. No RAGE game-frame callback, GTA Online transport carrier, native arrest, sync, or two-iPhone gameplay test has been performed.

## Sources

- Apple XNU Mach-O `loader.h`: https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h
- Apple dyld API (open-source header): https://github.com/opensource-apple/dyld/blob/master/include/mach-o/dyld.h

## Next action and rollback

First restore GitHub runner allocation and run actual Apple SDK build plus host CI. Then inspect genuine dyld image evidence on exact v13 iPhone, and independently verify GTA game-thread and authenticated network callback semantics. Do not treat loader UUID matching as permission for gameplay. To roll back, revert these source/test/workflow entries from the PR; do not touch main, PR #12 or the IPA.
