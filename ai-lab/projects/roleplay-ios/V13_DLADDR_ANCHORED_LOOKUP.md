# RP v13 — Anchored dladdr image lookup, source-only research

Date: 2026-11-13 UTC. Scope: PR #14 stacked on draft PR #12. **No GTA IPA, no native engine hook or proprietary game assets.**

## Verified issue and minimal fix

Prior source `rp_v13_dyld_collect_identity()` iterated `_dyld_image_count()` and queried image headers/names by indices. Apple documents that enumerating images this way is not thread-safe when another thread loads/unloads an image. See: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dyld.3.html.

The new source-only alternative `rp_v13_dladdr_collect_identity(gta5_anchor, compat_anchor, out)` calls `dladdr()` for TWO independently provided code addresses instead of enumerating a mutable array of images. Apple states that `dladdr` resolves an address to a loaded image; dyld's header recommends it instead of index enumeration for many use cases. See: https://github.com/opensource-apple/dyld/blob/master/include/mach-o/dyld.h and https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dladdr.3.html.

**Caught by actual initial failing regression:** an earlier draft passed the anchors into the order-independent `rp_v13_collect_image_candidates` and therefore accepted swapped `compat_anchor`/ `gta5_anchor`. The first GCC mock test aborted on the reversed-anchor assertion. Corrected by requiring each resolved image name to match the proper *ordered* suffix BEFORE calling the candidate collector. Then the exact corrected source passed GCC and Clang sanitizers.

## Safety contract

- Requires non-null, distinct, **stable/pinned real code addresses** for the exact v13 executable and compatibility module, obtained from a separately authenticated native adapter. These anchors MUST NOT be read from raw UDP, untrusted game packets, INI, arbitrary file offsets, or stale images.
- Rejects missing dladdr result, null loaded image paths/headers, unsupported Mach-O magic, oversized/absent load command size, wrong image path role, different bundle root, invalid CPU/filetype, malformed/duplicate LC_UUID and mismatch with BOTH pinned v13 UUIDs.
- Outputs a zeroed `RP_V13_IdentityEvidence` on any failure; flags are set only if both resolved images pass the exact baseline check.
- **No code execution through supplied anchors.** No offsets, networking, code signing, jailbreak/entitlement bypass or IPA modification.
- This is metadata verification, NOT cryptographic signature verification. Incorrect/malicious caller-supplied anchor provenance can invalidate trust. Memory-mapped header size still derives from a dyld-validated Mach-O image; it is not safe for arbitrary unmapped pointers.
- A loaded module must not be concurrently unloaded while reading its header/name. `dladdr` avoids the image-index enumeration race but does **not** magically pin the lifetime of returned image pointers.
- No source in this PR locates valid v13 GTA game-frame or transport anchors yet. Thus this provider is **not integrated into gameplay**.

## Local reproducible tests (not GitHub CI)

Toolchains on Linux: GCC 14.2.0 and Clang 17.0.0.

```sh
# run from police-rp/v13
cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
 rp_v13_dladdr_identity.c test_rp_v13_dladdr_portable.c -o /tmp/v13_dladdr_portable
/tmp/v13_dladdr_portable

cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic -D__APPLE__ \
 -Itests/fixtures -I. rp_v13_identity_gate.c \
 rp_v13_dyld_identity.c rp_v13_dladdr_identity.c \
 tests/test_rp_v13_dladdr_identity.c -o /tmp/v13_dladdr_stub
/tmp/v13_dladdr_stub

clang -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic \
 -fno-omit-frame-pointer -fsanitize=address,undefined \
 -fno-sanitize-recover=all -D__APPLE__ \
 -Itests/fixtures -I. rp_v13_identity_gate.c \
 rp_v13_dyld_identity.c rp_v13_dladdr_identity.c \
 tests/test_rp_v13_dladdr_identity.c -o /tmp/v13_dladdr_san
ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 /tmp/v13_dladdr_san
```

Recorded observed results (working container):
- Non-Apple fail-closed GCC: **5 checks PASS**.
- Host fake Apple dladdr + dyld ABI GCC: **32 assertions PASS**.
- Host fake Apple dladdr + dyld ABI Clang ASan/UBSan: **32 assertions PASS**, no reported sanitizer failures in exercised paths.
- Prior parser regression GCC: **46 assertions PASS and 12,000 bounded malformed Mach-O header mutations**.
- Prior fake dyld API regression Clang ASan/UBSan: **14 assertions PASS**.

Complete log: `RP_V13_DLADDR_HOST_VALIDATION_20261113.log` (local handoff, not uploaded to GitHub to avoid confusing it with an Actions log).

## New file fingerprints (exact host-tested contents)

| File under police-rp/v13 | SHA-256 | Git blob SHA-1 |
|---|---|---|
| rp_v13_dladdr_identity.h | cf82b163983401584a89672c9b0c411bc4d8788b51e3420f0941ed7429145318 | 5ba798aaf28ac6d03e7a969cb9167935178b71f5 |
| rp_v13_dladdr_identity.c | 765dd078d023ce9e00994cdbd62af7771ce2e8151439e1ba83b1e29c7d407b4c | 0176763c133080de8eac5968e58637fd9a8d3193 |
| test_rp_v13_dladdr_portable.c | e603689e94449eb270c365914befee60f8d226a3d226ac3afddbcd869cad013e | b98f3afa71c3220318d9f92266ab95017cb41db3 |
| tests/fixtures/dlfcn.h | 4fa15754d2d2f95ed5c586f2dfff1094cad8f64634b9ef673a30785ece061dfa | f34b62530ef9dc7fc3594822dde04735c0c95ebd |
| tests/test_rp_v13_dladdr_identity.c | f33199807c4358c94d6191ae758112fce86256a7f3c265b287d04bfe7fc60d20 | efeca89e07ec57d126ad98b2f8eb9d4a15bef034 |

The GitHub blob hash of each new file was checked against the exact file compiled on the host. The original dyld provider and existing API behavior remain unchanged.

## Pending: Apple/engine proof, CI and rollback

- GitHub Actions on previous source head failed *before runner allocation* (runner_id=0; steps=[]). Updated workflow adds Linux normal/sanitizer and unsigned iPhoneOS arm64 compile/export check for `_rp_v13_dladdr_collect_identity`; **this Apple build is not yet verified**.
- Verify Apple SDK build, real dyld/dladdr behavior, module lifetime and code anchor provenance from exact v13 iPhone before use.
- Only then bind to trusted GTA frame/session adapter and authenticated RP transport, independently test 2-device disconnect/host migration and prove local ped release.
- Revert the isolated source commit to roll back. No automatic merge or IPA publication.
