# GTA V iOS V10.3 — Camera/FOV experimental patch

Bản mã nguồn vá ARM64 thử nghiệm từ GTA V iOS V10.2.

## Nội dung
- `gtav_ui_camera_patch.s`: logic chèn các mục Trainer.
- `gtav_game_camera_patch.s`: logic camera xe và FOV ở dạng ARM64.
- `build_gtav_camera_experimental.py`: script build/binary patch theo đúng bản IPA đã kiểm tra.
- `verify_gtav_camera_experimental.py`: script kiểm tra tĩnh.
- `GTA-V10.3-Camera-Patch-Report.json`: báo cáo hash, offset và giới hạn.
- `GTA-V10.3-Huong-Dan-Thu-Nghiem.txt`: hướng dẫn thử nghiệm.
- `GTA-V10.3-Camera-Patch-Source.zip`: bản ZIP nguồn gốc, SHA-256 `cf52d1b262718fd1f2ebcf0e95b85213260ebf7ddf0695f1efc1c7f465f034e4`.

## Trạng thái
**Experimental / Unsigned / Not tested on iPhone.**
Đã có bản vá nhị phân thử nghiệm; chưa xác nhận chạy trên thiết bị thật. Không phải mã nguồn gốc của GTA V hay của bản port iOS. Không kèm IPA, executable, tài sản game, chứng chỉ hoặc khóa.

Các script sử dụng đường dẫn `/mnt/data` và các binary V10.2 khớp SHA-256; không thể chạy trực tiếp trên IPA khác nếu chưa điều chỉnh và kiểm tra lại. Xem báo cáo gốc để biết các giả định kỹ thuật, offset và rủi ro.
