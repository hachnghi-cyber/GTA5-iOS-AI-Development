# Superman Standalone — GTA V iOS v11.3 (thử nghiệm)

Đây là **bản mod riêng dạng ScriptHookVDotNet3 DLL**, viết lại độc lập.
KHÔNG phải `Superman.asi` Windows gốc, không chỉnh sửa hoặc ghép IPA.

## Tương thích

- Chạy nhờ ScriptHookV .NET được nạp sẵn trong GTA V iOS v11.3.
- Chỉ sử dụng trong **GTA V Story Mode (chơi đơn)**; ở Online mod tự tắt.
- Tạo DLL bằng GitHub Actions qua `.github/workflows/build_superman_standalone.yml`.
- Mã nguồn dùng API SHVDN3 3.6.0/net48. Port iOS có thể khác API gốc:
  **chưa xác minh bằng bản build và chưa thử trên iPhone**.
- Các lệnh J/K/L/M chỉ hoạt động nếu bản port chuyển sự kiện bàn phím đến
  ScriptHookVDotNet. Bạn có thể thử bàn phím Bluetooth trước; với C+ của bản
  trước, cần thiết lập map J/K/L/M và kiểm tra bridge tương thích.

## Cách cài sau khi BUILD THÀNH CÔNG

1. Trong GitHub Actions, tải artifact `SupermanStandalone-v11.3-IMPORT.zip`.
2. Trên launcher GTA V iOS v11.3, vào **Mods > ScriptHook > Import Script**;
   chọn file ZIP chứa `SupermanStandaloneSHVDN.dll`.
3. Khởi động lại game. Vào **GTA V > Story Mode**, không chọn GTA Online.
4. Dùng bàn phím hoặc các phím ảo đã được cấu hình để thử.
5. Nếu script không hiện, gửi `ScriptHookVDotNet.log`, `posthook.log` và
   `run.log` sau khi vào Story Mode.

Không đưa `Superman.asi` vào ZIP: launcher có cơ chế bỏ qua `.asi` Windows.
Không tự nhập `ScriptHookVDotNet3.dll` gốc trong NuGet: game đã có API
riêng, chép đè có thể làm hỏng mod đang chạy.

## Phím điều khiển

| Phím | Tác dụng |
|---|---|
| J | Bật/tắt Superman (mặc định tắt) |
| K | Bật/tắt bay |
| L (giữ) | Tia Heat Vision màu đỏ-vàng, sát thương giới hạn |
| M | Sóng xung kích cự ly 11m, hồi 2,4 giây |
| Joystick di chuyển | Tiến/lùi/trái/phải khi bay |
| Nhảy / Space | Bay lên |
| Cúi người | Bay xuống |
| Shift (giữ) | Bay nhanh hơn |

## Giới hạn của phiên bản này

- Không tích hợp nút riêng vào giao diện: file .NET DLL không cài đặt UIKit
  và không làm thay đổi cấu trúc IPA. Dùng C+ hoặc bàn phím đã có.
- Không có animation Superman chính hãng, âm thanh SFX hoặc laser VFX từ
  `Superman.asi` gốc. Tia hiện tại chỉ vẽ đường sáng và đạn giới hạn.
- Không chạm dữ liệu/nhân vật trong chế độ Online.
- Nếu runtime ném ngoại lệ, script tự dừng để tránh lặp lỗi.

## Đối chiếu mã nguồn

Sử dụng các API `Script`, `Game.IsKeyPressed`, `Game.IsControlPressed`,
`GTA.Native.Function`, `World.GetNearbyPeds` của thư viện
SHVDN3. Nguồn tham khảo: https://github.com/scripthookvdotnet/scripthookvdotnet

**Kiểm thử hiện tại:** cấu trúc nguồn và workflow đã được kiểm tra tĩnh.
Chưa có thư viện DLL được biên dịch thành công trên GitHub Actions.
Không được coi thư mục này là gói mod có thể nhập trực tiếp trước khi có DLL.
