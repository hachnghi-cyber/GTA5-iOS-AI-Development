# GTA5Port RP v1.8 - read-only ScriptHookV RPR1 guest probe

Purpose: prove ARM64 host -> RPV10_remote.bin -> guest ScriptHookV ASI on the user's v2.0.0 game, without touching gameplay.

Implementation
- Reader: RPRemoteMailboxReaderV18.c. Registers scriptRegister + scriptWait(250); uses CreateFileA/ReadFile and WriteFile(stdout) for native-port.log.
- RPR1: validates exact 764 bytes, magic/version, FNV1a checksum, 0..31 peers, unique 12-hex ID bounds, finite bounded coordinates, monotonic generation.
- Logs: RP18 READER_STARTED, FILE_MISSING, INVALID_FRAME, MAILBOX_VALID count=N frame=N, STALE_FRAME.
- No RAGE natives, PED creation, sockets, gameplay actions or Online hooks. Read-only except log line.

Installation
Place the ASI **beside RPPoseToFile-v0.8-E.asi in the SAME Mods subfolder** (e.g. Documents/Mods/RPPoseToFile-v0.8-E/). The v1.6 host writes RPV10_remote.bin beside RPV08_pose.bin; guest relative Win32 paths use each mod root in the publicly available source. This mapping still requires verification on the v2.0.0 IPA.
Run Story Mode, inspect native-port.log for `ASI console: RP18 READER_STARTED`. In the laptop peer test, expect `RP18 MAILBOX_VALID count=1 frame=N`; after departure, count=0.

CI evidence
- [v1.8 GitHub Actions PASS](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/44486520314): 8/8 pure C decoder fixtures; GCC/Clang; x86_64-pc-windows-msvc PE32+ DLL linking.
- ASI size 5,632 bytes. SHA256 c664c4fdb9a65fa16a99fff60e944018be154c464e62dc07a08aa9a44aaa55c8.
- Verified imports: ScriptHookV.dll scriptRegister/scriptWait, CreateFileA, ReadFile, WriteFile, CloseHandle.
- Separate owner-only source ZIP includes CI-built .asi, decoded C, static 764B fixture, Python generator, logs and manifest.

Critical source mismatch
Official [Five Star Port site](https://fivestarport.site/) clearly says open source available only to v1.5.2. The v2.0.0 release includes Five Star Online and changes to the native game runtime. The older source is a reference, NOT a matching build. Do not overwrite the existing 2.0.0 IPA with a 1.5.2 rebuild.

Pending device gates
1. ASI registered and reader started on real iPhone v2.0.0.
2. Host log REMOTE_POSE_RECEIVED and MAILBOX_WRITTEN after a simulated laptop peer.
3. Guest logs MAILBOX_VALID count=1 and then count=0 when the peer leaves.
4. Only then prototype PED creation in Story Mode, with cleanup, model validation and crash protection.

This is experimental; not a production Online RP feature. Keep the PR Draft, no game assets or IPA in the repository.