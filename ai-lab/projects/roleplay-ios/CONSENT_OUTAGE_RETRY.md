# RP-003 — Retry opt-out khi transport GTA Online tạm mất kết nối

**Phạm vi:** bridge C11 source-only, PR #9; chưa được hook vào executable GTA5 iOS.

## Nguyên nhân

`prp_bridge_set_consent(bridge, 0)` từng dựa vào
`prp_runtime_consent(..., 0)` để xóa `runtime.local_opt_in`.
Nếu `send_authenticated` từ chối gói do mất mạng thì hàm trả 0
và giữ `local_opt_in = 1`, dù `want_opt_in = 0`.
Client có thể nhả còng nhờ `pr_adapter_stop`, nhưng trạng thái
`runtime` và host chưa đồng bộ.

## Giải pháp

- Khi người chơi **chủ động opt-out**, đặt `want_opt_in=0`,
  `runtime.local_opt_in=0` và gọi `pr_adapter_stop` ngay tại game thread.
- Nếu `send_authenticated` từ chối, đặt `pending_opt_out=1`
  trong `PRP_GameBridge` (chỉ game thread mới đọc/ghi).
- Với snapshot Online hợp lệ, mỗi `prp_bridge_frame` thử gửi lại
  opt-out một lần; khi vẫn thất bại, giữ local không tham gia RP.
- Ngăn bật lại RP khi revocation còn pending. Sau khi callback gửi
  chấp nhận gói, tiếp tục xử lý theo `want_opt_in`.
- Khi session/host identity không hợp lệ, `prp_bridge_stop` xóa
  mailbox, consent, pending và giải phóng kiểm soát local. Không
  phát lại yêu cầu cũ sang session khác.

**Lưu ý quan trọng:** trả về 1 từ `send_authenticated` chỉ có nghĩa
adapter mạng **nhận gói để gửi**, KHÔNG phải host đã xử lý.
Protocol hiện tại **chưa có application ACK** cho opt-out.
Nếu gói được chấp nhận rồi bị mất trên đường truyền, host có thể còn
lưu consent cho tới khi peer disconnect/tái đồng bộ phiên. Trạng
thái local vẫn bảo vệ người chơi khỏi việc bị hạn chế điều khiển.
Một phiên bản tiếp theo phải có ACK/sequence hoặc snapshot consent
từ server có quyền hạn trước khi cam kết đồng bộ end-to-end.

## Tái lập host test

`Integration/test_engine_binding.c` mô phỏng guest đã bị còng,
adapter gửi mạng lỗi, người chơi tắt consent, đổi ý trong lúc mất
mạng, rồi adapter gửi phục hồi. Kiểm tra local uncuff tức thì,
không gửi opt-in khi revoke pending, đúng thứ tự thử lại, host
xử lý opt-out và giải phóng state mục tiêu sau khi nhận.

`ai-lab/tests/test_engine_bridge_host.py` biên dịch chương trình C
và chạy trên Linux, bao gồm Clang ASan + UBSan. Test này
**không xác minh iPhone/RAGE engine**.

## Không thay đổi

Không chỉnh game data/IPA, native jobs, Menyoo, offline NPC police
hoặc các gói native/transport Windows. Không merge PR tự động.

**Rollback:** revert thay đổi `pending_opt_out` ở
`prp_engine_binding.{h,c}`, đoạn test outage trong
`test_engine_binding.c` và tài liệu này.
