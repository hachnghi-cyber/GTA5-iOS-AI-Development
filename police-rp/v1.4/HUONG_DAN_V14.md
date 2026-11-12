# HƯỚNG DẪN KIỂM TRA POLICE RP v1.4 TRÊN IPHONE

**Đây là bài thử nạp thư viện, chưa phải mod cảnh sát bắt người Online.** Không cài lên bản v12 chính đang sử dụng nếu chưa sao lưu dữ liệu; tuyệt đối không đăng IPA gốc lên repository GitHub công khai.

## A. Build thư viện bằng GitHub Actions

1. Đưa mã nguồn từ ZIP lên repository GitHub (giữ nguyên thư mục `Diagnostics`, `Tools`, `Tests` và `.github/workflows`).
2. Mở **Actions** → **Police RP v1.4 - noninvasive loader diagnostic** → **Run workflow**.
3. Khi workflow chạy thành công, tải artifact `PRP-v14-iOS-arm64-loader-PROBE-NOT-GAMEPLAY`. Trong đó cần có `PoliceRPProbe.dylib`, `load_commands.txt`, `sha256.txt`.
4. Nếu Actions báo build fail, lấy log; không tự đổi target sang macOS hoặc Simulator để vượt qua kiểm tra.

## B. Tạo IPA thử nghiệm (thực hiện cục bộ trên máy tính)

Cần Python 3, IPA v12 thường chính xác (không phải bản Menyoo Online), và dylib iOS vừa build.

```sh
python3 Tools/inject_prp_probe.py 'GTAV-v12(1).ipa' 'PoliceRPProbe.dylib' --out 'GTAV-v12-PRP-v14-DIAG-UNSIGNED.ipa'
```

Công cụ từ chối sai SHA/UUID, sai nền tảng dylib và tệp đích đã tồn tại. Gói xuất ra **chưa ký**, không chạy ngay trên iPhone. Ký lại cả app và thư viện nhúng bằng công cụ cài đặt hợp lệ của bạn.

## C. Kiểm tra trên iPhone

1. Sao lưu dữ liệu game và giữ lại v12 thường để khôi phục nếu cần.
2. Cài IPA chẩn đoán đã ký lại. Nếu không khởi động được, lấy crash log và dừng thử.
3. Mở game một lần, sau đó vào ứng dụng **Tệp (Files)** → **Trên iPhone của tôi (On My iPhone)** → thư mục GTA V/GTAV → tìm tệp `PoliceRPProbe-v14.txt` (nếu game expose Documents).
4. Nếu không nhìn thấy trong Tệp, kiểm tra system console hoặc phương thức truy cập Documents đang dùng. **Không thấy tệp chưa chứng minh dylib không nạp** (có thể lỗi quyền ghi/hiển thị thư mục).
5. Nội dung mong đợi: `[PRP_DIAG_V14] dylib_loaded=1 gta5_uuid_verified=1 hooks=0 network_events=0 police_gameplay=0`.
6. Có thể gửi tệp TXT vào chat để phân tích hoặc dùng:

```sh
python3 Tools/check_prp_probe_log.py PoliceRPProbe-v14.txt
```

Chỉ khi xác nhận thư viện nạp ổn định mới có cơ sở kiểm tra vòng cập nhật game. **Chưa thử bắt người trong Online bằng bản chẩn đoán.**

## Tránh nhầm lẫn

Mã nguồn `P2P`/`Integration` ở các bản trước chỉ vượt qua kiểm thử mô phỏng. Chúng **chưa kết nối** với giao thức Online của GTA5. Probe v1.4 cũng chưa có xử lý nghiệp vụ Police RP.
