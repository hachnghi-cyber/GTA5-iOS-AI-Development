# Tài khoản Police RP trên iPhone

Trong GTA, chọn **RP riêng → Tạo tài khoản**. Nhập tên gồm 3–32 chữ cái Latin, chữ số hoặc dấu gạch dưới. Nhập mật khẩu từ 15 đến 128 ký tự và nhập lại để xác nhận. Khi tạo thành công, chọn **Tham gia RP**.

Ở lần chơi sau, chọn **RP riêng → Đăng nhập** bằng tài khoản đã tạo. **Rời RP** rút sự đồng ý tham gia. **Đăng xuất** kết thúc kết nối của tài khoản.

Bản iPhone cần có bảng tài khoản và hồ sơ RP do server cấp cho lượt chơi hiện tại. Mỗi hồ sơ danh tính RP dùng cho một tài khoản.

## Thử beta R85 với hai bản GTA trên một iPhone

1. Ký và cài IPA R85 Private RP Beta cho GTA cài riêng. Nhập cùng IPA vào LiveContainer. Khi cài cập nhật, giữ dữ liệu của cả hai bản.
2. Cho iPhone và laptop vào cùng Wi-Fi. Trên laptop thử nghiệm, mở `Thu-Beta-2-GTA.cmd`. Khi công cụ báo đã đọc lại cả hai hồ sơ, mở lại hai bản GTA. Mỗi lượt server kéo dài 20 phút. Chạy lại lệnh khi lượt hết hạn hoặc nếu cài lại làm mất hồ sơ.
3. Trong **RP riêng**, đăng ký hoặc đăng nhập bằng hai tài khoản khác nhau. GTA cài riêng dùng RP ID 11 (cảnh sát), LiveContainer dùng RP ID 22 (công dân). Bấm **Tham gia RP** ở cả hai.
4. Trong GTA cài riêng, mở **Người chơi RP** và kiểm tra có cả 11 và 22. Bấm **Chào hỏi**, xem thông báo bên LiveContainer. Gửi **Yêu cầu giấy tờ** theo chiều ngược lại. Nếu hiện **Đang chờ người chơi kia tham gia**, đưa bản kia ra trước, kiểm tra tài khoản và trạng thái tham gia.

Đăng nhập và chào hỏi dùng server RP trên laptop. Có thể thử các nút này trong Sandbox. Để thử tuần tra ở đồn, vào phòng GTA chỉ mời và đến Mission Row. Bài thử hai ứng dụng trên một máy chỉ xác nhận hai client trong điều kiện đa nhiệm của máy đó.

Trên laptop Windows khác, chạy từ `v133_interaction`. Tham số `DeviceId` dùng cho iPhone đã ghép đôi qua Wi-Fi. Khi cắm một iPhone qua USB, có thể bỏ tham số đó.

```powershell
.\tools\start_paired_beta.ps1 -ServerPython C:\rp\server\Scripts\python.exe -DevicePython C:\rp\device\Scripts\python.exe -DataFolder C:\rp\private -Library C:\rp\rp_authority.dll
```

Python của server cần `cryptography` và `aiohttp`. Python giao tiếp iPhone cần `cryptography` và `pymobiledevice3` (đã thử với 11.56.0). Thư mục dữ liệu nằm ngoài Git. Mỗi lần cấp hồ sơ, công cụ xác minh chứng chỉ hai vai trò và đọc lại tệp ở cả hai ứng dụng.
