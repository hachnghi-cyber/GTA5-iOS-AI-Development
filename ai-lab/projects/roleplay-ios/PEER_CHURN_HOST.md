# RP-003 — Rà soát churn 32 người trong cầu nối engine (host C)

**Trạng thái:** đã triển khai trên PR nháp #9, kiểm thử host CI;
không phải mod đã tích hợp GTA V iOS hoặc IPA phát hành.

## Nguyên nhân gốc

`prp_bridge_frame` trước đây thêm/cập nhật `trusted_peers` **trước**
khi xóa các ID đã rời từ `PRP_Host.peers`. Khi host đang có
`PRP_MAX_PEERS = 32` slot và một người thoát cùng frame có một
người vào, `prp_host_update_peer` không còn slot để thêm ID mới.
Lỗi trả về từng bị bỏ qua; người mới chỉ xuất hiện trong trạng thái
RP ở frame kế tiếp. Gói consent gửi ngay sau frame đầu có thể bị
từ chối `PRP_ERR_PEER`.

## Thay đổi hẹp

Ở `police-rp/v1.4/Integration/prp_engine_binding.c`:

1. Sau khi `valid(snapshot)` xác nhận danh sách không trùng ID và có
   local+host, **xóa ID vắng mặt trước** theo snapshot đã xác thực.
2. Sau đó cập nhật/thêm các peer đang kết nối. Không đọc consent từ
   snapshot; consent chỉ đến từ gói đã xác thực.
3. Nếu cập nhật peer thất bại dù snapshot hợp lệ (bất biến bị phá),
   `prp_bridge_stop` xóa session, mailbox, local opt-in và nhả còng
   thay vì giữ trạng thái đồng bộ nửa vời.

`prp_host_remove_peer` đã xóa trạng thái còng/áp giải của người
vừa rời, consent và replay-sequence tại slot. Người chơi **không
rời phiên** vẫn giữ consent của mình.

## Kiểm thử và bằng chứng

Test C `police-rp/v1.4/Integration/test_engine_binding.c` mô phỏng:

- Host 32/32 người, ID2 đã opt-in và bị còng, ID3 vẫn opt-in.
- Ngay frame tiếp theo ID2 rời, ID33 xuất hiện cùng slot.
- Vẫn đủ 32 người sau **chính frame này**; ID33 không thừa hưởng
  consent/còng/replay-sequence của ID2.
- Consent ID3 được bảo toàn. Gói consent hợp lệ đầu tiên từ ID33
  được xử lý ngay mà không chờ thêm một frame.

Chạy trong `ai-lab/tests/test_engine_bridge_host.py` bằng compiler
C11 host bình thường và Clang ASan+UBSan; bộ CI khác vẫn chạy
theo cấu hình đã có trên nhánh. Kết quả:
https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43366201979

**Không được diễn giải** host simulator là RAGE multiplayer thực.
Chưa xác minh nguồn identity/session, callback game-frame, carrier
mạng đã xác thực, xử lý trên iPhone, ký IPA hoặc test hai thiết bị.

## Rollback

Revert đúng phần đổi thứ tự duyệt host peer trong
`prp_engine_binding.c` và case churn bổ sung trong
`test_engine_binding.c`; không thay đổi IPA, chứng chỉ hoặc dữ
liệu lưu game. Không merge PR khi các test fail.

## Bước tiếp theo

Xác minh nguồn `PRP_GameSnapshot` từ engine GTA v12
và callback game-frame trên iPhone thực, sau đó mới kết nối UI
Roleplay và test multiplayer giữa hai thiết bị.
