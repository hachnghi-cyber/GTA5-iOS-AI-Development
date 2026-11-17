# GTA V iOS v13.3 — E3: thử 1 iPhone + laptop/PC

**Mục đích:** chứng minh kênh UDP chẩn đoán RBP1 giữa PC và plugin ScriptHook trên iPhone. Đây **không** phải RAGE multiplayer, PoliceRP hoặc đồng bộ người chơi. Không sửa GTA5/ScriptHook binary. Chỉ gửi PING có HMAC, không có native hash hay lệnh game tuỳ ý.

## Bước 1 — Chuẩn bị

- iPhone **đã ký và cài bản E3**, không phải E1. E0/E1 đã được kiểm tra trên thiết bị trước đó.
- Laptop/PC chạy Python 3.9+; giải nén bộ kit. iPhone và PC cùng LAN và cho phép UDP ngang hàng. Nếu dùng Personal Hotspot/VPN, kiểm tra địa chỉ nguồn/cách ly mạng; tùy trường hợp thiết bị sẽ không truy cập được nhau.
- Trên Windows: `ipconfig` lấy **IPv4 của Wi-Fi**, không lấy IP VPN. Trên iPhone: **Cài đặt → Wi-Fi → (i) → Địa chỉ IP**.
- Không cần GTA trên laptop. Không cần iPhone thứ hai.

## Bước 2 — Tạo hai cấu hình mới

Tại thư mục giải nén, mở Command Prompt/PowerShell:

```powershell
python prepare_one_phone_e3.py --pc-ip 192.168.1.20 --iphone-ip 192.168.1.30 --output-dir E3Configs
python -m unittest -v test_pc_sender.py
```

**Thay IP ví dụ bằng IP thật.** Hai file được tạo với khóa dùng riêng cho lần thử. File `PC_sender.cfg` giữ trên máy tính. Đổi tên file `iPhone_RBPProbe.cfg` thành **`RBPProbe.cfg`** khi chép vào thư mục **Documents** của ứng dụng GTAV trên iPhone (thông qua iOS File Sharing). Không chép file PC sang iPhone. Không tải hai file `.cfg` lên chat/GitHub; khóa HMAC là dữ liệu bí mật.

## Bước 3 — Gửi PING đúng cửa sổ callback

Mở chương trình trên PC trước:

```powershell
python pc_sender.py --config E3Configs/PC_sender.cfg --iphone-config E3Configs/iPhone_RBPProbe.cfg --ready
```

Chương trình sẽ **mở socket UDP trước rồi chờ phím Enter**. Trên iPhone, thoát hẳn GTA nếu đang mở, mở lại bản E3. Khi vào game, **nhấn Enter trên laptop càng sớm càng tốt**. iPhone nhận ở tick 10 và plugin hoàn tất ở tick 900 (khoảng 15 giây chạy scheduler), nên nếu chậm sẽ báo thất bại giả; khi đó khởi động lại game và tạo cặp cấu hình mới cho lượt thử tiếp theo.

PC phải hiện cả:

```text
[PC_E3] ACK_VERIFIED seq=1
[PC_E3] NATIVE_INVOCATION_REPORT_VERIFIED seq=1
[PC_E3] Result: ACK=1 NATIVE_RECEIPT=1
```

Điện thoại: `Documents/RBPProbe.log` cần ghi `NETWORK_ACTIVE mode=receiver`, `PACKET_ACCEPTED seq=1 ack_sent=1`, `REMOTE_E3_GAME_ACTION_INVOKED=1` và `NATIVE_INVOCATION_REPORT_SENT=1`. Ghi nhận riêng thông báo HUD thực sự xuất hiện hay không. `ACK=1` mà `NATIVE_RECEIPT=0` chỉ chứng minh gói vào queue; không chứng minh game native đã chạy.

## Xử lý lỗi

- `PC/iPhone configurations match` nhưng lỗi `PC would send from IPv4...`: hệ điều hành đang định tuyến qua IP khác (ví dụ VPN). Hãy tắt VPN hoặc chọn đúng giao diện IP, rồi **tạo lại cấu hình mới**.
- `ACK=0`: kiểm tra đúng địa chỉ IPv4 của Wi-Fi, UDP 47880→47881, quyền Local Network, firewall Windows, AP isolation và thời điểm mở game.
- `ACK=1 NATIVE_RECEIPT=0`: PC đến được queue, nhưng chưa xác minh callback native; thu `RBPProbe.log` của **lần chạy mới nhất**.
- `CONFIG_MISSING_OR_INVALID_NETWORK_DISABLED`: file sai tên/đường dẫn, cấu hình sai hoặc game không truy cập được Documents.
- Nếu không có `RBPProbe.log`: kiểm tra ScriptHook đã bật và đã cài đúng **bản E3**, không phải E0/E1.

Đây là công cụ chạy cục bộ; không tạo hoặc tự kích hoạt công việc nền. **Không thử bắt giữ/điều khiển player Online** bằng giao thức này. RAGE sender/session provenance vẫn là cổng riêng chưa hoàn thành.
