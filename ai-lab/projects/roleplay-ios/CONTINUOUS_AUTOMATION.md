# GTA V iOS RP — Continuous Engineering Policy

This repository uses **event-triggered and scheduled jobs**, not an endlessly running ChatGPT process.

## Enabled without API costs
- Existing GTA AI Lab CI: validation and routing on PR/push, daily on main.
- New `GTA RP - Continuous Source Watch` workflow: scheduled at minutes 11 and 41 of every hour (UTC), plus push/PR/manual dispatch. Runs after this PR is merged to the default branch. Each run validates project state, runs host unit tests and produces `RP_CONTINUOUS_STATUS.json` + `RP_HANDOFF.md`.
- GitHub issue automation: `[AI]` Issue titles receive role selection on main. The router is deterministic; **not 100 GPT instances**.
- Optional ChatGPT hourly task outside GitHub: monitors issues/PRs and may perform small, authorized changes when tool access is present. GitHub action and ChatGPT task are separate services.

## Version gate now available
- Metadata file: `ai-lab/projects/roleplay-ios/baselines/v12-verified.json`.
- Actual user-supplied IPA **not committed or distributed**.
- Exact `GTA5` SHA256: `d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b`.
- UUID: `6A498E32-E70C-334C-BCA3-AFFD35E8D171`.
- IPA ZIP SHA256: `23c039cb59e24f0107243a32252a3a60fbca1c934ac482d285109c323132f0dc`.
- Verify an authorized local IPA before any source patch, symbol/offset mapping, or integration:

```bash
python ai-lab/verify_ipa_baseline.py path/to/GTAV-v12.ipa
```

A new signature/ZIP layout may change the entire IPA SHA while the executable remains the same; the script gates on executable SHA256 and Mach-O UUID. A matching binary still does **not** establish valid signing, playable Roleplay or safe hook offsets.

## Why unattended code changes are gated
- Codex auto-implementation requires an authorized runtime and configured API credentials, potentially billable. No API key is stored in source control or supplied by ChatGPT.
- Unreviewed AI-generated code can break existing online sessions, consume CI budget, or inadvertently affect game binaries.
- Until a reviewed implementation workflow is configured, periodic actions **inspect, test and report**. They do not automatically patch game binaries or ship IPAs.
- For future autonomous coding, choose one bounded GitHub Issue; isolate on a feature branch, run tests, open draft PR, update `state.json` with evidence; never auto-merge or sign/distribute protected game assets.

## Operational controls
- Repository variable `DISABLE_RP_WATCH=true` skips watchdog jobs (for cost/CI capacity control).
- GitHub Actions schedule delivery is best effort; scheduled jobs may be delayed or missed.
- ChatGPT scheduled tasks can be paused through the ChatGPT automation controls.
- The original uploaded IPA is not automatically available to every future chat or GitHub runner. Only the verified metadata is persistent in the repository.

## Important technical blockers
Verified IPA version identity **does not** verify that `MacportWorkTaskFrame` is a safe recurring engine callback or that GTA Online allows an authenticated custom packet carrier. See `police-rp/v1.4/P2P/ENGINE_BINDINGS_REQUIRED.md`. Continue C/C++ source integration tests with mocks until device logs establish the real callback/transport ABI.
