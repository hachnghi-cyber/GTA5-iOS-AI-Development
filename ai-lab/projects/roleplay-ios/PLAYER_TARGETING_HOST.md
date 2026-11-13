# Roleplay — chọn người chơi thật để tương tác cảnh sát (source-only)

## Mục tiêu

Thêm một bộ chọn mục tiêu trên **host** cho nhiệm vụ RP: thay vì chọn NPC
hoặc vị trí slot ngẫu nhiên, duyệt tối đa 32 người chơi Online và đề xuất
người gần nhất có đồng ý tham gia Police RP.

Hàm mới: `prp_host_find_nearest_cuff_target(host, officer_id,
host_monotonic_ms, &target_id)` trong `P2P/prp_p2p.c`.

## Điều kiện và hành vi đã mã hóa

- Cảnh sát phải kết nối, **opt-in**, có nghề `native_job=0..2` đã được
  engine xác minh, đang nhận ca; tọa độ phải mới trong 2 giây và hữu hạn.
- Người chơi mục tiêu phải có ID khác cảnh sát, đang kết nối, **opt-in** qua
  giao thức xác thực, vị trí hợp lệ và chưa bị còng/áp giải/giam giữ.
- Chỉ chọn trong bán kính `PRP_CUFF_RADIUS_M = 3.25m`; tính bình phương
  khoảng cách 3D bằng `double` để tránh phụ thuộc tính căn bậc hai.
- Nếu bằng khoảng cách, ưu tiên ID nhỏ hơn, **không phụ thuộc thứ tự slot**.
- Không có mục tiêu hoặc bị từ chối: trả `0`, gán `*target_id=0`.
- **Không thay đổi trạng thái người chơi**. Sau khi UI hiện lựa chọn và
  người dùng xác nhận, host vẫn phải xử lý `PRP_OP_CUFF` bằng
  `prp_host_receive` và kiểm lại quyền, consent và khoảng cách tại
  đúng thời điểm thực thi. Mục tiêu có thể đã rời đi sau lúc được đề xuất.

## Điều kiện tích hợp còn thiếu

API đề xuất mục tiêu chỉ hoạt động với bảng `PRP_Host.peers[]` được tạo
từ dữ liệu phiên GTA Online đã được xác thực. Không lấy ID/vị trí/nghề từ
payload RP chưa đáng tin cậy, JSON hay nickname. Không gửi dữ liệu thô qua
UDP. Một adapter còn phải cung cấp game-frame callback thật trên cả host
và khách, native callback chỉ thao tác nhân vật **local**, và kênh truyền
56 byte qua carrier game đã được chứng thực. Chưa xác định các điểm nối
này trong GTA V iOS v12.

Hàm này không thêm nút cảm ứng hay tự tạo arrest animation, và **chưa
chứng minh bắt được người chơi trong game**. Không ảnh hưởng nhiệm vụ
cảnh sát bắt NPC đang có.

## Tái lập kiểm thử

```sh
python ai-lab/host_rp_tests.py --output ai-lab/reports/RP_HOST_C_TESTS.json
python ai-lab/host_rp_tests.py --compiler clang --sanitize-address --sanitize-undefined
```

Test mới `P2P/test_target_selection.c` gồm: không có consent, đổi
thứ tự slot, hòa khoảng cách, mục tiêu bị còng, người chơi không tham
gia, người chơi ngoài phạm vi, tọa độ NaN/tương lai/quá hạn, mất kết nối,
cảnh sát nghỉ ca/sai nghề, ranh giới 3,25 m và host kiểm tra lại sau
khi mục tiêu di chuyển.

GitHub Actions bổ sung test này vào bộ regression C đang chạy; workflow
macOS tiếp tục biên dịch thư viện ARM64 **không ký, không tích hợp IPA**.

**Rollback:** revert `prp_host_find_nearest_cuff_target`, prototype và
`test_target_selection.c`; không cần sửa dữ liệu lưu game hay IPA gốc.
