# Superman Standalone v11.3 — bản mở rộng thử nghiệm (iOS)

**Bản mod độc lập C# ScriptHookVDotNet3**; không cần chỉnh IPA GTA V v11.3.
Không chứa, không tải và không chạy `Superman.asi` (Windows x64) của TamedMods.
Mã này do dự án viết mới để mô phỏng các tính năng nổi bật của mod PC.

> **Chưa đạt mức tương đương 100% bản PC.** Chưa được biên dịch và chạy thử
> trên v11.3 trong phiên làm việc này. Các tính năng bên dưới là mã **thử nghiệm**;
> hiệu ứng 3D, animation và âm thanh gốc cần công việc port thêm.

## Phím PC và nút C+ của launcher

| Phím | Tính năng trong mã thử nghiệm |
|---|---|
| **F10** | Bật/tắt Superman; tự khôi phục trọng lực, hiệu ứng tạm, time scale |
| **Space** (bấm) | Siêu nhảy đơn giản |
| **Space** (giữ 250 ms) | Cất cánh; dùng Space / Ctrl để lên / xuống |
| **W/A/S/D**, **Shift** | Điều hướng và tăng tốc khi bay (joystick dùng điều khiển gamepad) |
| **R** | Bắn loại tia đang chọn |
| **NumPad 0** | Chuyển 5 tia: Heat, Plasma Arc, Solar Flare, Pulse Cannon, Cryo |
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

Các nút **C+** trên màn hình chỉ là trình gán phím có sẵn của GTA V iOS:
phải gán đúng F10/Space/R/NumPad0... để mã mod nhận được. Mod này **không**
tự tạo nút nổi và không thay đổi bố cục cảm ứng mặc định.

## Tự động build bằng GitHub Actions (không cần tự tạo yml)

1. Mở ZIP mã nguồn được cung cấp trong cuộc trò chuyện này.
2. Tải lên repository GitHub **cả hai đường dẫn**, giữ nguyên cấu trúc:
   - `.github/workflows/build_superman_standalone.yml`
   - `superman_standalone_v113/` (gồm `.csproj`, ba `.cs`, README và ma trận port).
3. Vào **Actions → Build Superman standalone v11.3 expanded → Run workflow**.
4. Khi build xanh, tải artifact `SupermanStandalone-v11.3-Expanded`.
5. Artifact GitHub là ZIP bọc ngoài: giải nén **một lớp** lấy đúng
   `SupermanStandalone-v11.3-Expanded-IMPORT.zip` chứa trực tiếp
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
- Gửi lại `ScriptHookVDotNet.log`, `posthook.log`, `run.log` nếu không tải DLL.

Xem [PORT_MATRIX.md](PORT_MATRIX.md) để biết chiêu nào đã viết mô phỏng và
chiêu nào còn thiếu so với TamedMods.

API tham khảo: https://github.com/scripthookvdotnet/scripthookvdotnet
