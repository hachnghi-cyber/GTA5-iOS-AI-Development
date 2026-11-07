# Gojo iOS v11 — dự án build và kiểm thử

Đây là bộ nguồn Gojo thử nghiệm được sửa từ `Class1.cs` người dùng cung cấp.
Thư viện tham chiếu ScriptHookVDotNet2 và System.Windows.Forms được trích nguyên vẹn từ bộ `GTAV-ScriptHook-Pack-Menyoo-VietHoa-MoRong-v11(2).zip` người dùng cung cấp.

**Chưa có xác nhận biên dịch DLL thành công hoặc chạy trên iOS.** IPA v11 gốc không bị thay đổi.

## Biên dịch

- Cần .NET SDK 8.0 trên PC hoặc GitHub Actions.
- Chạy `dotnet build Gojo_iOS.csproj -c Release` trong thư mục này.
- Nếu build thành công, lấy `bin/Release/net8.0/Gojo_iOS.dll`.
- Đưa DLL vào ZIP mod có dạng `scripts/Gojo_iOS.dll`, rồi dùng `IMPORT SCRIPT` của launcher v11 (cần kiểm tra thực tế có nạp được không).

Đã kèm workflow GitHub Actions `.github/workflows/build-gojo.yml` để tạo file ZIP DLL và gửi vào mục Artifacts khi chạy workflow.

### Đưa bộ nguồn lên GitHub và build (chỉ cần làm một lần)

1. Giải nén **ZIP mã nguồn** trên máy tính. Trong thư mục giải nén phải thấy `Gojo_iOS.csproj`, `refs/`, `native/` và **thư mục ẩn** `.github/workflows/`.
2. Sao chép **nội dung** thư mục đó vào **gốc** một GitHub repository do bạn quản lý; đừng chỉ tải nguyên file `.zip` lên repo. Giữ nguyên đường dẫn `.github/workflows/build-gojo.yml`.
3. Commit và push các tệp. Vào trang repository > **Actions** > **Build Gojo iOS and Touch Bridge** > **Run workflow** (hoặc đợi lần build từ push).
4. Nếu cả ba job hoàn tất, mở lần chạy và tải artifact **Gojo_v11_BUILD_KIT_TEST**. Trong đó có hai thư viện biên dịch và công cụ kiểm tra/đóng gói IPA thử nghiệm. Nếu GitHub hiển thị lỗi, gửi log của job thất bại để xử lý.

**Quan trọng:** ZIP build **không phải** IPA đã ký/cài được. Việc tạo bản IPA thực sự cần đúng IPA v11, công cụ ký iOS và kiểm chứng trên thiết bị. Workflow không chứa hoặc tải lên IPA thương mại của người dùng.

## Kỹ năng và phím

| Phím | Chức năng |
|---|---|
| H | Infinity bật/tắt |
| J | Red, đẩy ra xa |
| U | Blue, hút về tâm đang ngắm |
| Y | Hollow Purple |
| I | Unlimited Void |
| K | Khôi phục trạng thái khẩn cấp |

Phần `System.Media.SoundPlayer` đã được bỏ vì không có bằng chứng host iOS hỗ trợ cách phát WAV này. File WAV gốc không được đóng vào bản thử nghiệm.

## Nút trên màn hình

IPA v11 có `TCOverlay` trong `libgtacompat.dylib`. Thư mục `native/` giờ có bản thử nghiệm cầu nối độc lập:

- `GojoTouchQueue.c`: hàng đợi sự kiện atomic (đã biên dịch và kiểm thử trên Linux).
- `GojoTouchOverlay.mm`: mẫu tạo năm UIButton bằng UIKit và nối vào `TCOverlay` bằng method swizzling (chưa được biên dịch/test trên iOS).
- `build_ios.sh`: lệnh build `GojoTouchBridge.dylib` trên máy Mac có Xcode. **Không tự chèn dylib vào IPA.**
- `pack_test_ipa.py`: kiểm tra hash v11, thêm load command vào bản sao `libgtacompat.dylib`, đóng IPA **chưa ký** sau khi đã có dylib ARM64 thật; không sửa IPA đầu vào.
- C# có tùy chọn `DllImport("GojoTouchBridge")` để lấy sự kiện và vẫn dùng phím H/J/U/Y/I khi chưa có native bridge.

Cầu nối native **chưa được chứng minh** hoạt động trên v11; không được coi là bản vá cài được. Cần xác minh ABI, vòng đời UIKit, giao diện chạm, ký mã và đường nạp trước khi đưa vào IPA.

## Trình tự test an toàn

1. Sao lưu save, cài bản ScriptHook người dùng gửi, thử một mod .NET đã xác nhận hoạt động trước.
2. Nhập `Gojo_iOS.dll` (nếu đã build), bật trong Trainer › Add-ons › Mods; thử phím H và K bằng bàn phím được hỗ trợ, rồi mới thử các chiêu tấn công.
3. Nếu lỗi, tắt mod trong Trainer hoặc xóa DLL; gửi log `posthook.log` và log ScriptHookV .NET để phân tích.
4. Chỉ khi chứng minh các phím và kỹ năng chạy trên iOS mới tiếp tục làm cầu nối nút cảm ứng native.

## Kiểm thử độc lập phần hàng đợi (Linux)

```sh
gcc -std=c11 -Wall -Wextra -Werror -O2 -pthread \
  native/GojoTouchQueue.c native/test_touch_queue.c -o /tmp/gojo_touch_queue_test
/tmp/gojo_touch_queue_test
```

Kết quả trong môi trường phân tích: `GojoTouchQueue: all tests passed`.

## Thử riêng phần Mach-O (không ghi IPA)

```sh
python3 native/pack_test_ipa.py --ipa '/path/to/GTAV-v11(3).ipa'
```

Trên đúng IPA người dùng đã gửi, kiểm tra hash và mô phỏng load-command patch trong bộ nhớ đạt: thêm 56 byte `LC_LOAD_DYLIB`, còn 11.064 byte vùng trống. Thao tác này **không** chứng minh dylib nạp và các nút có thể chạm trên iPhone.

Lệnh kiểm tra hồi quy không ghi file:

```sh
python3 native/test_macho_header.py '/path/to/GTAV-v11(3).ipa'
```

Kết quả đã đạt: chỉ vùng header bị thay đổi, phần `__text` giữ nguyên, và file bị sửa sai hash sẽ bị từ chối.

Khi đã có file `GojoTouchBridge.dylib` ARM64 thật, bộ đóng gói cho phép tạo một bản IPA chưa ký mới bằng tùy chọn `--bridge ... --out ...`. **Không cài bản này trực tiếp**; cần ký lại toàn bộ code phù hợp với chứng chỉ/cách cài của người dùng và kiểm thử trên thiết bị. Không phân phối bản IPA không có tính năng đã được xác minh.
