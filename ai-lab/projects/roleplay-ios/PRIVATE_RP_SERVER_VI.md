# Server Police RP riêng cho v13.3

Server mTLS chạy trên Windows/Linux, dùng lại `rp_v133_police.c` và PRPC/PRPA
40 byte. Không phụ thuộc Winstom. Mỗi chứng chỉ đã ghim được server ánh xạ
sang một RP ID và vai trò. Payload không có sender, role, vị trí hoặc cờ xác thực.
Một event loop sở hữu toàn bộ authority; không gọi native GTA từ network thread.

Đã kiểm thử thực tế socket TLS trên host: hai client nhận cùng revision/trạng
thái qua chuỗi nhận ca, còng, tháo còng, áp giải, ghế xe và nhà tù. Quan sát
vị trí/job/xe trong các bài này **là dữ liệu mô phỏng do test sở hữu**. Bản server
chạy bình thường không có provider đó: opt-in/out và snapshot hoạt động;
nhận ca và tác động custody bị từ chối cho đến khi có dữ liệu game tin cậy.
Đây chưa phải bản RP chơi được trên iPhone.

## Chạy trên host

Yêu cầu Python 3.11 trở lên; `cryptography==50.0.2` để tạo bộ chứng chỉ phát
triển. Thư viện server dùng C11, không có asset game. Trong các lệnh dưới,
`MODULE` là đường dẫn tới `ai-lab/projects/roleplay-ios/v133_interaction`.

```sh
python MODULE/tools/build_rp_authority.py --compiler cc --output /private/rp/rp_authority.so
python MODULE/tools/prepare_private_rp.py /private/rp/kit
python MODULE/tools/rp_private_server.py --library /private/rp/rp_authority.so --config /private/rp/kit/server.json
```

Trên Windows chọn `clang` hoặc Zig và xuất `.dll`. Ví dụ Zig:

```powershell
python MODULE/tools/build_rp_authority.py --compiler C:/tools/zig/zig.exe --compiler-arg=cc --compiler-arg=-target --compiler-arg=x86_64-windows-gnu --output C:/private/rp/rp_authority.dll
python MODULE/tools/prepare_private_rp.py C:/private/rp/kit
python MODULE/tools/rp_private_server.py --library C:/private/rp/rp_authority.dll --config C:/private/rp/kit/server.json
```

Mặc định chỉ nghe `127.0.0.1:30133`. Hai terminal client:

```sh
python MODULE/tools/rp_private_client.py --config /private/rp/kit/officer.json
python MODULE/tools/rp_private_client.py --config /private/rp/kit/citizen.json
```

Gõ `opt-in`, `opt-out`, `duty`, `cuff 22`, `escort 22`, `seat 22`, `jail 22`
hoặc `quit`. Khi chưa nối nguồn game, `duty`/custody trả `denied`, đúng thiết kế.
Client gửi heartbeat và in snapshot/ACK; disconnect xóa snapshot cũ ở client.

Bộ phát triển có hạn 30 phút, không ghi khóa CA xuống đĩa và không ghi đè thư
mục cũ. Tạo thư mục mới khi hết hạn. Công cụ từ chối tạo trong Git worktree.
Các file `.key`, JSON cấu hình và chứng chỉ chỉ lưu riêng ở máy; không commit.
Để thử LAN sau này, tạo kit với `--ip <IPv4 LAN>` và chạy server với `--host`
cùng IP. Không cần mở cổng Internet cho các kiểm thử hiện tại.

## Giao thức và vòng đời

TLS 1.3 hai chiều, CA/hostname và pin server; ALPN `police-rp-authority/1`.
Server tra pin client trong registry tối đa 32 principal, từ chối kết nối kép
cho cùng ID. Mỗi lần restart tạo session/epoch ngẫu nhiên mới; không khôi phục
consent/custody cũ. Replay counter được giữ qua reconnect trong cùng generation.

Record: header big endian `uint8 kind, uint32 length`, tối đa 4096 byte.

| Kind | Payload |
| --- | --- |
| 1 WELCOME | `PRPSRV01`, ID, session, epoch, last_nonce; 8 byte magic + bốn uint64 BE |
| 2 REQUEST | PRPC 40 byte, định dạng little endian đã có |
| 3 ACK | PRPA 40 byte; quyết định lịch sử của transaction, không phải trạng thái hiện tại |
| 4 SNAPSHOT | session, epoch, revision BE rồi 0..32 hàng, mỗi hàng mười uint64 BE |
| 5 PING / 6 PONG | Rỗng; client gửi trong mỗi lease 15 giây |

Hàng snapshot: ID, role, consent, duty, custody, custodian, vehicle, seat,
jail_until_ms, last_nonce. Đồng hồ jail là monotonic của server, không phải
wall-clock hay đồng hồ iPhone. Timer phát snapshot khi án hết hạn.

Mỗi connection giới hạn 30 record/giây, burst 60; outbound queue 32 record.
Đọc header/body dùng chung deadline. Client chậm, record lỗi, replay, timeout
hoặc disconnect thu hồi consent/duty/custody. Leave vô hiệu ACK liên quan ID
cũ nhưng giữ nonce. Exact retry trong cùng admission trả ACK cũ; snapshot
revision mới phản ánh trạng thái sau opt-out. Không suy trạng thái từ ACK.

## Kiểm chứng và phần tiếp theo

152 test Python đạt trên Windows, trong đó 15 test private-server dùng TLS
thật và thư viện C đã compile. FFI có kiểm thử C về kích thước, uint64, nguồn
facts và lifecycle. CI chạy GCC/Clang ASan/UBSan và static analyzer. Xem
`baselines/private-rp-server-host.json` và Actions của commit, không gộp với
kiểm thử thiết bị.

Mã client iOS mới hỗ trợ authority ALPN, heartbeat, xác minh ACK và snapshot,
và xóa trạng thái phiên khi ngắt kết nối. Hai bài loopback TLS kiểm tra codec
C dùng trong client với server thật. Probe cài trước đây cần build lại để
dùng giao thức mới. Kit sinh cấu hình iPhone theo từng chứng chỉ; đặt bản
phù hợp vào Documents với tên `PoliceRP-Authority-PRIVATE.json` khi thử LAN.
File chứa danh tính riêng và hết hạn sau 20 phút. Trước khi nối gameplay,
cần xác minh RP principal ↔ game participant, nguồn quan sát và game thread.

Build ARM64 trên commit `99ed120` đạt trong run `44492859651` (SDK 18.5,
iOS tối thiểu 16.3). Source CI `44492869967` đạt cả GCC/Clang ASan/UBSan.
IPA chẩn đoán cục bộ `GTAV-v13.3-Private-RP-Authority-Diagnostic-99ed120-UNSIGNED.ipa`
đã qua CRC, kiểm tra dependency và so sánh mọi mục của gói. Chỉ executable
gốc thay đổi để nạp dylib probe, và một dylib được thêm. Dùng chữ ký và
provisioning của thiết bị để ký lại toàn bộ app trước khi cài.

Để thử một iPhone với Windows, tạo kit mới với `--ip` là IPv4 của PC trên
cùng Wi-Fi. Khởi động server với `--host` là IP đó. Đặt `officer-iPhone-PRIVATE.json`
trong thư mục Documents của app dưới tên `PoliceRP-Authority-PRIVATE.json`.
Chạy CLI Windows bằng `citizen.json` để giữ hai danh tính riêng, sau đó mở
lại GTA và cho phép truy cập mạng cục bộ nếu iOS hỏi. Giữ game ở Sandbox riêng.
Trong `PoliceRP-v13.3-Authority.txt`, `rp_tls_verified=1` và
`result=snapshot_received` xác nhận kênh RP đã nhận dữ liệu. Snapshot trên
Windows cần hiện cả PC và iPhone, sau đó còn một thành viên khi đóng game.
Chỉ gửi log `.txt` khi cần đối chiếu. Cấu hình JSON chứa khóa client.

Với bản IPA hỗ trợ `consent-round-trip-v1`, thêm `--consent-probe` lúc tạo
kit. iPhone tự gửi yêu cầu tham gia rồi rời RP cho chính ID của mình, đối
chiếu ACK và snapshot theo nonce, sau đó đóng kết nối. PC có thể quan sát
thành viên xuất hiện và trạng thái trả về như cũ. Log iPhone chỉ ghi
`result=consent_round_trip_passed` khi nhận đủ cả hai xác nhận. Dòng
`connected=0` là trạng thái dự kiến sau khi phép thử hoàn tất. Khi bỏ tùy
chọn, probe duy trì kết nối như trên và không gửi lệnh tham gia.

Chưa có hai iPhone, log gameplay, kiểm thử native effects hay regression của
Story/GTA Online. Không phát hành IPA gameplay hoặc bật runtime adapter lúc này.
