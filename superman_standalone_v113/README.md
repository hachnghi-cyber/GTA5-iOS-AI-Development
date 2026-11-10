# Superman Standalone v11.3 — F10 duy nhất để bật/tắt (iOS)

**Bản mod độc lập C# ScriptHookVDotNet3**; không cần chỉnh IPA GTA V v11.3.
Không chứa, không tải và không chạy `Superman.asi` (Windows x64) của TamedMods.
Mã này do dự án viết mới để mô phỏng các tính năng nổi bật của mod PC.

> **Chưa đạt mức tương đương 100% bản PC.** Chưa được biên dịch và chạy thử
> trên v11.3 trong phiên làm việc này. Các tính năng bên dưới là mã **thử nghiệm**;
> hiệu ứng 3D, animation và âm thanh gốc cần công việc port thêm.

**Sửa lỗi build 10/11/2026:** `NativeNearby.cs` đã thay lời gọi constructor
`new Ped(handle)` và `new Vehicle(handle)` (không public trong SHVDN3) bằng
`Entity.FromHandle(handle) as Ped/Vehicle`, kèm kiểm tra `null`. Mục tiêu là
khắc phục hai lỗi `CS1729` từ GitHub Actions. Chưa xác nhận build xanh cho tới
khi chạy lại workflow và chưa xác nhận hành vi gần NPC/xe trên iOS.

## Phím PC và nút C+ của launcher

| Phím | Tính năng trong mã thử nghiệm |
|---|---|
| **F10** | Bật/tắt Superman; tự khôi phục trọng lực, hiệu ứng tạm, time scale |
| **Space** (bấm) | Siêu nhảy đơn giản |
| **Space** (giữ 250 ms) | Cất cánh; dùng Space / Ctrl để lên / xuống |
| **W/A/S/D**, **Shift** | Điều hướng và tăng tốc khi bay (joystick dùng điều khiển gamepad) |
| **R** | Bắn loại tia đang chọn |
| **Giữ Ngắm + Bắn** | Bắn laser dự phòng qua điều khiển cảm ứng/gamepad |
| **NumPad 0** | Chuyển 5 tia: Heat, Plasma Arc, Solar Flare, Pulse Cannon, Cryo |
| **Giữ Ngắm + Nạp đạn** | Chuyển tia dự phòng qua nút gamepad |
| **NumPad 1–5** | Chọn trực tiếp loại tia tương ứng |
| **F** | Nhấc xe gần người, bấm lại để ném theo hướng nhìn |
| **V / B** | Hai phím đều tạo sóng xung kích thử nghiệm; B chưa có hoạt ảnh đập đất |
| **G** | Đóng băng mục tiêu ngắm trong thời gian ngắn |
| **H** | Đẩy mục tiêu phía trước theo hình nón |
| **T** | Lốc xoáy đẩy vật thể xung quanh |
| **Y** | Bật/tắt thời gian chậm (bullet time đơn giản) |
| **N** | Bật/tắt nhìn nhiệt, **chưa phải X-ray xuyên tường** |
| **K** | Bật/tắt combat, rồi dùng U / Z / L đẩy mục tiêu |
| **P** | Hiển thị số NPC gần bạn (chưa có radar như PC) |
| **F8** | Chiêu Solar Flare diện rộng (EMP, lực đẩy, nổ nhẹ) |

**Dấu hiệu xác nhận DLL đã chạy**: vào Story Mode, dưới màn hình sẽ xuất hiện
`Superman DLL DA NAP | bam F10 de BAT` một lần. Nếu không thấy
dòng này, không thể khẳng định lỗi nằm ở F10: cần lấy `ScriptHookVDotNet.log`.

**F10 là phím duy nhất bật/tắt Superman**, không có nút hoặc tổ hợp bật khác.
Mod lắng nghe F10 bằng cả sự kiện `KeyDown/KeyUp` lẫn trạng thái phím;
không đổi tác dụng F10 và không tự bật khi vào game.
Các nút **C+** trên màn hình là trình gán phím của GTA V iOS, có thể **không**
truyền phím giả lập vào `ScriptDomain.IsKeyPressed` của SHVDN3. Vì vậy cần
kiểm tra log và thử F10 bằng bàn phím Bluetooth nếu F10 trên C+ không chạy.
Tổ hợp Ngắm + Bắn/Nạp đạn chỉ là cách dùng chiêu sau khi Superman đã bật.
Mod **không** tự tạo nút nổi, không sửa layout và không chỉnh IPA.

## Tự động build bằng GitHub Actions (không cần tự tạo yml)

1. Mở ZIP mã nguồn được cung cấp trong cuộc trò chuyện này.
2. Tải lên repository GitHub **cả hai đường dẫn**, giữ nguyên cấu trúc:
   - `.github/workflows/build_superman_standalone.yml`
   - `superman_standalone_v113/` (gồm `.csproj`, ba `.cs`, README và ma trận port).
3. Vào **Actions → Build Superman standalone v11.3 F10 only → Run workflow**.
4. Khi build xanh, tải artifact `SupermanStandalone-v11.3-F10-Only`.
5. Artifact GitHub là ZIP bọc ngoài: giải nén **một lớp** lấy đúng
   `SupermanStandalone-v11.3-F10-ONLY-IMPORT.zip` chứa trực tiếp
   `SupermanStandaloneSHVDN.dll`.
6. Trong launcher v11.3 chọn **MOD → ScriptHook → IMPORT SCRIPT**, chọn ZIP
   `-IMPORT.zip` rồi khởi động lại, chơi **Story Mode** để thử.

Nếu không nhìn thấy Actions: bảo đảm workflow được đặt trong **`.github/workflows/`
ở thư mục gốc repository** và đã commit lên nhánh mặc định. Không tạo tên
`build-custom.yml` mới khi workflow trên đã có.

## Giới hạn và xử lý lỗi

- **Không nhập `Superman.asi` gốc**: launcher iPhone sẽ bỏ qua plugin PE Windows.
- Script cần bridge ScriptHookVDotNet3 hoạt động; không phải mọi native có thể
  được GTA iOS port hỗ trợ. Nếu một chiêu mở rộng bị lỗi, mod cố gắng trở lại
  nhóm cơ bản; log ghi thông tin để sửa.
- Không có 19 WAV gốc: mã C# chưa có phát âm thanh iOS. Không phát hành lại
  tài nguyên bản quyền của tác giả TamedMods.
- Chế độ GTA Online: script **chủ động ngừng** khi phát hiện phiên mạng.
- Cần thử trên save dự phòng ở khu vực ít NPC để theo dõi crash.
- Nếu không nhận phím, thử **bàn phím Bluetooth** để phân biệt lỗi mod với
  lỗi ánh xạ C+ → `System.Windows.Forms.Keys`.
- Nếu có thông báo "DLL DA NAP" nhưng F10 không phản hồi ngay cả với bàn phím
  Bluetooth, gửi lại `ScriptHookVDotNet.log`: cần sửa đường nạp phím bàn phím
  vào `ScriptDomain` của bản port, không thể kết luận lỗi do mod.
- Gửi lại `ScriptHookVDotNet.log`, `posthook.log`, `run.log` nếu không tải DLL.

Xem [PORT_MATRIX.md](PORT_MATRIX.md) để biết chiêu nào đã viết mô phỏng và
chiêu nào còn thiếu so với TamedMods.

API tham khảo: https://github.com/scripthookvdotnet/scripthookvdotnet
