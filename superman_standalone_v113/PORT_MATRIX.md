# Superman v11.3 — Ma trận port (10/11/2026)

Đây là dự án **viết lại độc lập** bằng C# ScriptHookVDotNet3 cho GTA V iOS.
Không chứa mã Windows từ `Superman.asi`; không chỉnh sửa IPA. Tính năng ghi
"đã viết" nghĩa là **có mã thử nghiệm**, KHÔNG nghĩa là đã chạy trên iPhone.

| Nhóm | Trạng thái mã thử nghiệm | Còn thiếu để tương đương TamedMods |
|---|---|---|
| F10 bật/tắt, Space giữ/tap, WASD/joystick, Shift/Ctrl | Đã viết | Hover animation, hạ cánh tự động, collision, bank/pitch, sonic boom |
| 5 tia (Heat, Plasma, Solar, Pulse, Cryo) | Đã viết mô phỏng màu và tác dụng khác nhau | Raycast chính xác, cháy/đen vật thể, lan điện, EMP điện tử, cryo VFX 3D |
| Nhấc/ném xe (F) | Đã viết bằng lực/velocity | Nhấc prop, animation nâng/cầm/ném, collision an toàn |
| G đóng băng, H đẩy, T lốc, V/B shockwave | Đã viết mô phỏng vật lý | B còn dùng shockwave thay vì ground pound, particle 3D, âm thanh, ragdoll đồng bộ, cooldown/overheat đầy đủ |
| F8 Solar Flare | Đã viết EMP + hiệu ứng nổ | Xóa khu vực đúng gốc, hiệu ứng quang học và điện tử |
| K, U/Z/L combat | Chỉ đẩy mục tiêu trong nón ngắm | Lock-on theo crosshair, homing melee, combo, takedown/piledrive animation |
| Y bullet time | Giảm `SET_TIME_SCALE` | Simulated bullet tracers, đóng băng/đánh bật/phá đạn |
| N X-ray | Hiệu ứng thermal thay thế | X-ray đúng nghĩa qua vật cản |
| P super hearing | Hiện số NPC trong bán kính | Radar highlight và marker xuyên tường |
| O telescope | Chưa triển khai | Camera zoom mượt và restore FOV |
| 19 tệp WAV gốc | Chưa phát | Cầu nối audio iOS, quyền tái phân phối tài nguyên |
| File `Superman.ini` >200 mục | Chưa đọc | Cấu hình runtime, key overrides, từng hiệu ứng và hiệu năng |
| Online | Tự tắt khi session active | Kiểm thử trên nhiều chế độ và restore an toàn |

Lưu ý: quét bằng 9 mẫu native chỉ tìm **một số** NPC/xe trong vùng, không
bảo đảm mỗi mục tiêu đều chịu hiệu ứng. Đây là đánh đổi tạm thời để tránh
đọc các pool địa chỉ bộ nhớ Windows trên iOS ARM64.

## Kiểm thử bắt buộc trước khi gọi là hoạt động

1. **Build**: GitHub Actions biên dịch net48, nhận đúng `SupermanStandaloneSHVDN.dll`.
2. **Import**: launcher `MOD > ScriptHook > IMPORT SCRIPT` nhận ZIP, không từ chối.
3. **Load**: trong `ScriptHookVDotNet.log` có lớp `SupermanStandaloneMod.SupermanStandalone`.
4. **Input**: F10/Space/R/Num0/F/G/H/V/T/Y/L/Z/U hoạt động qua bàn phím;
   riêng C+ cần xác minh sự kiện được chuyển từ touch đến .NET.
5. **Gameplay**: mỗi năng lực chạy 10 lần, đổi nhân vật, vào/ra xe, chết,
   thoát menu; không treo render, không rò rỉ handle/particle.
6. **Restore**: tắt F10 trong khi bay/bullet time/đang nâng xe; trọng lực,
   timescale, camera, invincibility, đóng băng và khả năng lái được khôi phục.
7. **Online**: mod ngừng tác dụng; không thao tác vào nhân vật/xe từ xa.

## Những rủi ro cần loại bỏ

- `SHVDN.NativeMemory` trên bản iOS có thể khác Windows. Đã thay
  `World.GetNearbyPeds/Vehicles` bằng `GET_CLOSEST_PED/VEHICLE` với 9 điểm mẫu
  để giảm phụ thuộc offset; **đổi lại khả năng tìm nhiều NPC/xe bị giới hạn**.
  `Ped.CurrentVehicle` cũng được tránh, dùng native để lấy handle.
- Bản C# hiện dùng nhiều native của GTA; một số có thể chưa được bridge hỗ trợ
  trong v11.3. Catch lỗi và giữ log; không công bố "100% tương thích".
- Một số phép thử tạo vụ nổ/tác động lực: **chỉ test Story Mode với save dự phòng**.
- Quyền của tác giả TamedMods không cho phép phát hành lại bản gốc tùy ý.
  Gói mã nguồn phát hành chỉ chứa code độc lập; không chứa `.asi` hoặc WAV.

Nguồn kỹ thuật: https://github.com/scripthookvdotnet/scripthookvdotnet
Mã nguồn tham khảo được phép theo MIT: https://github.com/Mouataz86/SimpleMenu
