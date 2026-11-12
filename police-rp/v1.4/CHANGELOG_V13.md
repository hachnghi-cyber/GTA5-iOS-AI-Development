# Police RP Only v1.3 – Loader diagnostic / integration gate

Đây **không** phải bản Police RP đã chạy. Bản này kiểm chứng một điều kiện có thể thử thật trên iPhone: liệu game v12 có nạp một thư viện ARM64 iOS bổ sung thông qua một `LC_LOAD_DYLIB` mới hay không. Chưa can thiệp vòng cập nhật RAGE, không cho Menyoo chạy Online và không truyền lệnh bắt giữ.

## Điều đã xác minh với GTAV-v12(1).ipa

- GTA5 UUID `6a498e32e70c334cbca3affd35e8d171`; SHA-256 `d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b`.
- Tệp Mach-O ARM64 `GTA5` có 39 load commands, bảng lệnh dài 3408 byte, kết thúc tại offset 3440. Phân đoạn dữ liệu đầu tiên bắt đầu offset 16384. Vùng dư để thêm lệnh liên kết thư viện có chứa toàn byte 0.
- Đã viết công cụ `inject_prp_probe.py`: từ chối IPA khác build, từ chối `.dylib` không phải nền tảng iOS (LC_BUILD_VERSION platform=2), từ chối patch lần hai; thay duy nhất hai trường header `ncmds/sizeofcmds`, thêm load command, thêm `PoliceRPProbe.dylib`, bảo toàn các thành phần IPA khác.
- Trình liên kết `ld64.lld` trong môi trường Linux không hỗ trợ iOS. Cần dùng workflow `build-prp-v13-probe-ios.yml` trên macOS/Xcode để tạo thư viện.

## Mức độ kiểm chứng

- Đã kiểm thử offline mã vá trên bản GTA5 v12 người dùng cung cấp (không ghi đè bản gốc).
- Chưa chạy workflow trên macOS, chưa có dylib iOS hợp lệ trong gói này, chưa tạo/cài IPA thử nghiệm lên iPhone.
- Bản thử nghiệm sau khi ký lại nếu nạp được chỉ in `PRP_DIAG_V13`; **không có hook**, không bắt NPC/người chơi.

## Vẫn thiếu để Police RP hoạt động

1. Callback *game-thread* được engine gọi trong GTA Online, giữ nguyên luồng `MacportOnlineUpdate` và các script của engine.
2. Route gửi/nhận dữ liệu Police RP có xác thực network player ID; không dùng `MPJ2` và không dựa vào claimed sender trong payload.
3. Native actions trên local player + test đồng thuận trên hai máy.
4. iOS build/sign/reinstall + runtime logs. Không tuyên bố thành công khi chưa có log.
