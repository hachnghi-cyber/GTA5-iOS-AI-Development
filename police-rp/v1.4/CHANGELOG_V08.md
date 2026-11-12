# Police RP Only v0.8 — Änderungen / Changes / Thay đổi

## Đã triển khai

- Thêm `Integration/prp_mailbox.{h,c}`: hàng đợi nhận gói thông tin 56 byte có giới hạn 64 mục, tối đa 32 gói xử lý mỗi game-frame, phù hợp mô hình một/multi luồng nhận từ network và xử lý game state chỉ trên game thread.
- `prp_bridge_enqueue`: nhận metadata phiên và sender **được xác thực từ engine transport**, từ chối gói không xác thực, sai độ dài, từ sender/session rỗng. Không đọc các giá trị định danh từ payload gửi qua mạng.
- `prp_bridge_frame`: tự lấy gói khỏi hàng đợi, kiểm tra trùng phiên đã xác thực trước khi chuyển tiếp cho P2P core; queue tự xóa khi rời phiên / đổi chủ phòng.
- Sửa `PRP_OP_JAIL`: cả cảnh sát và người bị bắt phải ở gần nhau (tối đa 6m) tại khu giam giữ. Chỉ có cờ “ở đồn” không đủ.
- Thêm kiểm thử tràn hàng đợi, 2 producer chạy song song, wrong session, ungated auth và trường hợp bỏ tù khác vị trí.
- Thêm `Tools/inspect_v12_hook_sites.py` (READ-ONLY) xác nhận SHA-256/UUID và ghi lại byte tại 4 điểm nghi vấn để tiếp tục nghiên cứu native hook.
- Thêm `Tools/build_v08_arm64_objects.sh` và workflow GitHub Actions macOS/Xcode để build dylib iOS, CHƯA CHẠY trên Mac.

## Kết quả

- 33 bài test Python server đạt.
- 60 assertions P2P core + 25.000 đầu vào fuzz đạt.
- 21 assertions mô phỏng hai máy đạt.
- Engine binding và mailbox test đạt dưới AddressSanitizer/UndefinedBehaviorSanitizer.
- 6 Mach-O ARM64 object tạo thành công (shim compile only).
- IPA gốc và server GTA Online gốc vẫn nguyên vẹn; **không có IPA được vá**.

## Chưa giải quyết

1. Chưa tìm được hook game-thread hợp lệ cho bản GTA5 đã xác minh, nên chưa ai gọi `prp_bridge_frame` trong game.
2. Chưa kết nối `prp_bridge_enqueue` với sender/channel thực đã được chứng thực trong GTA5.
3. Chưa có client điều khiển ped/hoạt ảnh/xe/tù qua GTA native.
4. `ld64.lld` có mặt trên Linux nhưng trả về `This version of lld does not support linking for platform iOS`, nên chưa có dylib iOS đã liên kết; workflow macOS chưa được chạy.
5. Chưa có kiểm thử 2 iPhone. **Không cài ZIP này dưới dạng mod.**
