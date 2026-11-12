# v1.0 — Bản nghiên cứu ARM64 + giao thức Police RP (12/11/2026)

## Phát hiện mới đã xác minh từ `GTAV-v12(1).ipa`

1. `CTheScripts::LaunchStartupScript` kiểm tra `MacportSandboxMode()` rồi mới `BL MacportSandboxProgram` tại `0x100e30584`.
2. `MacportSandboxProgram` dựng địa chỉ callback `MacportSandboxNative` (`0x100039e34`) bằng `ADRP/ADD`, đăng ký với `rage::scrThread::RegisterCommand` tại `0x100039dbc`.
3. `MacportSandboxNative` thực hiện `B` (nhảy đuôi) trực tiếp tới `MacportOnlineUpdate` tại `0x1000e01a0`. Đây là lý do quét mỗi lệnh `BL` ở v0.9 không thấy xref.
4. Bên trong `MacportOnlineUpdate`, tại `0x1000e5188` có `BL MacportJobsUpdate`. Do vậy có đường thực thi của nghề cảnh sát trong Online, nhưng chưa chứng minh callback chạy trong mọi phiên.
5. `MacportJobSend` dùng `CScriptedGameEvent` (vị trí lệnh gọi `0x1000f5f3c`), payload dài `0xF4` = **244 byte**, và magic **`MPJ2`**. Không phải tự động mở kênh Police RP.
6. Có các event RAGE `CStartNetworkPedArrestEvent` và `CStartNetworkPedUncuffEvent` (mã máy xác minh), nhưng chưa chứng minh chúng có thể khống chế **người chơi** Online.

Công cụ **chỉ đọc**, kiểm tra SHA-256 và UUID: `Tools/trace_v12_police_carrier.py` → `ARM64_SANDBOX_NETWORK_CARRIER_V12.json`.

## Đã bổ sung mã

- `Integration/prp_candidate_carrier.{h,c}`: bộ đóng gói Police RP 56 byte thành envelope 244 byte (độc lập, tag `PRC1`, CRC32 phát hiện lỗi hỏng dữ liệu, zero-padding). **KHÔNG** gửi vào mạng GTA thật.
- `Integration/test_candidate_carrier.c`: 22 assertions, kiểm tra gói hợp lệ, metadata xác thực do engine cấp, giả sender, giả session, dữ liệu hỏng và queue.
- `Tools/test_v10_carrier.sh`: biên dịch và chạy thử cùng ASan + UBSan trên Linux.
- Workflow macOS `build-prp-v10-ios.yml`: build dylib iOS ARM64 bằng Xcode SDK, **chưa được chạy**.

## Giới hạn trung thực

- Gói `MPJ2` đang được GTA dùng cho tính năng Online khác; **không thay thế**.
- Envelope mới chỉ có mã đóng gói và hàng đợi; chưa nối `CScriptedGameEvent` send/receive hay xác thực peer từ engine. CRC32 không cung cấp xác thực mạng.
- Không có point-injection hoặc signed IPA. Không có còng tay trong game, không có hoạt ảnh hoặc đồng bộ đã xác minh trên 2 iPhone.
- IPA GTA5 gốc không sửa; không mở khóa Menyoo/ScriptHook Online; không sử dụng server Police RP TCP.

## Việc tiếp theo

1. Xác minh lớp nhận `CScriptedGameEvent` của GTA v12 và nguồn metadata peer đã được engine xác thực; tìm message namespace không xung đột với `MPJ2`.
2. Thiết lập hook/callback game-thread đã kiểm tra ABI, lưu nguyên lệnh gốc, rollback an toàn trên đúng hash v12.
3. Build thật bằng workflow macOS/Xcode và triển khai test nhỏ chỉ ghi log; sau đó mới bật thao tác còng và thử 2 iPhone.
