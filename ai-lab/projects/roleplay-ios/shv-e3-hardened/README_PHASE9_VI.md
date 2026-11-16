# GTA V iOS v13.3 — Phase 9: Native E3 Hardened (Source & Evidence)

**Mục tiêu đang theo đuổi:** chứng minh A gửi PING, B xác thực gói và gọi native HUD, rồi trả lại bằng chứng đã gọi native cho A. Đây là *diagnostic PING*, CHƯA phải GTA Online Police RP. Chưa có iPhoneOS SDK, chưa cài và kiểm tra trên iPhone.

## Điểm mới của Phase 9

- Thay vòng lặp `scriptWait(0)` vô hạn bằng **900 tick có giới hạn**, `scriptWait(16)`, guard 4 lần trả về dưới 0,5 ms, có log fail-closed. Ở cuối callback dừng UDP worker (không để thread sống sau test).
- Native-report chỉ được phát hành **sau khi callback đã gọi** chuỗi ba native functions ở game-side adapter; không phát hành từ UDP worker khi chỉ nhận packet.
- Giao thức HMAC RBP1 96 byte thêm `kind=3` (native-invoked). A yêu cầu cả `ACK_VERIFIED` (đã vào queue) và `NATIVE_INVOCATION_REPORT_VERIFIED` (đã nhận HMAC report khớp nonce/seq/target/session/time/IP).
- Handoff lưu nonce gốc; report one-slot sử dụng atomic release/acquire; từ chối state trùng hoặc báo cáo trễ/không khớp. Không gửi thông tin người chơi hoặc khóa bí mật vào log.
- Sửa `dlsym` để Clang và GCC -Wpedantic -Werror đều build.

## Bằng chứng

`PHASE9_VALIDATION.json` ghi rõ phân biệt host/static/device. Cả Clang và GCC chạy `run_phase3_checks.sh` thành công, Python 37/37 PASS (0 skip), C ASan/UBSan PASS. Trên hai tiến trình Linux, A log `ACK_VERIFIED seq=1` và `NATIVE_INVOCATION_REPORT_VERIFIED seq=1`; B log `REMOTE_E3_GAME_ACTION_INVOKED=1 seq=1` và `NATIVE_INVOCATION_REPORT_SENT=1 seq=1`. *Đây là mock callback/native; không chứng minh RAGE gameplay trên iPhone.*

## Tái lập trên Linux

```bash
# Cần clang + gcc + Python3 + libssl-dev/OpenSSL
cd e3_hardened
CC=clang RBP_IPA_PATH=/path/to/GTAV-v13.3.ipa RBP_GTA5_PATH=/path/to/GTA5 bash tools/run_phase3_checks.sh
CC=gcc RBP_IPA_PATH=/path/to/GTAV-v13.3.ipa RBP_GTA5_PATH=/path/to/GTA5 bash tools/run_phase3_checks.sh
```

Không có IPA, vẫn chạy host checks; chỉ bỏ qua một số kiểm tra tĩnh phụ thuộc binary gốc. **Tuyệt đối không đưa file IPA hoặc config khóa riêng lên GitHub công khai.**

## Build iPhoneOS (macOS/Xcode)

```bash
bash ios/build_probe_macos.sh 0  # E0: chỉ kiểm thử script loader/tick
bash ios/build_probe_macos.sh 1  # E1: local HUD native
bash ios/build_probe_macos.sh 3  # E3: diagnostic UDP -> native -> HMAC invocation report
```

File tạo ra là dylib **CHƯA KÝ**, cần tích hợp và ký hợp pháp cùng ứng dụng v13.3. Bắt đầu từ E0, yêu cầu log callback thật. Chỉ thử E1 khi E0 chạy ổn. Chỉ thử E3 với **hai iPhone kiểm thử được phép, cùng LAN**, config sinh riêng, không sử dụng ngoài môi trường test. `tools/make_two_phone_configs.py` sinh A/B configs; config này không phải RAGE Online session và không vượt NAT. Nếu ScriptHook bị tắt trong Online, phải ghi BLOCKED và không suy luận đã hoạt động.

## Chỉ tiêu kết luận

- **Host E3:** PASS, nhưng chỉ xác nhận integration với mock.
- **iOS dylib:** CHƯA BUILD; linux clang tạo ARM64 .o chứ không tạo IPA.
- **iPhone E0/E1/E3, RAGE sender/session, Roleplay:** CHƯA XÁC MINH.
- **Game v13.3 gốc:** không sửa binary, không patch IPA.

**Ưu tiên thực tiếp theo**: dùng macOS runner khi được cấp phát hoặc máy Mac có Xcode, ký/cài E0 rồi lấy log. Sau E0, E1 HUD và E3 hai iPhone; tiếp tục PR#16 chỉ khi có real receive-context. Không bật còng tay/chỉnh máu/xe với mức chứng minh hiện tại.
