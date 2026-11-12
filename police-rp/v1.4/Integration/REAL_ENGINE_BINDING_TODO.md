# Những callback RAGE phải được xác minh trước khi ghép IPA

`prp_transport_port.c` là adapter có dependency injection, KHÔNG phải hook tự động. Một developer có quyền truy cập engine/source hoặc debugger thiết bị cần cung cấp:

1. **Game frame**: callback trong `MacportOnlineUpdate`/sandbox script hợp lệ, bảo toàn context/script thread gốc. Gọi `prp_port_frame()` sau khi lấy snapshot đáng tin và trước khi trả điều khiển.
2. **Thông tin local**: `read_snapshot` phải xác minh session-id, host-id, local network player-id, peer-id, nghề native 0..2, on_shift, vị trí và thời gian monotonic. Không nhận các giá trị này từ mạng chưa xác thực hoặc INI.
3. **Kênh Police RP riêng**: `send_private` phải gắn vào một event type/route có xác thực của game, không chiếm `MPJ2` (loại nhiệm vụ gốc 0xAE). Kênh nhận cung cấp sender/session từ metadata transport đã được xác thực, sau đó gọi `prp_port_deliver()`.
4. **Hành động ped**: callbacks chỉ sửa nhân vật do CHÍNH máy điều khiển, không ghi trực tiếp remote Ped; áp dụng hạn chế điều khiển mỗi khung hình; hủy hạn chế khi disconnect/lỗi.
5. **Opt-in**: mọi người bị ảnh hưởng phải tự bật tham gia Police RP; không can thiệp người dùng v12 thường hoặc server GTA Online gốc.
6. **Re-sign + kiểm thử iOS**: bundle executable + thư viện nhúng phải có chữ ký phù hợp; ký lại IPA sau khi sửa executable hoặc thêm framework. Kiểm thử 2 máy iPhone trong phòng riêng và kiểm soát lỗi crash/giật.

Giới hạn hiện tại: mới có ứng viên `MacportSandboxNative -> MacportOnlineUpdate`, `MacportJobSend -> CScriptedGameEvent` và parser MPJ2. Chưa thể chứng minh đủ yếu tố để tạo hook.
