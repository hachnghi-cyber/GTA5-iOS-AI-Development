# BÁO CÁO BÀN GIAO CHO AI KHÁC — GTA V iOS v13.3 Police Roleplay

**Ngày chốt bản:** 16/11/2026. **Ngôn ngữ:** Tiếng Việt. **Trạng thái:** Phase 8, nghiên cứu xác thực sender/session trên mạng GTA Online, chưa tích hợp RP gameplay thật. **Nguồn sự thật:** GitHub branch và log CI, không phải các lời hứa trong cuộc trò chuyện.

## 0. Đọc điều này trước khi nhận dự án

- Repo: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development
- Branch nghiên cứu: `feature/winstom-rp-ipa-audit-20261116`; Draft PR #16: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/16
- Commit cuối trước khi tạo báo cáo: `e7068058a33ebe8e718356a664361a16dad8cb66` (các commit bổ sung báo cáo/đóng gói sẽ thay đổi HEAD, xem manifest trong ZIP).
- Điểm nối trạng thái máy: `ai-lab/projects/roleplay-ios/state.json`, `CONTINUE_HERE.md`, `ROADMAP.md` và `AGENTS.md` ở repo.
- **KẾT LUẬN KHÔNG THỂ HIỂU SAI:** Chưa có IPA Police RP Online có còng tay/áp giải chơi được. CI pass và dựng thư viện chẩn đoán **không** đồng nghĩa xác minh gameplay trên iPhone.
- **Không tự merge PR, không tự bật còng tay Online, không đăng IPA GTA5 thương mại/game assets/certificates lên repo công khai.**

## 1. Mục tiêu cuối cùng và giới hạn

Phát triển Police Roleplay trong GTA V iOS v13.3 đang có, không tách server RP riêng theo hướng thiết kế hiện tại; giữ nguyên Story Mode, Online base, UI/VI/Telegram khi cần. Những hành động đích: nhận ca cảnh sát, xác thực nhân viên/đối tượng, còng/tháo còng, áp giải, đưa lên xe, nhà tù, đồng bộ với người chơi khác. Chỉ triển khai sau khi xác minh truyền thông A→B, quyền điều khiển entity và opt-in.

Mô hình mục tiêu sơ bộ:

    Original GTA5 v13.3 (chưa nối)
         ├─ game-thread callback [CHƯA XÁC MINH]
         ├─ engine-owned session/epoch/player/sender [CHƯA XÁC MINH]
         └─ private authenticated gameplay transport [CHƯA XÁC MINH]
                       ↓
          rp_v133_mailbox (C11, đã viết)
             64 slots × 40B PRP3, tối đa 8 event/frame
                       ↓
          rp_v133_wire_decode + rp_v133_interact_gate (đã viết)
             GREET/DOCUMENTS, opt-in, 400 cm, anti-replay
                       ↓
          observe_interaction (chưa nối UI/game thật)
                       ↓
          cuff/escort authority + state sync [CHƯA LÀM]

Không được dùng `MPJ2.slot_hint`, remote pointer, JS payload, tên người chơi, hay cờ `authenticated=true` tự khai báo để giả dạng native sender. Đối với bản thân log JSONL, chữ 'engine-authenticated' chỉ là **lời khai dữ liệu**, không phải chứng thực nguồn.

## 2. Fingerprint binary — tuyệt đối không trộn phiên bản

| Dữ kiện | Original GTA V iOS v13.3 | Winstom 0.7.171 |
| --- | --- | --- |
| IPA | `GTAV-v13.3.ipa` | `Winstom-0.7.171.ipa` |
| Bundle | `com.macport.gtav` | `com.winstom.rp` |
| iOS tối thiểu | 16.3 | 18.0 |
| IPA SHA-256 | `7a5e23358e4a72a03322fe016ea08adde1ee6189b0c66f86e656a48649057b89` | `9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126` |
| Main `GTA5` SHA-256 | `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc` | `df7427d0e19271b1b49f0132d8d6d3be0dd65a04b4c86991749b75ed9b15f0e4` |
| Main `GTA5` UUID | `EB122C35-96F4-307F-91C3-A2255DD9C685` | `048DCEFF-A696-3E7A-9086-2A9953C909CD` |

Winstom `lmx.dylib` UUID `003F682B-D578-332C-840E-7B789CD594DC`, SHA-256 `dd2a00535b4df1118ce5f94bab1434c052233de4d9a04e3d153f5707d0404ec5`. Winstom nhập `lmx.dylib` và `wf.dylib` trong main executable; nó không đóng gói y nguyên Menyoo, ScriptHookV, Mono, DXGI của original v13.3. **Không sao chép offset/hook Winstom vào original.**

**Bẫy nghiêm trọng đã phát hiện:** `police-rp/v1.4/DIAGNOSTIC_READONLY_REPORT_V13.json` có tên V13, nhưng ghi UUID `6a498e32e70c334cbca3affd35e8d171` cùng với `HOOK_CANDIDATES_V12.json`. Địa chỉ `MacportOnlineUpdate 0x00000001000e01a0` trong tài liệu đó chỉ là candidate của *binary khác*. Công cụ `tools/audit_hook_fingerprint.py` cố ý luôn trả `may_hook_v133=false`, kể cả khi SHA/UUID khớp, vì khớp build chưa đủ chứng minh ABI, thread, pointer lifetime, sender.

## 3. Reverse engineering Winstom — điều đã xác minh

Phân tích tĩnh `lmx.dylib`, không giải mã asset `WSPK/WPK` và không sửa game:

| Mục | Địa chỉ VA lmx | Chứng cứ |
| --- | --- | --- |
| `LMXMessageProxy.userContentController:didReceiveScriptMessage:` | `0xe888` | Forward target sang script handler |
| `AVPanel.userContentController:didReceiveScriptMessage:` | `0xb2358` | Xử lý action trong native WebKit handler |
| Check `interact` | `0xb8784` | Objective-C `isEqual:` |
| Đọc `cuffed` | `0xbc2ec` | `objectForKeyedSubscript:` |
| Đọc `follow` | `0xbc63c`, `0xbc6b0` | `objectForKeyedSubscript:` |
| Function trạng thái | bắt đầu `0xba738` | Có tham chiếu CFString `cuffed` và `follow` |

`LemexiLauncher/rp.js` có UI tương tác `greet`/`documents` và lọc mục tiêu 4 m phía client. Thấy field `cuffed/follow` **không chứng minh** hành động native còng hoặc server sync. `WRTransport` chủ yếu là HTTP (`NSURLSession`), `WRAccountSession` giữ session tài khoản, `WRVoice` lo âm thanh; không được coi đó là carrier RP gameplay đáng tin cậy. `westrayn-core` / OneSync chỉ mới có bằng chứng chuỗi diagnostic và vùng phân tích tĩnh, chưa rõ network dispatch chính xác.

Đọc thêm báo cáo `WINSTOM_V133_BINARY_DIFF_PHASE3.md`, `WINSTOM_0_7_171_CFSTRING_ROUTE_PHASE4.md`, `WINSTOM_V133_PHASE5_DISPATCH_WIRE.md`, `WINSTOM_V133_PHASE6_TRACE_VALIDATION.md`.

## 4. Mã nguồn đã có — trách nhiệm mỗi file

**C11 main, thư mục `ai-lab/projects/roleplay-ios/v133_interaction/`:**

- `include/rp_v133_interact_gate.h` + `src/rp_v133_interact_gate.c`: gate chỉ cho `GREET=1`, `DOCUMENTS=2`; callback xác thực build, game thread, phiên, peer distance 400 cm, consent, anti-replay. Callback mới là dependency injection, **chưa nối RAGE thật**.
- `include/rp_v133_wire.h` + `src/rp_v133_wire.c`: frame `PRP3` 40 byte, little-endian gồm magic/version/kind, session ID, receiver ID, session epoch, nonce. **Không có sender/auth trong payload**.
- `include/rp_v133_mailbox.h` + `src/rp_v133_mailbox.c`: network-thread producer không block, 64 slot, xử lý tối đa 8 packet trong game frame. Dữ liệu có nguồn engine là hợp đồng chưa xác minh, không phải tính năng đã có.
- `tests/test_v133_interact_gate.c`, `test_v133_wire.c`, `test_v133_two_peers.c`, `test_v133_mailbox.c`, `test_v133_mailbox_threads.c`: fixture giả lập, có đa luồng pthread, không mô phỏng chính xác RAGE.
- `tools/run_host_tests.sh`: chạy năm binary test; `tools/verify_device_trace.py` + `tests/test_verify_device_trace.py`: đối chiếu log PRP3 A/B, không chứng thực nguồn log.
- `tools/audit_hook_fingerprint.py` + `tests/test_audit_hook_fingerprint.py`: cấm dùng nhầm JSON hook cũ.

**iOS, thư mục `v133_interaction/ios/`:**

- `PRPV133LaunchProbe.m`: Objective-C startup-only dylib constructor; kiểm tra main Mach-O UUID, ghi `Documents/PoliceRP-v13.3-Phase8.txt`. Bốn dòng `engine_game_thread_verified=0`, `authenticated_network_sender_verified=0`, `rp_network_enabled=0`, `cuff_or_escort_enabled=0` phải giữ đúng vì chưa tích hợp.
- `patch_exact_v133_probe.py`: xác minh hash IPA và executable gốc, thêm duy nhất load command tải dylib, giữ resource game, tùy chọn bật File Sharing; tạo **IPA unsigned** tại máy người dùng, không ký.
- `Make_Phase8_IPA_Windows.bat`; `Make_Phase8_IPA_macOS_Linux.sh`: trình đóng gói cục bộ đơn giản.
- `test_v133_probe_packer.py`: sáu unit tests, gồm thử ghép ZIP/Info.plist với Mach-O giả lập.
- `README_TEST_VI.md`: lệnh build IPA unsigned, re-sign và thử iPhone.

**Tool phân tích nhị phân:** `ai-lab/winstom_rp_audit.py`, `ai-lab/winstom_lmx_objc_map.py`, hai Python unit tests dưới `ai-lab/tests/`.

**CI:** `.github/workflows/winstom-rp-ipa-audit.yml` (Python, C11) và `build-v133-phase8-probe.yml` (Mac `iphoneos` arm64 dylib), không có luồng xuất bản game IPA.

## 5. Bằng chứng kiểm thử có thể đối chiếu

| Đã kiểm tra | Bằng chứng | Không chứng minh |
| --- | --- | --- |
| Host GCC/Clang ASan+UBSan C11, source-only | https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43786760288 | Kết nối game/network iPhone |
| Trace Python, Mach-O source audit | https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43788777959 | Native authenticated sender |
| iPhoneOS arm64 `PoliceRPV133Probe.dylib` và 6 synthetic packer tests | https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43793010558 | Boot IPA / code signing / RP gameplay |
| CI Winstom + AI lab sau Phase 8 | https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43793312865 | Hai iPhone đồng bộ RP |

Cấu trúc H5 device diagnostics được ghi trong Phase 6: **8 `Decide` và 8 `MPJ2` mẫu** đều `sender_auth=0`, `gameplay=0`. Mẫu hẹp này không đại diện toàn bộ game. Ghi chú lịch sử trong báo cáo Phase 5/6 có thể ghi CI thất bại hoặc 12/13 tests; **trạng thái cuối phải đối chiếu run mới hơn ở bảng trên**.

**Không có bằng chứng:** real 2-iPhone `PRP3`, signer build install, live GTA5 hook, trusted sender/session, quyền ownership, cuff/escort/jail playable, bảo toàn crash/FPS, ThreadSanitizer, full IPA phát hành.

## 6. Tái lập từ mã nguồn

    git clone https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development.git
    cd GTA5-iOS-AI-Development
    git switch feature/winstom-rp-ipa-audit-20261116
    cd ai-lab/projects/roleplay-ios/v133_interaction
    CC=gcc bash tools/run_host_tests.sh
    CC=clang bash tools/run_host_tests.sh
    python3 -m unittest discover -s tests -p 'test_verify_device_trace.py' -v
    python3 -m unittest discover -s tests -p 'test_audit_hook_fingerprint.py' -v
    python3 -m unittest discover -s ios -p 'test_v133_probe_packer.py' -v

Trước khi test IPA với thư viện đã biên dịch: lấy artifact trong workflow Mac ở bảng trên, dùng **đúng** original `GTAV-v13.3.ipa`, tạo IPA unsigned bằng tool `ios/`. Hash sai thì dừng; ký lại **toàn app và dylib** với provisioning thích hợp, sao lưu save, thử launcher/Story, rồi lấy `PoliceRP-v13.3-Phase8.txt` và crash logs. Thư viện startup probe không chứa RP online; khi chưa có log máy thật, ghi **NOT DEVICE VERIFIED**.

## 7. Vấn đề chặn số 1 và tiêu chí gỡ chặn

**Root blocker:** Chưa có điểm callback game-thread RAGE v13.3 và nguồn **authenticated sender/session/epoch** được chính engine chứng thực. Đây là vấn đề thực chất, không giải quyết bằng cách thêm nhiều fixture giả lập.

**Thứ tự triển khai AI tiếp nhận phải theo:**

1. Đọc code và xác minh binary `GTA5` v13.3 SHA/UUID bằng công cụ đọc-only; định vị `MacportOnlineUpdate`/network receiver theo call graph **trong đúng binary**. Xác định ABI, ASLR slide, concurrency, pointer lifetime trước khi hook. Không dùng RVA v12/Winstom.
2. Xác nhận IPA Phase 8 startup probe thực sự nạp được trên một iPhone sau khi ký; lấy log/kết quả crash; rollback nếu fail.
3. Bằng chứng provenance sender từ **private authenticated engine channel**, không từ `MPJ2`, JS/UI, display name, pointer hoặc JSON flag. Xác thực session epoch/peer id qua đổi host, rời phòng.
4. Chỉ gửi sự kiện `PRP3 greet` thử A→B trên 2 iPhone được phép; ghép TX/RX bằng `verify_device_trace.py`, đồng thời có bằng chứng callback/stack/runtime rằng log đến từ engine.
5. Khi 1–4 PASS: thiết kế transactions `cuff/uncuff`, `escort/stop`, `vehicle seat`, `jail` với opt-in, host authority/ownership, timeout, rollback khi disconnect/migrate; test hai máy, network loss, crash, FPS, menu/Story regression.

**Thứ tự ưu tiên:** xử lý đúng bước khó số 1 + kiểm thử iPhone, tránh lặp nhiều phiên bản source POC chỉ có unit tests. Báo cáo công khai mọi blocker và trạng thái thực tế.

## 8. Báo cáo kiểm thử và bằng chứng cần AI tiếp nhận bổ sung

Mỗi thay đổi cần có: tên và SHA input exact, commit, file diff, kết quả GCC/Clang/iPhoneOS link (nếu chạy), link CI, nhận định verified/inferred, còn thiếu gì, một bước tiếp theo, hướng rollback. Phân biệt bốn trạng thái:

- `STATIC_VERIFIED`: cấu trúc/mã máy, SHA, disassembly hợp lệ.
- `HOST_TESTED`: unit/integration fixture trên runner.
- `IPHONE_BOOT_VERIFIED`: người dùng gửi log tương ứng từ máy thật.
- `TWO_DEVICE_RP_VERIFIED`: hành động real A/B cùng hiện đúng state.

Không gộp các trạng thái. Không viết `99% hoàn thành`, `cuff working`, `no crash` nếu chưa có bằng chứng thiết bị.

## 9. Về ZIP bàn giao và nguồn riêng tư

ZIP bàn giao chỉ được chứa tài liệu, source sạch và tests. **Không bao gồm** `GTAV-v13.3.ipa`, `Winstom-0.7.171.ipa`, `lmx.dylib`, nguồn game độc quyền, tài khoản, provisioning, signing key hay log cá nhân. AI mới cần binary thật thì nhận qua kênh riêng với sự cho phép của chủ sở hữu.

**Điểm tiếp tục duy nhất:** `ai-lab/projects/roleplay-ios/state.json` (đọc ngay trên HEAD mới nhất), ưu tiên **exact-build RAGE callback + real-device boot**, không nhảy sang còng tay khi `authenticated sender` chưa có.
