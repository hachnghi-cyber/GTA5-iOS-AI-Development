# Phase 8 — ScriptHookV loader-source correlation (v13.3 only)

## Evidence
Using the user-supplied v13.3 IPA, ScriptHookV SHA256
a86451f766925adf9fa8dfedd8cfa92f9895bd68fda16b3795e6f747fef2196d
and UUID F768B7B5-AD75-39F4-83D3-8E49234325B5, exact ARM64 disassembly:
- _sh_game_start 0x4C1C..0x4C34: open Documents/posthook/scripthook-off; off marker disables plugin scan.
- 0x4CB0..0x4D2C: enumerate Frameworks, filter .shv.dylib.
- 0x4D70..0x4D94: dlopen, resolve DllMain, compare before/after script count.
- 0x4DA4..0x4DAC: call DllMain(handle,1,NULL) if count unchanged.
- 0x4DB4..0x4DC4: subtract new registrations and log "[shv] loaded plugin %s (%d scripts)".
- dlopen failure logs "[shv] couldn't load plugin %s: %s".

New readonly tool `tools/verify_loader_contract.py` checks SHA256,
Mach-O UUID, 16 exact ARM64 words and stock loader string literals. Local
exact IPA audit PASS. These are code-path facts, NOT on-device observations.

## Evidence ladder
1. Loader log explicitly names RBPProbeE0.shv.dylib (module load attempt).
2. Stock "loaded plugin ... (1 scripts)" indicates ScriptHook registration
   count incremented by one in the same loader call. Registration alone does
   not prove the callback ran. Counter effects from constructors could exist,
   so also require the probe's DllMain/registration markers.
3. A fresh RBPProbeE0.log with callback enter, ticks 1/30/120 and completion.
4. Correlate both logs' clock/time zone; text consistency still does not
   authenticate logs, device, binary or Story/Online mode.

## Run after device signing (NOT YET PERFORMED)

Collect current-run `posthook.log` and `Documents/RBPProbeE0.log` from
the same installed, development-signed v13.3 app. Do not send raw player
identities, session keys, or unrelated private data.

    python3 tools/evaluate_e0_pair.py \
      --probe RBPProbeE0.log --posthook posthook.log --timezone-offset-minutes 420

Set timezone offset to the actual iPhone setting (example +420 for UTC+7).
If omitted, clock correlation remains unverified. The classification
`STOCK_AND_E0_LOGS_CONSISTENT_NOT_DEVICE_PROOF` is deliberately NOT
a hardware-success status; device provenance, execution mode, signature,
and installation must be independently checked.

Negative classes include SHV_DISABLED, PLUGIN_DLOPEN_FAILURE,
STOCK_LOADER_ENTRY_MISSING, REGISTRATION_DELTA_NOT_ONE,
STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED, TIME_MISMATCH.

Current blocker: GitHub macOS-15 ios-link job 43898609050 was CANCELLED before
linking; no E0 iPhoneOS dylib artifact. Host-mock CI and these static checks
do not prove E0, E1, E3, or Police RP on two iPhones.
