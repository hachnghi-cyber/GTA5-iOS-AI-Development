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

Authority host ABI 3 cần build lại DLL hoặc `.so`. Định dạng truyền tới
iPhone giữ nguyên. Bên cạnh dữ liệu cho từng lệnh, server yêu cầu nguồn
quan sát ca độc lập, trong cùng tiến trình authority. Mẫu phải khớp chứng
thực RP, phiên, epoch và lần kết nối hiện tại, với dấu thời gian gốc không
quá 250 ms. Nếu nguồn báo bỏ ca, mất dữ liệu hoặc mẫu hết hạn, vòng cập
nhật server thu hồi ca và phát snapshot giải phóng người bị giữ ngay cả
khi client không gửi lệnh. Mặc định chưa có nguồn quan sát game như vậy.

Nguồn quan sát cho từng lệnh nhận hai `GameBinding` đang hoạt động. Mỗi liên
kết gồm lần vào RP qua TLS, phiên GTA, generation và lần vào của nhân vật.
Nguồn trả lại `PairObservation` với hai liên kết gốc của lần lấy mẫu. Server
từ chối mẫu tráo người hoặc mẫu từ phiên cũ, kể cả khi client vẫn dùng cùng
chứng chỉ và chưa đóng kết nối. Adapter phải xác minh các liên kết trong GTA
và giữ dấu thời gian gốc. Khi rời phiên hoặc chuyển generation, server xóa
trạng thái giữ người, thu hồi ca và yêu cầu opt-in lại. Luồng RP giữ kết nối
và nonce để lệnh cũ không được khôi phục.

Ngày 19/11/2026, **iPhone thật và Windows đã qua phép thử tham gia/rời RP**.
Log iPhone lấy qua USB xác nhận TLS và hai phản hồi. PC quan sát lần lượt
kết nối, tham gia, rời RP và ngắt kết nối trong cùng phiên. Xem bằng chứng
đã lọc tại `baselines/private-rp-iphone-consent-20261119.json`. Hai bên dùng
hai danh tính RP. Chỉ phía iPhone chạy GTA, nên chưa xác minh ánh xạ nhân vật
hay gameplay giữa hai thiết bị.

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

### Thử bảng RP trên iPhone

Với build có bảng `RP riêng`, thêm `--panel` khi tạo kit LAN. Chép cấu hình
`officer-iPhone-PRIVATE.json` vào Documents theo tên ở trên. Mở GTA và vào
Sandbox riêng, bấm **RP riêng → Tham gia RP**. Ở CLI Windows dùng danh tính
`citizen.json`, chạy `opt-in` rồi thử `greet 11` hoặc `documents 11`.
Trên iPhone, bấm **Chào hỏi** hoặc **Yêu cầu giấy tờ** để thử chiều về.
Nếu dùng hai iPhone, máy thứ hai dùng `citizen-iPhone-PRIVATE.json` và thao
tác qua cùng bảng. Mỗi file cấu hình có sẵn ID của người còn lại trong kit.

Bảng hiển thị xác nhận ứng dụng đối tác đã nhận yêu cầu. Bấm **Rời RP**
để thu hồi consent trên server. Bảng chỉ xuất hiện khi dùng cấu hình
`--panel`. Muốn tắt, xóa riêng cấu hình RP trong Documents rồi khởi động
lại GTA. Giao diện hiện điều khiển thông báo RP. Tác động lên nhân vật
trong phiên GTA còn cần adapter và kiểm thử riêng.

Bản ký `103c23b` đã xác nhận hai yêu cầu theo cả hai chiều giữa iPhone và
Windows trong một lượt LAN. Lượt khác xác nhận hai nút Tham gia/Rời RP
qua snapshot của cùng lần vào phiên. Xem log đã lọc ở
`baselines/private-rp-iphone-panel-20261119.json`.

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

Để chạy phép thử có đối chứng, thay các bước tạo kit, bật server và mở CLI
Windows bằng một lệnh. `--folder` phải là thư mục mới ngoài Git:

```powershell
python MODULE/tools/run_private_rp_iphone_check.py --ip IP_WIFI_CUA_PC --library C:/private/rp/rp_authority.dll --folder C:/private/rp/iphone-check
```

Khi terminal hiện `ready`, chép đúng file `PoliceRP-Authority-PRIVATE.json`
được báo vào Documents của GTA đã ký, rồi mở lại app. Terminal Windows
xác nhận lần lượt kết nối, tham gia, rời RP và ngắt kết nối. Phiên tự dừng
khi đủ bốn bước hoặc hết thời gian. Đối chiếu `host_witness_passed` với log
`consent_round_trip_passed` trên iPhone trong cùng khoảng thời gian. Một
dòng báo đạt trên PC riêng lẻ chưa chứng minh peer là iPhone thật.

Chưa có hai iPhone, log gameplay, kiểm thử native effects hay regression của
Story/GTA Online. Không phát hành IPA gameplay hoặc bật runtime adapter lúc này.

## Thử Chào hỏi và yêu cầu kiểm tra giấy tờ

Kênh PRP3 tùy chọn chuyển thông báo giữa những người cùng chọn tham gia.
Sender do server lấy từ mTLS. Chỉ phiên kết nối của người nhận mới có thể
xác nhận. Một bên rời hoặc rút đồng ý trước ACK, hoặc hết hạn 3 giây, sẽ hủy
lệnh đang chờ. Nonce giữ qua reconnect; kiểm tra này độc lập với nonce
custody. Yêu cầu giấy tờ không gửi nội dung giấy tờ.

Hai client Windows có thể bật `--social`, rồi mỗi bên gõ `opt-in`. Gõ
`greet 22` hoặc `documents 22` từ ID 11. Người nhận thấy loại tương tác và
RP sender. Người gửi chỉ thấy `recipient_received` khi peer đã xác nhận.

Trên iPhone, cần bản IPA hỗ trợ `social-round-trip-v1`:

1. Tạo kit mới bằng `prepare_private_rp.py ... --ip IP_WIFI_CUA_PC --social-probe`.
   Dùng đường dẫn mới ngoài Git. Bật server bằng `server.json` như trên.
2. Mở client Windows với `--config …/citizen.json --social`, rồi gõ `opt-in`.
3. Chép `officer-iPhone-PRIVATE.json` vào Documents của GTA dưới tên
   `PoliceRP-Authority-PRIVATE.json`, sau đó mở lại app trên cùng Wi-Fi.
4. Khi PC thấy ID 11 đã opt-in, gõ `greet 11` trong vòng 60 giây. iPhone
   xác nhận Chào hỏi và gửi lại yêu cầu giấy tờ. PC tự xác nhận, iPhone
   ghi `result=social_round_trip_passed` rồi đóng kết nối.

Chỉ bật chế độ này qua kit tùy chọn. Client cũ vẫn dùng giao thức consent
bình thường. Phép thử xác minh đường gửi giữa hai RP principal qua server.
Các hành động game tiếp tục cần ánh xạ đúng nhân vật và phiên GTA.

Phép thử ngày 19/11/2026 trên iPhone thật đã ghi
`social_round_trip_passed`. Windows xác nhận iPhone nhận lời chào và máy
Windows nhận yêu cầu kiểm tra giấy tờ ngược lại. Log iPhone lấy qua USB.
Xem `baselines/private-rp-iphone-social-20261119.json`. Hai danh tính RP
qua TLS đã đối chiếu. Phép thử chưa ghép chúng với hai nhân vật GTA.
