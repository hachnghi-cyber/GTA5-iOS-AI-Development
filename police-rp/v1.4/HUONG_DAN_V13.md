# Police RP Only v1.3 – Kiểm thử nạp dylib trên v12 thường

**Chưa phải mod Police RP có thể chơi.** Đây là bài thử an toàn tối thiểu để xác minh việc liên kết một thư viện mới vào GTA5. Giữ bản v12 thường và dữ liệu gốc đã sao lưu.

## Bước 1: Build probe bằng GitHub Actions (không tải IPA có bản quyền lên GitHub)

Từ thư mục mã nguồn này, đưa `Diagnostics/PoliceRPProbe.c`, `Tools/inject_prp_probe.py`, `Tests/test_v13_loader.py` và `.github/workflows/build-prp-v13-probe-ios.yml` lên repository của bạn.

Trong GitHub -> Actions -> **Police RP v1.3 - noninvasive loader diagnostic** -> **Run workflow**. Nếu runner Xcode hoàn tất, lấy artifact `PRP-v13-iOS-arm64-loader-PROBE-NOT-GAMEPLAY` và giải nén lấy `PoliceRPProbe.dylib`.

## Bước 2: Tạo IPA chẩn đoán trên máy tính

```sh
python3 Tools/inject_prp_probe.py 'GTAV-v12(1).ipa' PoliceRPProbe.dylib --out 'GTAV-v12-PRP-v13-DIAG-UNSIGNED.ipa'
```

Công cụ so khớp SHA256 và UUID của `GTA5`, kiểm tra dylib iOS ARM64, xác minh mọi file gốc khác không thay đổi. Xuất tệp báo cáo `*.verify.json`. Nó từ chối ghi đè bản IPA gốc.

## Bước 3: Kiểm thử thiết bị

Ký lại IPA bằng công cụ cài ứng dụng tương thích, sao lưu dữ liệu trước khi cài. Khởi chạy Story Mode trước; xem system log/console để tìm thông báo `[PRP_DIAG_V13] dylib loaded; GTA5_v12_UUID_verified=1; hooks=0; network_events=0`.

Nếu không thấy log hoặc app crash, **không thử Online**: lấy log từ console hoặc crash report và kiểm tra ký framework / LC_LOAD_DYLIB. Nếu khởi chạy ổn định, mới thử phòng Online riêng và kiểm tra game vẫn hoạt động bình thường. **Sự kiện probe xuất hiện không có nghĩa Police RP đã hoạt động**.

## Bảo vệ

- Không có mã sửa memory protection, không có hook, không chiếm `MPJ2`.
- Không cho Menyoo/ScriptHook hoạt động trong Online.
- Không có server TCP 7789.
- IPA thử nghiệm chưa ký, không dùng làm bản phát hành.

**Chưa thực hiện trên iPhone hoặc GitHub runner:** cần kết quả bài thử mới đi tiếp đến hook gọi thực tế.
