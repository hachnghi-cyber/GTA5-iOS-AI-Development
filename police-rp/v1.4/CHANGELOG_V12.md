# GTA V iOS v12 – Police RP ONLY v1.2 (12/11/2026)

## Đã triển khai

- Thêm `Integration/prp_transport_port.{h,c}`: lớp ghép hai chiều cho `PRP_GameBridge`, codec PRC1 244 byte, và bộ định tuyến sự kiện riêng của Police RP. Chỉ chấp nhận metadata `session_id`, `sender_id`, `authenticated` do **engine RAGE xác minh**. Không tạo hoặc mở socket.
- Chỉ khi event được phân loại từ đường **Police RP riêng** mới phân tích PRC1. Sự kiện nguyên bản (`MPJ2`) chuyển tiếp không thay đổi.
- Lệnh về nhân vật chỉ áp dụng khi `prp_port_frame()` được gọi từ *game thread*. Network dispatcher chỉ thêm gói hợp lệ vào hàng đợi giới hạn.
- Test `Integration/test_transport_port.c` mô phỏng 2 thiết bị và 25 kiểm tra: opt-in, chủ phòng kiểm tra lệnh, nhận gói giả danh, mất xác thực, giữ nguyên event game, còng, giải phóng khi mất phiên.
- Thêm workflow Xcode tạo bundle `PoliceRPOnly.framework` unsigned. Không đặt DLL/dylib thẳng vào IPA khi thiếu chữ ký và điểm gọi. Chưa chạy workflow này trên macOS.
- Tạo 9 tệp đối tượng Mach-O ARM64 trên Linux (không phải thư viện hoàn chỉnh).

## Chưa có – Điều kiện bắt buộc trước IPA

- `read_snapshot()` nối với trạng thái phiên, net player ID, nghề cảnh sát, vị trí đã được game xác thực ở runtime. Hiện callback mô phỏng.
- `send_private()` thực sự gửi sự kiện qua kênh RAGE đã xác thực và có đường nhận Police RP riêng; **không** được tái sử dụng `MPJ2` hay đọc sender từ payload.
- Điểm gọi `prp_port_frame()` trên game-thread đã kiểm chứng, bảo toàn callback Online gốc.
- Điều khiển nhân vật/hoạt ảnh, phát hiện mục tiêu gần nhất, xe áp giải, nhà tù.
- Biên dịch trên Xcode, ký code và kiểm thử từ 2 iPhone. Chưa tạo IPA dùng được.

**Gói này chỉ có mã nguồn/kiểm thử, không phải mod có thể cài. IPA v12 thường chưa được sửa.**
