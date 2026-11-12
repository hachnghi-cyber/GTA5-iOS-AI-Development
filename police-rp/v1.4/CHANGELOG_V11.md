# Police RP Only v1.1 — xác minh nhánh NHẬN nhiệm vụ Online (12/11/2026)

## Phát hiện từ tệp GTA5 của GTA V iOS v12

Tại `MacportJobsUpdate`, mã ARM64 của bản có SHA-256
`d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b`:

- `0x1000EA13C`: kiểm tra kiểu sự kiện `0xAE`.
- `0x1000EA154`: yêu cầu bản ghi 244 byte.
- `0x1000EA168–0x1000EA170`: kiểm tra chữ ký `MPJ2`.
- `0x1000EA174`: kiểm tra chỉ số người gửi công bố <=31.
- `0x1000EA1A0`: bỏ qua bản ghi mang chỉ số cục bộ.
- `0x1000EA1BC–0x1000EA1D8`: tham chiếu và cập nhật bộ đếm chống trùng.

Nhánh nhận là **giao thức nhiệm vụ có sẵn**; không tự tiếp nhận `PRC1`/Police RP.
Chỉ số người gửi có mặt trong payload, nên **không thể coi đó là danh tính mạng đáng tin cậy** nếu thiếu metadata từ engine. Trình nhận sự kiện cần phân biệt đúng kênh và lấy sender/session từ lớp mạng đã xác thực.

## Mã bổ sung

- `Tools/verify_v12_job_receiver.py`: công cụ đọc IPA, xác minh đúng mã máy & checksum, xuất `ARM64_JOB_RECEIVE_V12.json`. Không ghi sửa IPA.
- `Tools/test_v11_receiver.py`: kiểm thử chữ ký (dữ liệu giả lập), và kiểm tra nhị phân thật khi có `PRP_GTA5_BIN`; CI không đòi upload tài sản game.
- `Integration/prp_event_isolation.{c,h}`: lớp điều phối **nghiên cứu** chỉ nhận `PRC1` từ một kênh Police RP tách riêng đã được xác thực; mọi gói đường gốc chuyển tiếp, không nuốt hay thay đổi `MPJ2`.
- `Integration/test_event_isolation.c`: thử 7 điều kiện phân luồng, danh tính, session, dữ liệu.
- `Tools/test_v11_event.sh`, cập nhật bộ biên dịch Mach-O ARM64 và workflow macOS mới.

## Kiểm thử

- 33 unit tests Python cũ đạt.
- 60 phép kiểm tra P2P cũ; 25.000 đầu vào không hợp lệ và 21 phép kiểm tra mô phỏng giữ nguyên đạt.
- 7 kiểm tra cách ly sự kiện + 4 bài kiểm thử mã xác minh (3 chạy độc lập; bài còn lại cần GTA5 thật).
- 8 tệp Mach-O ARM64 dạng **object** tạo được (không phải thư viện nạp được).

## CHƯA CÓ

- Nhận và gửi sự kiện Police RP qua engine RAGE thật.
- Hook chạy mỗi frame, danh tính sender/session từ engine, điều khiển Ped Online trên iOS.
- Dylib iOS thực tế, IPA đã vá, kiểm thử hai iPhone.

**Không nhập gói này vào game. Không sử dụng Menyoo Online BETA làm nền.**
