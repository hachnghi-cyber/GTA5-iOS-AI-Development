# P0 — Integration preview, not merged into main

Source parent: `d83bcd049649856411595b8cbf7d5c7c4288311e` (2026-11-13).

| Source PR | Immutable head SHA |
|---|---|
| [#7](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/7) | `5ca26698fad9425cf5c059674f3c984a5bd3b00f` |
| [#4](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/4) | `784c9e257e84707e3896982c280002697f5344ea` |
| [#9](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/9) | `e32415c3184cdaca1338613a425014dd57552c27` |
| [#8](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/8) | `61d42522b7efa9df196a08f31ed8acc9697c150f` |

Combined 38 non-state file blobs using the PR order #7 → #4 → #9 → #8. The only shared changed path between PRs is `ai-lab/projects/roleplay-ios/state.json`. Main also changed `ai-lab/tests/test_continuity.py` since PR #4 split: this preview deliberately uses the PR #4 fix that makes the negative test independent of current evidence.

`state.json` starts from the PR #4 P0 phase/state and retains the v12 IPA/executable SHA256 and UUID; it adds unique verified facts, provenance, PR #9 snapshot and offline opt-out metadata and source-only release documentation. RP-006 is **not-started** and P0 gate remains **in-progress**.

## Review gate

- Verify the complete diff, all source file ownership and the reconciled `state.json`.
- Verify combined Python/C host tests including sanitizers, iPhoneOS ARM64 **unsigned source library** and phase/release gates.
- Examine any CI failures and fix on this preview branch only; do not merge `main` or the underlying PRs automatically.
- Real GTA v12 authenticated game-frame and network carrier, two-device gameplay and IPA signing are not verified. No IPA or assets have been uploaded.

Rollback: delete this standalone preview branch/PR after review. Original branches and main remain untouched.
