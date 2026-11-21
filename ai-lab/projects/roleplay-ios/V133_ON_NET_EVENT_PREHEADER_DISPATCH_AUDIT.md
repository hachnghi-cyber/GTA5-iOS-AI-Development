# GTA V iOS v13.3 — RAGE OnNetEvent pre-header dispatch audit (exact binary)

**Phạm vi:** đọc tĩnh executable GTA5 từ IPA gốc. Không chèn hook, không sửa game, không giả lập đã xác thực sender/session.

Mốc binary: SHA256 `f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc`, UUID `EB122C35-96F4-307F-91C3-A2255DD9C685`. Phép audit trước đã ghim 26 lệnh tại đường `CreateConnection/CloseConnection/P2pDecrypt/HandleReceivedPacket`.

## Khám phá tĩnh mới — thứ tự thực thi

Trong `rage::netPlayerMgrBase::OnNetEvent` tại `0x102024914`, ở nhánh đối tượng event trả loại **4**:

1. Kiểm tra ID số từ `netEvent+0x3c`; event phải có metadata tại `event+0x48` (`0x102024914..950`).
2. Kiểm tra flag manager `mgr+0x8f8`, danh sách peer `mgr+0x128`; so khớp **toàn bộ 32 bit** với ID tại `netPlayer+0x18`, duyệt `netPlayer+0x38` (`0x10202495c..980`). Đây là kiểm tra một handle số trong danh sách; không chứng minh danh tính mật mã hay chủ sở hữu session.
3. Có kiểm tra context global khác (`0x102024988..990`). Dữ liệu payload được lấy qua metadata (`0x102024994..99c`).
4. **`atDelegator1<ReceivedMessageData>::Dispatch` được gọi ở `0x1020249b8`.**
5. **Sau đó mới `netMessage::ReadHeader` ở `0x1020249e4`**, qua `datBitBuffer::SetReadOnlyBytes` (`0x1020249d8`), có điều kiện dừng nếu header lỗi (`0x1020249e8`).
6. Nếu parse đủ byte và message-kind phù hợp, có nhánh đến `HandleNonPhysicalUpdateMsg` ở `0x102024a10`.

### Hệ quả thiết kế

**Hook `ReceivedMessageData::Dispatch` KHÔNG được dùng như bằng chứng header đã được parse hợp lệ**, vì call vào delegator xảy ra *trước* `ReadHeader` trong nhánh đã được xác minh. Điều này không có nghĩa packet chưa được giải mã; tầng decrypt chạy trước theo audit cũ. Mốc Dispatch cũng không chứng minh sender/session của RAGE đã được xác thực. Cần thu bằng chứng runtime **sau** khi header/session/generation được xác minh, kiểm tra disconnect/reconnect và migration trước khi cấp quyền điều khiển người chơi.

Tool mới `v133_interaction/tools/audit_v133_event_route.py` ghim thêm **29 opcode ARM64**, đối chiếu 4 `BL` đích và so lại SHA256/UUID/26 pin gốc; trả về cờ `roleplay_gameplay_enabled=false` và `sender_cryptographic_identity_verified=false` bất kể audit tĩnh PASS.

Tái lập với IPA gốc được sở hữu hợp pháp:

```bash
python3 ai-lab/projects/roleplay-ios/v133_interaction/tools/audit_v133_event_route.py GTAV-v13.3.ipa
python3 -m unittest discover -s ai-lab/projects/roleplay-ios/v133_interaction/tests -p 'test_audit_v133_event_route.py' -v
```

Không đưa game binary, khóa session hay dữ liệu thiết bị cá nhân vào GitHub. Đây là bằng chứng tĩnh; thử nghiệm iPhone với session/peer hợp tác vẫn là cổng chưa vượt qua.
