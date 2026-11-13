# RP-006 — Automated release readiness gate (source-only)

This is **not** an IPA builder or a signed public release. It is a deterministic
Python/CI safeguard to avoid treating host tests as proof of working iOS
multiplayer. No commercial IPA, certificates or secrets are uploaded.

## What is automated

The existing `GTA RP - Continuous Source Watch` workflow, scheduled at
`11,41 * * * *` UTC on the default branch, now also runs:

```sh
python ai-lab/release_readiness.py --output ai-lab/reports/RP_RELEASE_READINESS.json
```

Its `rp-continuous-watch` artifact contains the release readiness JSON.
A blocked report is **expected** while engineering inputs are missing;
monitoring CI remains green if the report is generated correctly.
The script has no OpenAI API requests and does not build/sign/publish files.

A future actual packaging step **must** use the strict variant and refuse
to continue when blocked:

```sh
python ai-lab/release_readiness.py --require-ready
```

An authorized local IPA can be separately checked with the existing
read-only binary verification tool (never place the IPA in this repository):

```sh
python ai-lab/verify_ipa_baseline.py '/local/path/GTAV-v12.ipa'
```

## Required before manual IPA candidate review

The report requires the stored v12 IPA SHA-256, executable SHA-256 and Mach-O
UUID to match their baseline metadata. It also requires a recorded candidate
build artifact and `device_tested: true`. For each entry under optional
`state.json.release_evidence`, a reviewer must record `status: verified`,
a non-empty `evidence` reference and `executable_sha256` matching the exact
v12 executable:

- `game_frame_callback`: authentic per-frame engine entry point
- `authenticated_transport`: session/authenticated player packet delivery
- `ios_build`: actual ARM64 iPhoneOS linker/build output
- `codesign`: provisioned local signing/re-signing proof
- `device_multiplayer`: two-device session behavior with logs
- `regression`: crash and feature regression log

`manual_approval` additionally requires `approved: true`, an evidence
reference and matching executable hash. **Evidence references are declarations;
this script does not independently authenticate logs or signers.**
Even when all gates pass, the only possible status is
`ready-for-manual-release-review` with `auto_publish_allowed: false`.

## Current v12 blockers

The source inventory and baseline are available, but the engine game-frame
callback, authenticated RP packet carrier, signed build and real two-device
testing have not been established. Therefore an automatically released
`GTA-V-iOS-RP.ipa` would be misleading. The release gate must remain
blocked until the evidence exists.

**Rollback:** revert the Python script, its unit tests and the single
workflow report/upload change. This does not touch the app or game data.
