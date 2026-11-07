# GTA V iOS v11 — kế hoạch tích hợp nút Gojo (chưa áp dụng)

## Bằng chứng từ IPA được cung cấp

- `Payload/GTAV.app/Frameworks/libgtacompat.dylib` là Mach-O ARM64.
- Có lớp Objective-C `TCOverlay` và `TCButton`.
- Các selector được tìm thấy: `initWithFrame:`, `buttonForDef:context:scale:`, `touchWithRole:`, `editTouchControls`, `reloadTouchSettings`, `setPressed:`.
- Có dấu vết `_customButton`, `_addonButtons` nhưng **chưa chứng minh** có hỗ trợ dữ liệu cấu hình cho năm nút mới.
- `ScriptHookV.dylib`, Mono và ScriptHookVDotNet2/3 hiện diện; bộ add-on chứa thư viện .NET và `PostHook.DotNet.dll`.
- SHA-256 `libgtacompat.dylib` đã phân tích: `5d18bad7664cc282543098006eff2b2f5274a11ff37c1667e5eab0d8a47c3c43`.
- Địa chỉ method tĩnh trong **đúng dylib này**: `-[TCOverlay initWithFrame:]` tại `0x12c564`, `-[TCOverlay buttonForDef:context:scale:]` tại `0x12e6e4`, `-[TCOverlay touchWithRole:]` tại `0x136f90`. Địa chỉ chỉ dùng phục vụ đối chiếu; không chuyển sang phiên bản khác và không dùng làm địa chỉ runtime cố định (ASLR).

## Đề xuất UI

| ID không trùng | Nhãn | Phím logic | Trạng thái |
|---|---|---|---|
| gojo.infinity | ∞ | H | bật/tắt; đổi màu khi bật |
| gojo.red | RED | J | một lần chạm |
| gojo.blue | BLUE | U | yêu cầu ngắm mục tiêu |
| gojo.purple | PURPLE | Y | một lần chạm |
| gojo.void | VOID | I | một lần chạm |

Giữ nguyên nút Menyoo đang tồn tại. Tránh đặt nút đè lên Pause, hai joystick, nút ngắm/bắn, vùng mini-map. Layout cần tính safe area và tỷ lệ iPhone/iPad riêng; để người dùng di chuyển/đổi kích thước sau khi chức năng ổn định.

## Cầu nối bắt buộc phải xác minh

1. `TCOverlay` bắt đầu và kết thúc nhấn trên luồng UIKit. Không gọi native game từ thread này.
2. Mỗi sự kiện chạm tạo một yêu cầu kỹ năng (`H`, `J`, `U`, `Y`, `I`) với cạnh nhấn duy nhất vào hàng đợi thread-safe.
3. Trên thread chạy ScriptHook, hàng đợi được đọc và gọi kỹ năng qua API đã chứng minh hợp lệ. Không dùng địa chỉ hàm ARM64 đoán mò hoặc giả định `KeyDown` của .NET nghe được thao tác từ UIKit.
4. Khi chuyển sang màn hình Pause/Launcher/Online, bàn phím hoặc app background: nút phải ẩn/ngắt sự kiện theo ngữ cảnh. Khi script lỗi hoặc bị tắt, các nút không gây crash hay làm kẹt trạng thái.
5. Mọi patch binary phải có bản gốc, hash, so sánh bytes, kiểm tra Mach-O load commands và ký IPA lại. Kiểm thử thật trên thiết bị mới được kết luận hoạt động.

## Tiến độ mã nguồn cầu nối thử nghiệm

- `native/GojoTouchQueue.c` cung cấp hai hàm `gojo_touch_press` và `gojo_touch_consume`, dùng atomic bitmask để tránh sửa dữ liệu chung không đồng bộ.
- `native/GojoTouchOverlay.mm` là một giả thuyết tích hợp thông qua swizzle `-[TCOverlay initWithFrame:]`; tạo năm UIButton ngay trong view điều khiển gốc và phát sự kiện vào hàng đợi.
- C# đọc sự kiện qua `DllImport` và gọi chung logic H/J/U/Y/I. Khi dylib vắng mặt, mod vô hiệu hóa thử kết nối và vẫn nhận phím nếu có.
- Bộ test C của hàng đợi đã đạt. **Chưa có bằng chứng UIButtons thực sự nhận được touch trong TCOverlay** vì subclass có thể có `hitTest:` riêng; chưa biết kết quả P/Invoke Mono và chưa có kết quả chạy iOS.
- Bộ vá `native/pack_test_ipa.py` đã kiểm tra chính xác SHA-256 IPA v11 và thử thêm một `LC_LOAD_DYLIB` 56 byte vào vùng padding header ngay trong bộ nhớ: 11.120 byte trống trước, 11.064 byte trống sau. Đây chỉ là kiểm tra cấu trúc, không phải kiểm thử nạp thư viện.

## Điều kiện chưa đạt

- Chưa xác định một ABI/callback public ổn định từ touch overlay sang ScriptHook C#.
- Chưa có build toolchain iOS phù hợp trong môi trường hiện tại để tạo và ký dylib ARM64.
- Chưa chạy test touch trên iPhone/iPad.

**Kết luận:** Không chèn năm nút vào IPA gốc bằng một binary patch chưa chứng minh; bước tiếp theo phải kiểm chứng callback qua một mod tối thiểu không phá gameplay rồi mới nhân rộng ra năm nút.
