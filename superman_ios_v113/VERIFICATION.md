# Báo cáo kiểm tra trước khi build — Superman iOS v11.3 v0.1

Ngày: 10/11/2026

## Đầu vào đã kiểm tra

| Đầu vào | SHA-256 |
|---|---|
| GTA5 của `GTAV-v11.3(1).ipa` | `606aa87f9c22b40f167ae2bdf00ddf451b957801efb27169e38fa7af5c673aeb` |
| GTA5 của bản CustomTouch thử nghiệm | `0533fb5fd4c85c1741b6d42651ec64c196ba93834a6bdf7148cd1ca523776e6d` |
| `libgtacompat.dylib` v11.3 | `992148cae5866e20768b1e054075cbc7b9480731ffc3996a4a6f69d61177cb64` |

## Kết quả

- PASS: `g++ -std=c++17 -Wall -Wextra -O2 -c GameplayCore.cpp` — kiểm tra cú pháp phần lõi không phụ thuộc UIKit.
- PASS: `g++ -DSUPERMAN_MATH_ONLY ...` — vector camera, giới hạn tham số, nút bấm/giữ.
- PASS: `python3 -m unittest discover` với **IPA gốc** — kiểm tra chèn load command và nguyên byte vùng code khác.
- PASS: `python3 -m unittest discover` với **IPA CustomTouch đã vá** — bảo toàn bản đã có CustomTouch.
- PASS: `python3 -m compileall` — mã Python không lỗi cú pháp.
- PASS: `ScriptHookV.dylib` trong IPA có symbol `scriptRegister`, `scriptWait`, `nativeInit`, `nativePush64`, `nativeCall`, `worldGetAllPeds`, `worldGetAllVehicles`.
- PASS: `Menyoo.shv.dylib` trong IPA là ARM64 và phụ thuộc API `ScriptHookV.dylib` tương ứng.
- PASS: ZIP Superman TamedMods có 4 WAV dùng cho bản mới và `Superman.asi` là plugin PC, không nhập lại.

## Các bước **chưa thực hiện**

- CHƯA BUILD: `SupermanOverlay.mm` trên Xcode/iPhoneOS SDK; máy hiện tại không có `xcrun`/`codesign` để xác minh bản dylib ARM64 hoàn chỉnh. Cần GitHub Actions `macos-15`.
- CHƯA CÓ IPA: Không tạo ra IPA Superman, vì chưa có dylib ARM64 biên dịch hợp lệ.
- CHƯA KIỂM THỬ: Cài đặt, chạy trong game, nút hiển thị, súng Heat Vision, vật lý bay/sóng, FPS, khả năng Menyoo hoạt động và chuyển chế độ Online đều phải thử trên iPhone.
- CHƯA KÝ: Công cụ `install_unsigned.py` tạo IPA thử nghiệm **UNSIGNED**; cần ký lại toàn bộ app sau khi chèn dylib.

## Giới hạn và phương án xử lý

1. Nếu Action lỗi compile: lấy toàn bộ compiler log, sửa `.mm`/`.cpp` theo lỗi Xcode thực tế.
2. Nếu mod đã chèn nhưng không thấy nút S: đọc log `Superman iOS Script registered` và kiểm tra `ScriptHookV` đã khởi chạy script hay chưa.
3. Nếu bấm `S` thấy bật nhưng mod không có tác dụng: đối chiếu v2699 native hash và ABI của `nativeCall` với log game thực tế.
4. Nếu văng khi dùng SÓNG/NỆN: kiểm tra bản port có đầy đủ world pool APIs; có thể tạm tắt 2 nút để cô lập lỗi.
5. Nếu mất điều khiển sau bay: tắt Superman, chụp log, kiểm tra `SET_ENTITY_HAS_GRAVITY` trả lại `true`.

Vì chưa có build iOS và kiểm thử thực tế, hiện trạng dự án là **prototype nguồn**, không phát hành như bản ổn định.
