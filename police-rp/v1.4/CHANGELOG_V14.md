# Police RP Only v1.4 — Xác minh việc nạp dylib trên iOS (chưa có gameplay)

Ngày 12/11/2026. Nền: GTA V iOS v12 **thường**; không mở Menyoo/SHV Online, không sửa server.

## Thay đổi so với v1.3

1. `Diagnostics/PoliceRPProbe.c` ghi marker tối giản vào `Documents/PoliceRPProbe-v14.txt` **nếu** iOS cho phép ghi, đồng thời ghi stderr. Marker chứa đúng phiên bản, trạng thái UUID, `hooks=0`, `network_events=0`, `police_gameplay=0`. Không thu IP/ID người chơi.
2. `Tools/check_prp_probe_log.py` đọc marker, trả `LOADER_VERIFIED`, `FAILED_CHECK` hoặc `MISSING_MARKER`. Báo cáo nạp dylib **không** chứng minh Police RP có thể bắt người.
3. `Tools/inject_prp_probe.py` kiểm tra thêm `LC_ID_DYLIB` (đúng install_name), từ chối entry ZIP trùng lặp, đóng gói dylib với quyền Unix `0755`.
4. Workflow GitHub Actions `build-prp-v14-probe-ios.yml` chuẩn bị dylib bằng Xcode/macOS; giữ kết quả 7 ngày, đính kèm công cụ kiểm tra marker. Không upload IPA có bản quyền vào GitHub.
5. Bổ sung kiểm thử offline: parser, sai UUID, marker cũ, metadata Mach-O, kiểm tra nguyên vẹn tệp ZIP & quyền tệp.

## Những gì KHÔNG được thực hiện

- Không có native hook vào vòng cập nhật GTA5.
- Không có mạng Police RP thật hoặc `MPJ2`/`PRC1` trong game.
- Không tạo, di chuyển, khống chế, còng người chơi trên iPhone.
- Không có bản IPA đã tích hợp hoặc ký; chưa chạy GitHub Actions/macOS hay iPhone.

## Điều kiện để tiếp tục sang runtime hook

Phải có `PoliceRPProbe.dylib` iOS hợp lệ từ workflow, tạo IPA thử với `inject_prp_probe.py`, ký IPA, chạy thử trên thiết bị và xuất được `PoliceRPProbe-v14.txt` có `dylib_loaded=1 gta5_uuid_verified=1`. Nếu không có marker, **không** coi là thành công; rà ký lại và log crash trước khi chạm engine.
