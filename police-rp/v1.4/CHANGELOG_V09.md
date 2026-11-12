# Police RP Only v0.9 — ARM64 call-graph audit + off-duty release

**Tình trạng:** Mã nguồn nghiên cứu. CHƯA tích hợp vào game, CHƯA có dylib iOS/IPA chơi được.

## Điều chỉnh có thể kiểm tra

1. Sửa `prp_host_update_peer()` của lõi P2P: khi cảnh sát kết thúc ca (`on_shift=0`), chuyển sang nghề khác (`native_job` không phải 0..2), hoặc mất xác thực nghề (`job_verified=0`), chủ phòng trả trạng thái còng/áp giải của người do cảnh sát đó quản lý về `PR_FREE`. Nếu đã có án tù `PR_JAILED`, giữ đến khi hết thời hạn như trước.
2. Có kiểm thử mới `P2P/test_duty_exit.c`: đi qua đồng ý tham gia -> còng -> hết ca -> thả, từ chối bắt tiếp, thu hồi quyền khi không xác thực nghề, bảo toàn án đã tuyên cho đến khi hết hạn.
3. Thêm `Tools/inspect_v12_calls.py`: phân tích toàn bộ section `__TEXT,__text` của **đúng GTA5 v12** qua SHA256 + LC_UUID; giải mã ARM64 `BL` và báo các callsite cho Online/Jobs/Task/Arrest. Chỉ đọc, KHÔNG vá IPA.
4. Đã biên dịch lại 6 tệp ARM64 Mach-O object và chạy bộ kiểm thử native/Python trên Linux.

## Kết quả ARM64 (BL direct)

- `MacportOnlineUpdate` `0x1000E01A0`: **không thấy BL trực tiếp** đến hàm này; có thể được gọi qua function pointer/callback. Không khẳng định nó không chạy.
- `MacportJobsUpdate` `0x1000EA024`: gọi từ `MacportOnlineUpdate + 0x4FE8` (lệnh tại `0x1000E5188`).
- `MacportWorkTaskFrame` `0x100112010`: gọi từ `MacportOnlineUpdate + 0x6C40` (`0x1000E6DE0`).
- `MacportWorkArrestScene` `0x10011BC8C`: gọi ở `0x100117D08` trong hệ thống NPC.

Xem `ARM64_CALL_XREF_V12.json` và script kiểm tra. Kết quả này **không chứng minh** có thể hook tại đây an toàn và không chứng minh `MacportOnlineUpdate` luôn chạy trên game thread.

## Còn thiếu

- Xác minh điểm vào frame callback / register function pointer của GTA5.
- Authenticated transport binding từ mạng Online thực tế với peer ID đáng tin cậy.
- Callback áp dụng hoạt ảnh lên local ped, chọn người chơi và UI đồng ý tham gia.
- iOS SDK/macOS link dylib, tích hợp/đóng gói IPA, ký lại và test hai iPhone.

**Không dùng bản Menyoo Online Beta làm nền. Không bật ScriptHook Online. Không thay đổi IPA gốc.**
