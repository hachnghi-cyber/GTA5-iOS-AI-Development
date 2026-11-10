# GTA V iOS v11.3 — CustomTouch (thử nghiệm)

Đây là **mã nguồn thử nghiệm**, **không phải IPA đã chạy được**. Chưa biên dịch trên
Xcode, chưa kiểm thử trên iPhone và chưa xác minh GTA V v11.3 có nhận dữ liệu từ
`GCVirtualController` như tay cầm của người chơi chính hay không.

## Kết quả kiểm tra bản gốc

- IPA: `GTAV-v11.3(1).ipa`, iOS ARM64, bundle `com.macport.gtav`, iOS tối thiểu 16.3.
- `libgtacompat.dylib` đã có `TCOverlay`, `TCButton`, `pickCustom:` và nhập/xuất layout.
- JSON người dùng: 40 điều khiển, `1.custom` và `2.custom`; 14 mapping hiện đều là `Menyoo`.
- Không thêm `custom2` vào layout gốc vì parser có thể bỏ qua role không hỗ trợ.
- Không thay `libgtacompat.dylib`, `Menyoo.shv.dylib` hay layout gốc.

## Đã xây dựng

### Thử nghiệm sửa F10 cho Superman (10/11/2026)

- Khi mở C+ lần đầu, bản nguồn mới **bổ sung nút F10** cạnh J/K/L/M;
  các nút đã lưu không bị ghi đè. Layout cũ thiếu F10 được bổ sung một lần.
- Khi nhấn F10, ngoài `SendKey(USB_HID_F10)` của game, module thử gửi
  `WM_KEYDOWN/WM_KEYUP` (`VK_F10`) vào hàng đợi Win32 tương thích bằng
  `GetActiveWindow`/`PostMessageA`. Chỉ riêng F10 có đường gửi bổ sung.
- Ghi `CustomTouch F10 down=... ScriptHook message queued=...` vào log để biết
  hàng đợi có nhận sự kiện hay không. Giá trị `queued=1` **không bảo đảm**
  C# ScriptHookVDotNet đã nhận và xử lý phím.
- **Đây là bản thử nghiệm, chưa biên dịch hoặc thử trên iPhone sau khi sửa.**
  Không khẳng định đã chữa được gốc lỗi. Nếu ScriptHook không xử lý
  `WM_KEYDOWN`, phải tìm và sửa trực tiếp bridge keyboard của ScriptHook.
- Giữ mod Superman độc lập (`.dll`) và không chép `.asi` Windows vào IPA.

Workflow tự động mới: `.github/workflows/build_customtouch_f10.yml`.
Vào Actions → **Build GTA V v11.3 C+ F10 ScriptHook bridge** → Run workflow.
Không cần `ipa_url` nếu chỉ cần artifact `CustomTouch-v11.3-F10-Bridge-ARM64`.
Muốn workflow đóng IPA kiểm thử thì nhập **link HTTPS tải trực tiếp IPA v11.3
gốc** (hoặc đặt secret `GTAV_IPA_URL`) trước khi chạy. IPA tạo ra được ký
ad-hoc, cần ký lại bằng chứng chỉ cài đặt hợp lệ. Không đưa IPA chứa file
game lên repository công khai.

- Overlay UIKit có 4 nút khởi tạo **J, K, L, M** và công tắc `C+` / `C−`.
  Mặc định **chưa kích hoạt**. Đây không phải giới hạn 4 nút.
- Khi bật `C+`, chọn **Sửa → +** để tạo nút bàn phím PC mới (tối đa 24 nút),
  nhấn nút mới trong chế độ Sửa để đổi phím, tên, cỡ, độ mờ hoặc xoá. Kéo
  từng nút để sắp xếp vị trí; `Xong` để dùng. Các nút được lưu lại tự động.
- Có thể gán **A–Z**, **0–9**, **F1–F12**, **Space**, **Enter**, **Tab**, **Esc**,
  **Backspace**, **Delete**, **Numpad 0–9**, các phím điều hướng và tổ hợp
  **Ctrl/Shift/Alt + phím**. Ví dụ dành cho mod: `J`, `K`, `L`, `M`, `SPACE`,
  `F10`, `NUM0`, `CTRL+J`. Nhập tên không kèm `KEY_`. Một số mod sử dụng
  *phím Windows API* có thể chưa nhận mã phím từ bridge; phải thử trên máy.
- Có thể chọn thêm các chức năng tay cầm A/B/X/Y, LB/RB,
  LT/RT, 4 hướng D-pad, hoặc mapping thử nghiệm `MENYOO` (RB+D-pad trái;
  chỉ được xác nhận ở bản cũ v10.3).
- **iOS 16.3–16.x:** chỉ bật các nút phím PC; các hàm chỉnh trạng thái của
  `GCVirtualController` cần iOS 17 trở lên, nên nút tay cầm ảo được vô hiệu hoá
  trên iOS 16 để tránh ảnh hưởng hệ thống điều khiển của game.
- Phím bàn phím gọi trực tiếp hàm nội bộ `SendKey(unsigned char, bool)` của
  `libgtacompat.dylib`. Hàm này được tìm trong Mach-O gốc tại `0x152e3c`,
  đối chiếu UUID `07E7118E-C3A1-380E-9192-58BCF3D30DD7` và 16 byte đầu
  trước khi gọi. **Sai phiên bản => bỏ qua phím, không thử địa chỉ khác.**
- Mã nút đang nhấn được giữ tới khi nhấc tay; các tổ hợp và phím chia sẻ
  trạng thái dùng chung để hạn chế kẹt phím. Khi tắt `C−`, vào chế độ Sửa hoặc
  app chuyển nền, code chủ động gửi sự kiện nhả phím.
- Tùy chọn lưu qua `NSUserDefaults`, tách biệt với JSON gốc của game.
- Không kết nối tay cầm ảo trước khi người dùng chủ động bật, tránh ảnh hưởng
  logic touch/input của game ngay khi mới cài.
- Nếu không tìm thấy `MacwinViewController`, module không đặt nút lên launcher.

### Giới hạn cần kiểm tra

1. Keyboard bridge sử dụng hàm **nội bộ không có API chính thức**; đã xác minh
   tên, chữ ký, UUID và vị trí bằng đọc Mach-O. Chưa test trên thiết bị rằng
   `GCKeyCode` USB HID được game xử lý giống phím J/K/L/M từ bàn phím thật.
2. `GCVirtualController` (chỉ kết nối nếu một nút đã gán tay cầm) có thể được GTA V nhận thành một controller khác player 1,
   khiến nút hiện nhưng không điều khiển được hoặc làm ẩn nút gốc. Phải kiểm tra trên
   iPhone. **Không phát hành đại trà khi chưa qua kiểm thử này.**
3. Các nút chưa kết nối trực tiếp vào editor `Edit controls` chính của v11.3.
   Việc chỉnh sửa nút PC là trên overlay riêng. Chế độ ẩn nút gốc chưa tự đồng bộ.
4. GitHub Actions đã biên dịch được `libCustomTouch.dylib` ARM64 (artifact
   ngày 10/11/2026). **Chưa có xác nhận ứng dụng chạy và nhận phím trên iPhone.**
5. Cần ký lại IPA bằng chứng chỉ hợp lệ khi cài; bản ký ad-hoc chỉ phục vụ kiểm tra.

### Lỗi build macOS đã xử lý trong mã nguồn (10/11/2026)

- Trước đây script gọi `clang` khi liên kết Objective-C++; log Actions báo
  `___gxx_personality_v0` không tìm thấy. Đã chuyển sang `clang++` kèm
  `-stdlib=libc++` và link tường minh `CoreGraphics`.
- Thay `CGPointZero` bằng `CGPointMake(0, 0)` để tránh lỗi `_CGPointZero`.
- Bảo vệ các API `GCVirtualController` chỉ có từ iOS 17 bằng `@available`.
- Đây là **sửa mã theo log**, chưa có kết quả biên dịch lại từ GitHub Actions
  và chưa kiểm thử trên thiết bị.

## Cách build trên macOS có Xcode

```bash
bash build_on_mac.sh dist
python3 inject_ipa.py \
  --ipa '/path/to/GTAV-v11.3.ipa' \
  --dylib 'dist/libCustomTouch.dylib' \
  --output '/path/to/GTAV-v11.3-CUSTOM-TEST.ipa'
```

`inject_ipa.py` chỉ tạo **IPA mới**, không cho phép ghi đè IPA ban đầu; đọc
cấu trúc gói, thêm duy nhất `libCustomTouch.dylib`, thêm `LC_LOAD_DYLIB` vào
`GTA5`, ký ad-hoc, so sánh danh sách file và kiểm tra ZIP. Output kèm
`.report.json` ghi SHA-256 và danh sách file thay đổi. Cần test cài/khởi
động thực tế và ký lại bằng SideStore/chứng chỉ phù hợp.

### Tự động đóng IPA trên GitHub Actions (không cần Mac riêng)

Đưa `build_unsigned_ipa.py`, `inject_ipa.py`, `build_on_mac.sh` và
`CustomTouch.mm` vào **thư mục gốc** repository. Đưa
`.github/workflows/build_customtouch_ipa.yml` vào **đúng thư mục .github/workflows**.

- Actions → `Package GTA V iOS v11.3 CustomTouch IPA (test)` → Run workflow.
- Điền `ipa_url` là **URL HTTPS tải trực tiếp IPA gốc** (không phải bài đăng
  Telegram), hoặc tạo secret `GTAV_IPA_URL`.
- Workflow tự tải IPA, build thư viện, kiểm tra đúng phiên bản, thêm thư viện,
  ký **ad-hoc**, đối chiếu tệp và cung cấp IPA + báo cáo trong Artifacts.
- Đây vẫn là **IPA thử nghiệm**, cần **ký lại bằng danh tính cài đặt hợp lệ**
  và thử trên iPhone trước khi sử dụng chính thức.

Nếu chỉ có Linux và đã có ZIP artifact biên dịch, có thể đóng **IPA chưa ký**:

```bash
python3 build_unsigned_ipa.py \
  --ipa '/path/to/GTAV-v11.3(1).ipa' \
  --plugin-zip '/path/to/customtouch-v11-3-arm64.zip' \
  --output '/path/to/GTAV-v11.3-CustomTouch-UNSIGNED-TEST.ipa'
```

Bản chưa ký **không thể cài nguyên trạng**; phải ký lại toàn bộ app và thư viện.
Hai phương pháp khóa theo SHA-256 của `GTA5` và `libgtacompat` từ **IPA v11.3
gốc được gửi trong cuộc trò chuyện này**. IPA đã qua bản vá khác sẽ bị từ
chối cho đến khi kiểm tra tương thích lại, tránh làm hỏng bản gốc.

### GitHub Actions

Nếu đưa thư mục này vào **gốc repo riêng**, workflow
`.github/workflows/build_custom_touch.yml` có thể build module cho arm64 iOS và
trả file `.dylib` như artifact. Workflow **không** yêu cầu upload IPA lên repo
public. Sau khi tải dylib về, chạy script inject trên macOS.

## Kiểm thử và rollback

```bash
python3 -m unittest discover -s tests -v
bash -n build_on_mac.sh
python3 -m py_compile inject_ipa.py build_unsigned_ipa.py
```

- Trước tiên chạy game gốc, lưu phiên chơi, đo FPS và chụp bố cục cũ.
- Bản thử nghiệm: vào game, `C+` để bật; kiểm tra không mất touch chính.
- Chỉ khi touch vẫn dùng được mới thử J/K/L/M. `Sửa → +` để tạo nút mới,
  chọn `SPACE`, `F10`, `NUM0` hoặc tự nhập tổ hợp; `Xong` để dùng thử mod.
- `C−` tắt bộ nút độc lập; dùng lại IPA v11.3 gốc nếu có bất kỳ lỗi nào.
- Kiểm tra Menyoo/Telegram/Trainer/Online và cả cảnh chuyển từ launcher vào game.

Các nguồn API: [Apple GCVirtualController](https://developer.apple.com/documentation/gamecontroller/gcvirtualcontroller),
[LIEF Mach-O `add_library`](https://lief.re/doc/stable/formats/macho/python.html).
