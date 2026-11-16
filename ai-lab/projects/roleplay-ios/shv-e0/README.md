# GTA V iOS v13.3 — ScriptHookV E0 load/callback gate

This isolated diagnostic is separate from PR #16 native receive-context work. It contains NO RAGE hook, packet transport, native gameplay invocation or GTA binary changes. Source only; no copyrighted IPA or signing keys.

Exact input identity (verified locally): GTA5 SHA256 f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc; ScriptHookV SHA256 a86451f766925adf9fa8dfedd8cfa92f9895bd68fda16b3795e6f747fef2196d; ScriptHookV Mach-O UUID F768B7B5-AD75-39F4-83D3-8E49234325B5.

On Linux: run scripts/run_host_test.sh; the ScriptHook exports and callback are MOCKS. On macOS/Xcode: run scripts/build_iphoneos.sh /tmp/rbp-e0-out. GitHub workflow builds unsigned iPhoneOS ARM64 .shv.dylib and checks DllMain export, dependencies, architecture and platform. No IPA or installed app is produced.

Real iPhone E0 gate (NOT PERFORMED):
1. Embed RBPProbeE0.shv.dylib under the matching app's Frameworks and sign it and the owning app legitimately, with matching provisioning. Never distribute private IPA or certificates.
2. Enable normal ScriptHook from the port's UI (if disabled), restart app, and enter a controlled test session.
3. Retrieve app sandbox Documents/RBPProbeE0.log, plus posthook.log if no probe log exists.
4. Require fresh RUN_BEGIN VERSION=1, DLLMAIN_ATTACH, SCRIPT_HOOK_UUID_MATCH=1, SCRIPT_REGISTER_ATTEMPTED=1, CALLBACK_ENTER, and SCRIPT_TICK=1 in the same run. Registration returns void: a registration attempt alone is never a pass.
5. Repeat separately in Story and Online. Record iOS build, game mode, launch time and actual runtime logs. If plugin never loads or ScriptHook is OFF, mark E0 BLOCKED, not failed network.

Fail closed: find EXACTLY one already-loaded ScriptHookV.dylib by dyld basename, check full UUID before resolving any export, and open it with RTLD_NOLOAD only. If UUID/symbol fails, do not register a callback. No network, no nativeCall, no event queue. Logs contain no accounts/session IDs or keys.

Evidence statuses: local source + Linux host mock PASS; iPhoneOS SDK compile pending CI; on-device loading, scheduler tick, E1 native gameplay, E3 two-iPhone remote action and synchronization ALL unverified.

PR #16 remains primary native transport research. This E0 probe is an independent minimal experiment to validate the alternative ScriptHook gameplay bridge without guessing RAGE offsets.
