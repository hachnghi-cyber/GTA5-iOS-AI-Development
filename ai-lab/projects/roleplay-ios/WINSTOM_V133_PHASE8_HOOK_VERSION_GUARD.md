# Phase 8 — v13.3 authenticated sender research: reject wrong-binary hook candidates

**Date:** 2026-11-16. **Status:** static version check + Python regression, **NOT** native engine integration.

## Exact target

- Original `GTAV-v13.3.ipa` `GTA5` UUID: `EB122C35-96F4-307F-91C3-A2255DD9C685`
- Original v13.3 `GTA5` SHA-256: `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`
- Winstom `lmx.dylib` and Winstom `GTA5` have different Mach-O UUIDs and **are not substitutable hook offset sources**.

## Newly verified source discrepancy

Two existing source reports were reopened directly from this repository:

1. `police-rp/v1.4/HOOK_CANDIDATES_V12.json` contains a `MacportOnlineUpdate` candidate at `0x00000001000e01a0` and `MacportWorkArrestScene` at `0x000000010011bc8c`, but its **own recorded** `GTA5_UUID` is `6a498e32e70c334cbca3affd35e8d171` and SHA-256 `d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b` — i.e. not v13.3.
2. `police-rp/v1.4/DIAGNOSTIC_READONLY_REPORT_V13.json` has a **V13 in its filename**, but `input_gta5_uuid` and `input_gta5_sha256` still match the **same older binary**. Filename is not proof of v13.3 compatibility.

**Implication:** Copying the old addresses into v13.3 without re-identifying the call graph risks corruption or crashes. Even a perfect hash and UUID match only identifies an exact binary; it does **not** prove function calling convention, game-thread scheduling, event sender authentication or pointer lifetime.

## Implemented mitigation

- `v133_interaction/tools/audit_hook_fingerprint.py`: pure Python, read-only. Accepts both legacy JSON schema variants and reports exact-match / mismatch / invalid fingerprint. Always returns `may_hook_v133=false` and `may_use_as_authenticated_sender=false`. There is no patch/hook operation.
- `v133_interaction/tests/test_audit_hook_fingerprint.py`: five unit tests, including BOTH old source files and a synthetic exact-match candidate that still remains UNVERIFIED.
- PR workflow `.github/workflows/winstom-rp-ipa-audit.yml` runs the tests on changes.

## GitHub evidence

- Commit `ee84d311901a8bebae035865b3027a69d14fc10b` adds the regression step.
- [GitHub Actions run 43788777959](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43788777959): Python job **SUCCESS**; five new tests `Ran 5 tests ... OK`.
- Existing Phase 7 source-only C11 mailbox and synthetic network tests are unaffected by the new guard.
- No binary disassembly performed in this iteration because the underlying GTA5 file bytes were not directly accessible in the current execution environment. Findings here are from the verified source JSON files.

## Next narrow proof required

1. Materialize the **exact** original v13.3 `GTA5` for read-only disassembly with UUID/hash confirmed.
2. Compare actual `MacportOnlineUpdate` candidates against existing callsites, identify genuine game-frame context, and determine the correct function ABI/ASLR mapping. Reject old v12 RVA.
3. Trace authenticated sender ownership from RAGE transport metadata (not `MPJ2.slot_hint`, bare pointers, name, JS or synthetic flags).
4. Validate one read-only `PRP3 greet` A→B with logs from two user-controlled iPhones and independent provenance. Only after this should Police cuff/escort work begin.

**No real iPhone test, no actual network sender verification, no hook installed, no playable RP IPA.**