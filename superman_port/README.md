# Superman Native — GTA V iOS v11.4 / CustomKeys R7 (thử nghiệm)

**Trạng thái:** bản dựng lại độc lập từ mô tả tính năng và tệp cấu hình của mod
Superman by TamedMods. **Chưa thể tuyên bố tương thích 100% hay chạy full.**
Tệp `Superman.asi` gốc là binary Windows x86-64, không thể chạy trực tiếp trên
iOS ARM64. Đây là mã C++ mới để build thành plugin `SupermanR6.shv.dylib`
theo giao diện ScriptHookV iOS; *không phải* file `.asi` đã chuyển đổi.

## Chức năng được triển khai trong mã

| Nút | Chức năng | Hiện trạng |
| --- | --- | --- |
| F10 | Bật/tắt Superman | Kiểm thử logic host đạt |
| Space (giữ) | Bay, điều khiển WASD, tăng/giảm độ cao, tăng tốc Shift/LCtrl | Kiểm thử logic host một phần |
| R | 5 kiểu laser với màu/particle khác nhau, raycast và sát thương | Kiểm thử logic host một phần |
| Numpad 1–5 / 0 | Chọn/chuyển laser | Mã hoàn tất; chưa thử trên máy |
| G / H | Hơi thở băng / hơi thở mạnh | Mô phỏng bằng native/game particle |
| V / T / B | Vỗ tay sóng xung kích / xoáy / đập đất | Mô phỏng một phần |
| F | Nhấc và ném xe gần nhất | Mô phỏng một phần |
| F8 | Bùng nổ năng lượng | Mô phỏng một phần |
| K, chuột trái/phải, U/Z/L | Chế độ đánh, khóa mục tiêu, các đòn đặc biệt | Mô phỏng một phần |
| N / Y | Bộ lọc nhìn đêm (thay thế x-ray) / làm chậm thời gian | Mô phỏng một phần |

VFX sử dụng native `DRAW_LINE`, `DRAW_LIGHT_WITH_RANGE`, `START_PARTICLE_FX_*`
và hiệu ứng của GTA V; không có bảo đảm chúng giống chính xác bản Windows.
Âm thanh sử dụng `AVAudioPlayer`, tải file WAV tại `Documents/Superman_SFX`
hoặc thư mục pack cùng tên. **Không đóng gói lại 19 WAV của tác giả.**
Người dùng cần tự chép các WAV từ bản mod đã có quyền sử dụng.

Các khả năng **chưa được tái tạo đầy đủ**: animation nguyên bản, x-ray thật xuyên
vật thể, telescope/super hearing, bullet deflection, vật lý hàng loạt trên
mọi NPC, hầu hết 200+ tùy chọn `Superman.ini`, tính ổn định với script khác.
Không coi đây là bản phát hành hoàn chỉnh.

## Điều kiện bắt buộc

1. Cài bản IPA **CustomKeys R7** (bản này sửa cầu nối phím trong R6: ở bản
   cũ `iosKeyIsDown` là hàm *đọc*; R7 ghi trạng thái phím vào cùng bộ nhớ
   để các script đọc được). IPA R7 chưa kiểm thử trên iPhone.
2. Trong launcher, bật ScriptHookV tương ứng với GTA V. **Không chạy mod trong
   GTA Online.** Plugin chủ động ngừng tính năng khi bắt đầu phiên Online.
3. Tạo plugin ARM64 trên GitHub Actions của bạn (xem bên dưới); compiler không
   có sẵn trên môi trường kiểm thử này. **Chưa có `.shv.dylib` được build.**
4. Sau khi GitHub Action thành công, đưa `SupermanR6.shv.dylib` vào cùng thư mục
   script hook pack nơi đang có `Menyoo.shv.dylib`. Nếu launcher có chức năng
   import ZIP ScriptHook thì mở pack của bản GTA V tương ứng và thêm tệp đó;
   đường dẫn cụ thể tùy cấu trúc bản port trên máy.
5. Có thể chép tệp `Superman.ini` gốc vào `Documents/Superman.ini`; bản viết lại
   chỉ đọc các mục `Keys`, `General`, `Flight`, `Landing`, `Jump`, `Laser1`,
   `BulletTime` được nêu trong mã. Các mục còn lại không đổi hành vi.

## Build trên GitHub bằng iPhone

Tải ZIP nguồn, giải nén và tải nguyên cấu trúc vào root repo GitHub:

```text
.github/workflows/build-superman-ios.yml
superman_port/SupermanR6.cpp
superman_port/SupermanAudio.mm
superman_port/shv_api.hpp
superman_port/libScriptHookV.tbd
superman_port/build_ios.sh
superman_port/test_host.cpp
superman_port/test_Superman.ini
```

Vào **Actions → Build Superman Native for GTA V iOS R7 → Run workflow**.
Nếu build thành công, vào run mới nhất → **Artifacts** → tải
`SupermanR6-shv-dylib-ARM64-TEST`. Giải nén lấy `.shv.dylib` rồi thêm vào
ScriptHook pack. Chạy thử **chỉ trong chế độ chơi đơn** và lưu log/crash nếu lỗi.
Với plugin mới, bạn có thể cần ký lại hoặc nhập pack theo cơ chế của launcher;
không tự thay thế các framework gốc trong IPA.

## Kiểm thử đã thực hiện

- Compile C++17 host `-Wall -Wextra -Wpedantic -Werror`: đạt.
- Test giả lập: toggle F10, Space khởi động bay sau thời gian giữ, gửi native
  velocity, tia laser và hạt VFX, tắt và giải đăng ký script: đạt.
- Test parser một số phím và tùy chọn tệp INI: đạt.
- Mã ARM64 R7: kiểm thử mô phỏng input, 84 phím và kiểm tra cấu trúc IPA đạt.
- **Chưa được test:** build với Apple SDK, liên kết `.tbd`, game tick trên iOS,
  đồ họa thực tế, luồng âm thanh, mức RAM/FPS và tương thích mọi thiết bị.

## Quyền tác giả

Đây là mã độc lập phục vụ nghiên cứu tương thích. Không kèm theo `Superman.asi`,
`Superman.ini` nguyên bản hoặc bất cứ WAV nào của TamedMods; không đại diện
hay tuyên bố là bản phát hành được tác giả mod chứng nhận.
