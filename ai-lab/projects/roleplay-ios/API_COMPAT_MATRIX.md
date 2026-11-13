# RP-003 / RP-002 — GTA V iOS v12 Roleplay source contract matrix

Reviewed against these repository source paths (not the game executable):

- `police-rp/v1.4/P2P/prp_p2p.h`, `prp_p2p.c`
- `police-rp/v1.4/P2P/prp_runtime.h`, `prp_runtime.c`
- `police-rp/v1.4/NativeBridge/police_rp_adapter.h`, `police_rp_adapter.c`,
  `police_rp_only.c`
- `police-rp/v1.4/P2P/ENGINE_BINDINGS_REQUIRED.md`
- `police-rp/v1.5/README_VI.md`

The **source code implements a cooperative RP policy/protocol**, not a proven
in-game transport. Host tests are separate from iPhone device tests.

| Capability | Source contract / evidence | Source implementation | GTA v12 integration |
| --- | --- | --- | --- |
| 56-byte PRP packet | `PRP_WIRE_SIZE`, `prp_encode`, `prp_decode` in `P2P/prp_p2p.h/.c` | Implemented C encoder/decoder with length, opcode and bounds checks | Not verified; must use an already-authenticated game channel, never raw UDP |
| Host authority | `prp_host_receive` in `P2P/prp_p2p.c` | Validates session, engine-supplied trusted sender, opt-in, role, proximity, replay | Host/player metadata provenance from GTA not established |
| Opt-in/out | `prp_runtime_consent`, `prp_host_receive` | Explicit consent message; remote snapshots cannot grant consent | Game UI/transport/input binding not verified |
| Cuff / uncuff | `PRP_OP_CUFF`, `PRP_OP_UNCUFF`, `pr_adapter_tick` | Host state + local-only cuffs/restriction callbacks | No verified engine-owned game-frame callback or local-ped binding |
| Escort | `PRP_OP_ESCORT` | State transition from cuffed to escorted, proximity gate | Physical escort movement/animation not implemented by this P2P module |
| Jail | `PRP_OP_JAIL`, `PRP_MAX_JAIL_MS` | Host-authoritative state and expiry; verified-station flag requirement | No tested station provenance, jail animation, teleport or physics sync |
| State heartbeat | `prp_runtime_tick`, `PRP_HEARTBEAT_MS` | Host generates status every 500 ms; adapter clears stale state | No proven game frame dispatch to invoke tick |
| Session disconnect / host migration | `prp_runtime_stop`, `prp_runtime_tick` | Local reset on missing/wrong session; guarded by engine-provided identity | No verified GTA host-migration event callback |
| Police duty | `PR_EngineView.native_job`, `on_shift`; v1.5 duty probe | Source checks job 0..2 and shift; v1.5 is read-only instrumentation | Duty symbols and offsets require device log validation |
| EMS / taxi | Not part of `PRP_Op` v1.4 P2P protocol | **Not demonstrated in this audited P2P subsystem** | Other source snapshots require separate audit before claims |
| ABI / PC mod interoperability | `PR_ADAPTER_ABI=2`, `PR_ABI_VERSION=1` | Host C adapter API is versioned | Windows .asi/SHVDN/FiveM ABI compatibility is **not established** |

## Reproducible host verification

PR #4 adds an actual GCC/Clang build and execution of the C sources via:

```sh
python ai-lab/host_rp_tests.py --output ai-lab/reports/RP_HOST_C_TESTS.json
```

The runner compiles `test_p2p.c`, `test_runtime.c` and `test_duty_exit.c`
against the real protocol, runtime and bridge C sources; warnings are fatal.
It records SHA-256 of the audited C inputs, compiler, test outputs, and
whether each test compiled and passed. A failure causes CI to fail.

**Neither a passing host test nor the report proves GTA Online transport,
RAGE event compatibility, a signed IPA, or iPhone stability.** `test_p2p.c`
uses synthetic authenticated contexts; it does not establish an engine-level
trusted-sender source.

## Next integration evidence required

1. Identify an exact-version **game-thread** callback for both host/guest;
   capture logs showing it invokes `prp_runtime_tick` after GTA Online joins.
2. Identify a real GTA-owned authenticated application payload carrier,
   with `session_id`, `trusted_sender_id` and `host_player_id` from trusted
   dispatch context—not packet claims.
3. Exercise opt-in, cuff, opt-out, timeout, disconnect, host migration and
   2-device session behavior; attach non-sensitive device logs.
4. Build a separately signed authorized IPA only after that evidence.
   Until then, classify all in-game RP features as **not device-verified**.

Rollback: revert the host test runner/test, CI step, source formatting fix,
matrix and state changes in this draft PR. Do not merge without CI review.
