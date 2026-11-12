# GTA V iOS v12 — Police RP P2P: bắt buộc nối vào engine

**Không phải mod có thể cài trực tiếp.** `prp_p2p.c` và `prp_runtime.c` là mã thực thi độc lập đã kiểm thử, nhưng v12 gốc chưa gọi chúng từ vòng lặp game và chưa có đường truyền gói ứng dụng Police RP được xác minh.

## Hai điểm tích hợp CHƯA có

1. **GTA5 game-frame callback riêng:** cần điểm gọi chạy cho cả chủ phòng lẫn khách khi Online (không phải callback ScriptHook/Menyoo). Mỗi khung hình, gọi `prp_runtime_tick()` bằng `PR_EngineView` do engine xác thực. Cung cấp callback chỉ khóa điều khiển nhân vật LOCAL. Không bao giờ gọi `MacportWorkArrestScene` trực tiếp với Ped của người chơi từ xa.
2. **GTA Online transport carrier:** cần gửi gói `PRP_WIRE_SIZE=56` byte trong kênh truyền được game xác thực người gửi và mã hóa của phiên hiện tại. Phần relay UDP 7788 không giải mã được gói game. **Không gửi 56 byte trên raw UDP chưa được xác thực; không thêm sự kiện RAGE tùy tiện vào ID sự kiện sẵn có**. Từng thiết bị phải có đầu nhận; người chơi không có mod không thấy/không xử lý payload này.

Bắt buộc phải thu thập và cung cấp từ engine: `session_id`, `local_player_id`, `host_player_id`, `trusted_sender_id`, cờ `session_verified`, `channel_authenticated`; vị trí của peer (tối đa 2 giây), nghề và cờ nhận ca đã xác thực, tọa độ vùng đồn có kiểm tra tin cậy. Đừng tin các trường do gói Police RP khai báo là metadata của engine.

## Luồng gọi trên máy chủ phòng (pseudo C)

```c
// Called on GTA5 main game thread, never from socket callback:
PR_EngineView v = verified_local_view_from_engine();
prp_host_update_peer(&rp.host, &trusted_peer_snapshot); // for each player
prp_runtime_tick(&rp, monotonic_ms, &v, &local_callbacks, &game_channel);

// Called on GTA5 main thread AFTER authenticated game networking dispatch:
PRP_TransportContext ctx = trusted_delivery_from_engine();
prp_runtime_receive(&rp, payload, length, &ctx, &v);
```

## Luồng gọi trên máy khách

```c
PR_EngineView v = verified_local_view_from_engine();
prp_runtime_tick(&rp, monotonic_ms, &v, &local_callbacks, &game_channel);
// After game networking verifies host identity:
prp_runtime_receive(&rp, payload, length, &authenticated_context, &v);
```

Các dòng trên mô tả interface cần nối, không phải hàm GTA5 đã tìm được.

## Cơ chế an toàn

- Mỗi phiên/host migration phải gọi `prp_runtime_stop()` rồi `prp_runtime_init()` với ID phiên mới do engine cấp. Trường rỗng hoặc sai phiên sẽ tháo còng và ngừng gửi.
- Người dùng muốn tham gia phải gọi `prp_runtime_consent(..., 1, ...)` trên chính máy mình; tắt tham gia = `(..., 0, ...)`, game-thread tick tháo còng.
- Chỉ làm cảnh sát khi engine xác minh nghề gốc `0/1/2`, `on_shift=1`, có vị trí cập nhật và đã opt-in. Chủ phòng quyết định quyền; máy khách chỉ được gửi yêu cầu, không tự quyết.
- `prp_runtime_action()` trả `PRP_SENT_PENDING=1` trên máy khách tức **đã xếp hàng gửi**, KHÔNG có nghĩa host đã duyệt. Host cần trả gói `STATE` cho người bị bắt, ứng dụng tự áp dụng chỉ trên nhân vật máy đó.
- Gửi heartbeat `STATE` mỗi 500 ms; nếu không nhận >4.000 ms, client mở khóa điều khiển.
- `PRP_OP_JAIL` hiện là trạng thái + thời hạn; **không** có hoạt ảnh, lệnh lên xe, teleport hay đồng bộ vật lý.
- Người dùng v12 thường không có Police RP vẫn chơi Online bình thường, nhưng không thể bị RP bắt hoặc tác động.

## Tìm đường tích hợp trong nhị phân

Tệp `GTA5` của IPA v12 gốc có UUID `6A498E32-E70C-334C-BCA3-AFFD35E8D171` và SHA256 `d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b`.

Các symbol tham khảo từ phân tích tĩnh:

- `MacportWorkTaskFrame`: nhiệm vụ nghề có sẵn, chưa chứng minh là callback mọi người chơi Online.
- `CEventGroupScriptNetwork::AddRemote` và `CEventNetworkScriptEvent`: có trong nhị phân nhưng **không đủ** để chứng minh có thể gửi bản tin tùy ý; cần phân tích sâu định dạng sự kiện/dispatch.
- `CEventNetworkHostMigration`: có dấu hiệu hệ thống đổi host; cần kết nối tín hiệu này với `prp_runtime_stop()`.

Không patch lệnh ARM64/địa chỉ chưa thẩm định và không dùng bản HostGate BETA làm nền. Chỉ build/đóng gói sau khi xác thực hai điểm nối trên bằng log thiết bị thật.
