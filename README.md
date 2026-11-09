# GTA V iOS v11.2 — nhiều nút Custom (bản thử nghiệm)

Đây là mã nguồn của **một lớp nút mới**, gắn bổ sung lên giao diện cảm ứng
của GTA V iOS. **Không thay thế** `TCOverlay`, `TCButton`, Menyoo, nút Pause,
trainer, icon Telegram hay dữ liệu trò chơi.

## Có gì

- Nút **＋** trên màn hình chơi để thêm nhiều nút Custom tùy ý.
- Đặt tên, gán phím ví dụ `F8` (Menyoo), `E`, `SPACE`, `SHIFT+E`, `CTRL+F8`.
- Chế độ **Kéo để chỉnh vị trí**: kéo để di chuyển, chạm nút để đổi phím,
  chỉnh kích thước, độ mờ hoặc xóa. Nhấn `＋` để hoàn tất chỉnh sửa.
- Chọn hiện ở cả hai chế độ / chỉ đi bộ / chỉ lái xe.
- Tự lưu vào `NSUserDefaults`, không cần sửa JSON layout cũ.
- Lớp giao diện chỉ nhận chạm **đúng vùng của nút mới**; ngoài các vùng đó,
  chạm được truyền cho game.
- Chỉ kích hoạt phím nếu nhận diện được thư viện `libgtacompat` đúng UUID
  và đoạn mã gửi phím chính xác của bản IPA đính kèm. Nếu khác, **tự ngắt**
  để tránh gọi sai địa chỉ làm văng game.

## Hiện trạng

**BẢN BETA MÃ NGUỒN — chưa chạy thử trên iPhone. Không đưa cho người dùng cuối**
trước khi build và thử nghiệm. Môi trường phân tích hiện chỉ có Linux, không
có SDK iOS để biên dịch `.dylib`. Tập lệnh đóng gói đã kiểm tra ở mức Mach-O;
điều này **không có nghĩa** giao diện hay các phím chắc chắn hoạt động.

Không sử dụng cho một bản IPA khác vì offset/UUID `SendKey` có thể thay đổi.

## Build trên macOS / GitHub Actions runner macOS

1. Chuẩn bị Xcode (iOS SDK) và Python 3.
2. Có bản `GTAV-v11.2(2).ipa` đúng phiên bản đã phân tích.
3. Chạy:

   ```sh
   bash build_custom_buttons.sh /path/to/GTAV-v11.2\(2\).ipa output.ipa
   ```

4. Kết quả `output.ipa` **chưa ký**. Ký lại IPA và thư viện mới bằng phương
   pháp cài đặt của bạn. Sao lưu dữ liệu/lưu game trước khi cài.

### Build trên GitHub Actions (không cần máy Mac)

1. Đưa **các tệp mã nguồn** trong thư mục này lên một repository GitHub.
   Đặt `build_custom_buttons.sh` và `CustomButtons.mm` ở thư mục gốc repo;
   đặt workflow ở `.github/workflows/build-custom-buttons.yml`.
2. Giữ IPA gốc trên một đường dẫn HTTPS **riêng tư** và tạo repository secret
   `GTAV_IPA_URL` chứa URL tải trực tiếp đó. Không commit hoặc public IPA gốc.
3. Trong GitHub, vào **Actions → GTA V iOS v11.2 Custom Buttons (BETA) → Run workflow**.
4. Lấy file `GTAV-v11.2-CustomButtons-BETA-UNSIGNED` trong mục Artifacts. IPA
   trong artifact chưa ký. Nếu build lỗi, gửi log biên dịch để sửa tiếp.

Đường dẫn riêng tư chỉ được đọc trong workflow. Tránh dùng URL công khai chứa
token dài hạn; có thể dùng link tải tạm thời và thu hồi sau khi build.

Vì `GTA5` đã đổi load commands, mọi chữ ký mã trước đó không còn hợp lệ;
đây là hành vi bình thường khi sửa IPA. Công cụ cài phải ký **tất cả** binary.

## Kiểm thử bắt buộc trước khi chia sẻ bản cài

1. Cài bản gốc để đối chiếu, backup saves & layout.
2. Trên iPhone: mở launcher, vào Story, kiểm tra không crash.
3. Chạm `＋`, thêm `F8`. Ấn F8 phải mở/đóng Menyoo **không** văng.
4. Thêm `E`, `SHIFT+E`, xác minh phím xuống và nhả đúng (không kẹt phím).
5. Kéo, resize, chuyển đi bộ/lái xe, khóa máy, đổi orientation, thoát và mở lại.
6. Kiểm tra Pause, map, trainer, touch editor, giao diện ẩn cảm ứng, Telegram.
7. Nếu có crash, gửi `crash-*.txt`, `run.log`, `posthook.log`, và phiên bản IPA.

Nếu xuất hiện crash, cài lại IPA gốc trên đúng bundle ID (không xóa dữ liệu
người dùng), hoặc quay về bản sao lưu. Không công bố IPA BETA là ổn định
khi chưa hoàn tất các bước kiểm thử trên thiết bị.

## Giới hạn kỹ thuật

- Hiện chỉ hỗ trợ **phím bàn phím** macOS thông qua `SendKey`; chưa hỗ trợ
  trực tiếp các cặp gamepad như `RB + D-pad trái` hoặc macro chuỗi thời gian.
- Khả năng xuất hiện trên màn hình game phụ thuộc việc tìm được `TCOverlay`;
  việc ẩn trong Pause/map tùy vào context do game trả về.
- Đã kiểm tra tĩnh đúng một bản lib, không đảm bảo tương thích bản cập nhật.
- Cần biên dịch trên macOS, ký và thử trên thiết bị thực.
