# Luật Police RP v13.3

`rp_v133_police.c` chạy ở một trình xử lý có quyền quyết định trong một
phiên RP. Nó dùng metadata sender/session/generation đã xác thực, trạng
thái đã chọn tham gia và snapshot do phía có thẩm quyền cung cấp. Snapshot
phải khớp đúng cặp người chơi, phiên, generation và thời điểm không quá
250 ms trên cùng đồng hồ đơn điệu của authority. Cửa sổ này là chính sách
thử nghiệm. Sau giật hoặc pause, cần lấy snapshot mới. Payload
chỉ yêu cầu một thao tác, có nonce. Nó không cấp quyền, cung cấp khoảng
cách hay tự chứng nhận danh tính.

| Thao tác | Điều kiện và kết quả chính |
| --- | --- |
| Nhận ca | Người chơi đồng ý tham gia, được cấp vai cảnh sát và có job gốc hợp lệ |
| Còng, tháo còng | Trong phạm vi 4 m, cùng phiên game và cả hai đã đồng ý. Người còng quản lý trạng thái đang giữ |
| Áp giải | Bắt đầu khi đang còng, kết thúc về trạng thái đã còng |
| Lên/xuống xe | Đưa người đang áp giải vào ghế khách trống của xe cảnh sát. Xuống đúng xe và vẫn còng |
| Nhà tù | Xác minh cả hai ở cổng tiếp nhận, bắt đầu án thử 60 giây. Hết giờ hoặc có lệnh thả hợp lệ thì trả tự do |

Rời phiên, bỏ ca hoặc rút đồng ý dọn trạng thái giữ theo chính sách thử.
Reconnect trong cùng generation giữ nonce đã dùng. Một lệnh có envelope
hợp lệ đã xác thực sẽ tiêu thụ nonce kể cả khi bị từ chối. Sau đổi generation
phải lập lại phiên và quyền. Kiểm thử C dùng snapshot giả lập để kiểm tra
luật, bao gồm giả danh, ghế trùng, timestamp tràn và lệnh sau ngắt kết nối.

Probe iOS hiện có chỉ dành cho thử TLS GREET/DOCUMENTS. Các quyết định
trong module này chưa được gửi qua TLS hoặc áp dụng lên game. Trước khi
tích hợp, cần nối ID TLS với người chơi game đã đồng ý, chuyển snapshot
và kết quả trên callback đã xác minh, rồi thử hành động trên hai thiết bị.


## Yêu cầu và ACK

`rp_v133_police_tx.c` tách lệnh Police khỏi GREET/DOCUMENTS. Lệnh
`PRPC` và ACK `PRPA` đều 40 byte: magic (4), version (1), operation (1),
trạng thái ACK hoặc zero của lệnh (1), reserved zero (1), rồi lần lượt
session, target, generation và nonce (mỗi trường uint64 little-endian).
Sender lấy từ metadata kênh đã xác thực. Client đối chiếu cả 5 trường
của lệnh đang chờ trước khi chấp nhận ACK từ phía có thẩm quyền.

Mỗi sender chỉ cache ACK của giao dịch gần nhất. Gửi lại đúng giao dịch
này trả lại nguyên quyết định đã cấp mà không chạy lại thao tác. Nếu đổi
target/operation nhưng giữ nonce, hoặc yêu cầu cũ hơn cache, authority
từ chối. ACK chỉ ghi quyết định ban đầu. Nó không phải trạng thái mới
nhất và không thể dùng riêng để áp lại hành động trong GTA.


## Biên nối giữa kênh RP và engine

`rp_v133_police_bridge.c` nhận đăng ký ghép cặp đã được xác minh độc lập
từ phía có thẩm quyền. Liên kết 1:1 giữa ID của TLS và ID game giữ một
mã lần gia nhập tăng dần trong generation của game. Khi rời phiên, yêu
cầu và ACK gắn với người chơi cũ mất hiệu lực, đồng thời dọn trạng thái
giữ phía authority. Replay counter giữ qua reconnect. Khi đổi generation
cần ghép cặp và đồng ý tham gia lại.

Hàm dispatch liên kết các lệnh với hai thành viên đang hoạt động. Snapshot
còn phải khớp ID game, lần gia nhập, phiên/generation và instance thực.
Thông tin vị trí, job và xe chỉ đến từ snapshot của authority. Mỗi lượt
đăng ký chỉ xảy ra sau khi đã xác minh đúng người trên cả hai phía. Module
chưa tự tìm nguồn xác minh này trong GTA. Test host dùng dữ liệu được cấp
để kiểm tra mapping, chống tráo người sau reconnect và khóa khi đổi phiên.

Đối chiếu tĩnh trên GTA v13.3 đã xác nhận `MacportJobStart` ghi ID và loại
job vào metadata cục bộ. Hàm được gọi từ `MacportOnlineCommand` và cả đường
`MacportJobsUpdate`. Nhánh cleanup trong bộ xử lý lệnh xóa trạng thái job
sau khi gọi hàm cleanup. Log iPhone trước đó ghi `work cop_ls` và `work quit`.
Metadata job mới là ứng viên kiểm tra điều kiện nhận ca. Nó không cấp vai
cảnh sát hay chứng minh người gửi đã được xác thực. Chưa có đo bộ nhớ thời
điểm nhận và bỏ ca trên iPhone với observer mới.


Có thể thêm `--stock-job` vào lệnh observer USB Windows đã dùng trước đó.
Sau khi đối chiếu UUID, instruction và điểm dừng trong `jobs_update`, nó
đọc đúng 40 byte của trường ID job và hai số trạng thái/loại job. Log chỉ
cho biết ID có phải `cop_ls` hoặc rỗng hay không, cùng hai mã số. Không in
ID lạ, địa chỉ hay token. Lấy mẫu ba mốc chưa nhận ca, đã nhận, đã bỏ ca
trong Sandbox. Mã job vẫn chỉ là điều kiện, chưa có quyền Police RP.
