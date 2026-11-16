# Phase 6 — Exact-build ScriptHookV ABI and E0 full-path regression

Scope: user-supplied GTA V iOS v13.3 IPA; read-only disassembly. No IPA, game executable, signing key or private game asset committed to GitHub.

- IPA SHA256: `7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7`.
- ScriptHookV SHA256: `a86451f766925adf9fa8dfedd8cfa92f9895bd68fda16b3795e6f747fef2196d`.
- Mach-O UUID: `F768B7B5-AD75-39F4-83D3-8E49234325B5`.
- `_sh_game_start` at `0x4DAC`: indirect call to plugin `DllMain`, passing loader handle and reason 1. STATIC ONLY.
- `_scriptWait` at `0x56B4`: NULL script context skips `_sh_swap`; a spin risk if caller loops without a yield. STATIC ONLY.
- `_scriptRegister` at `0x59D0/0x59D4`: capacity guard. STATIC ONLY.
- `_sh_fiber_main` at `0x78F34/0x78F44/0x78F58`: invokes registered callback, sets completed status 2 on return and swaps to scheduler. Callback termination is a recognized engine path. STATIC ONLY.

Earlier host regression stopped at tick 31 using `longjmp` and never reached `SCRIPT_CALLBACK_COMPLETE=1`. This test design flaw was corrected: separate host processes now test all 120 normal ticks and four rapid no-yield returns, with independent log assertions. This still MOCKS the ScriptHookV functions, not real RAGE.

Locally verified 2026-11-16:
- Clang host tests: both normal and fast-return PASS.
- GCC host tests: both modes PASS.
- Clang ASan/UBSan: both modes PASS (leak detection disabled).
- Python: 15/15 PASS (9 E0 log validation + 6 synthetic Mach-O parser guards).
- Exact user-supplied v13.3 IPA audit: 9 ARM64 instruction words, SHA256 and UUID match.
- Original IPA unchanged.

Manual static auditor: `python3 tools/verify_shv_abi.py /path/to/GTAV-v13.3.ipa`.
It refuses other builds and invalid load commands, and **never** authorizes a live hook. It cannot prove iPhone callback execution. iPhoneOS SDK linkage/signing, Story/Online E0 log, E1 native HUD and E3 trusted remote action remain DEVICE VALIDATION REQUIRED. Sender provenance PR #16 remains separate, not resolved here.
