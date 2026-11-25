# WINSTOM 0.7.171 → GTA V iOS v13.3 — PHASE 6

**Ngày thực hiện:** 16/11/2026.  **Phạm vi:** phân tích tĩnh đọc-only trên binary Winstom đã cung cấp + phát triển công cụ kiểm chứng log nguồn mở độc lập. Không chỉnh sửa IPA, không giải mã tài sản WSPK, không giả định có máy chủ RP khả dụng hay callback RAGE đã xác thực.

## A. Binary và source đã kiểm chứng

- Đã mở lại `/mnt/data/Winstom-0.7.171.ipa` và `lmx.dylib` được trích từ IPA phiên trước. Hash Winstom IPA theo baseline: `9459b8753e1e8e171ec7da52624466cd2cfd6396a802415e7fa18814efeb0126`. `lmx.dylib` UUID `003F682B-D578-332C-840E-7B789CD594DC`.
- Đã đọc file `LMX_OBJC_MAP.json` trong gói reverse-engineering Phase 4 (26 class ObjC, 357 methods linked), và kiểm tra `llvm-objdump` ngay trên `lmx.dylib`.
- **Đính chính kiến trúc:** `WRTransport` có `URLSession:*` callbacks (HTTP requests/redirect/response/data). `WRAccountSession` có `validToken:`, `saveToken:mode:lifetime:` (account session). `WRVoice` có `openHost:port:ticket:`, `encodeAndSend`, `receive` (voice/audio). Các lớp này *không tự chứng minh* đã có authenticated sender/authority của GTA gameplay. Cần tìm lớp native C++ `westrayn-core` riêng.
- Phân tích disassembly tại `0xbc2ec` của `lmx` tiếp tục xác nhận `objectForKeyedSubscript:` đọc `cuffed` (sau đó lưu tạm trong object tại offset nội bộ); không phải lời gọi native còng tay. Phân biệt rõ trạng thái **được đọc** với hành động **thực thi và đồng bộ**.

## B. Đối chiếu với bằng chứng test v13.3 đang có

- Bộ nguồn R19/H6 (từ file người dùng): báo cáo H5 có 1 dòng tick, 8 mẫu `Decide` và 8 mẫu `MPJ2`; mọi bản ghi được phân tích đều `sender_auth=0`, `gameplay=0`. Mẫu chỉ giới hạn 8 dòng, **không phải tổng số event hay tổng người chơi**.
- Trong H5, `sender_ptr`, `slot_hint` và `event_obj` là con trỏ/hint được quan sát, chưa phải chứng thực độc lập danh tính sender. `PRP3` 40-byte packet cũng không bao gồm sender; chỉ transport thực với metadata engine-owned mới cấp được sender.
- Kết luận P0: **không có bằng chứng đủ để kích hoạt còng/áp giải trên v13.3**. Vấn đề chính vẫn là `authenticated source of sender / session` từ RAGE hoặc hệ thống tương đương đã chứng minh.

## C. Công việc triển khai Phase 6

Bổ sung công cụ `tools/verify_device_trace.py` và 13 unit tests `tests/test_verify_device_trace.py`. Công cụ chỉ đọc 2 file JSONL để **đối chiếu log sự kiện** trên hai thiết bị, không sửa game và không gửi mạng.

Đầu vào một bản ghi JSONL gồm:

```json
{
  "schema":"prp3-device-trace-v1", "device_id":"iPhone-A", "direction":"tx",
  "build_uuid":"EB122C35-96F4-307F-91C3-A2255DD9C685",
  "source":"engine-authenticated", "authenticated":true, "on_game_thread":true,
  "session_id":222, "session_epoch":7, "local_player_id":101,
  "remote_player_id":202, "monotonic_ms":100,
  "wire_hex":"5052503301010000de00000000000000ca0000000000000007000000000000000b00000000000000"
}
```

> Đây là **schema minh họa**, không phải log GTA V thật. Các trường `source`, `authenticated` và `on_game_thread` do nguồn log khai báo và **KHÔNG phải bằng chứng mật mã**. Tool mặc định từ chối `fixture_only=true`; chỉ nhận ví dụ giả lập khi bật `--allow-synthetic-demo` và gắn `synthetic_demo=true` trong báo cáo. Tool luôn trả `transport_provenance_cryptographically_attested=false`, `safe_to_enable_cuff_or_escort=false` ngay cả khi hai log khớp.

Các bước kiểm tra: `PRP3` đúng 40 byte, little-endian, magic/version/kind, reserved=0, session/epoch/receiver/nonce khác 0; đối chiếu session+epoch với metadata; receiver từ `tx` khớp `rx`; sender transport metadata của `rx` khớp local player của `tx`; source/build/game-thread/consent được khai báo; từ chối mismatched sender, peer, nonce, duplicate, local clock regression, self-interaction, mixed device logs, thiếu xác thực. Không so sánh trực tiếp monotonic_ms của hai thiết bị vì không cùng đồng hồ.

## D. Lệnh kiểm thử đã chạy

```bash
python -m unittest discover -s tests -p 'test_verify_device_trace.py' -v
python -m compileall -q tools/verify_device_trace.py
```

**Kết quả:** PASS 12/13 unit tests. Test khác của Phase 5 được chạy lại trên toolchain GCC và Clang (ba executable mỗi toolchain), đều PASS. Đây là host synthetic tests, không phải iOS device test. GitHub Actions trên PR #16 vẫn failure (log từ connector trả `BlobNotFound` trước đây); chưa có bằng chứng CI xanh.

## E. Chẩn đoán thực tế và bước tiếp theo

1. Đọc log H5/H6: `sender_auth=0` ⇒ tuyệt đối không gọi `rp_v133_wire_deliver` với cờ xác thực tự đặt. Chỉ capture read-only và thêm trường provenance do engine xác minh.
2. Xác định callback nhận `CNetGamePlayer` + `Session/Peer ID` từ RAGE; xác định pointer lifetime/ABI trên v13.3 UUID cố định. Không coi `MPJ2.slot_hint` hoặc pointer trần là danh tính.
3. Khi có 2 iPhone và kênh private authenticated, gửi duy nhất `greet` trong phòng thử nghiệm, lưu `TX.jsonl` và `RX.jsonl`, chạy tool trên hai file để kiểm tra tính nhất quán. **Tool không chứng thực log được tạo bởi engine**; cần log nguồn/stack từ thiết bị và thử nghiệm thực tế riêng.
4. Chỉ sau khi A→B được xác nhận bởi thiết bị và đối chiếu source, mới triển khai giao dịch state `cuff`/`escort` có opt-in, authority và rollback.

**Không tạo IPA RP có thể chơi trong Phase 6**, không giả định động cơ Winstom dùng cùng ABI với v13.3.