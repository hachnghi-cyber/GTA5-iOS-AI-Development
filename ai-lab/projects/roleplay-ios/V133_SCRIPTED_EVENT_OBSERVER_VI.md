# GTA v13.3 — kiểm tra scripted event trên iPhone

## Đã đối chiếu trên binary gốc

- Type `0x1c` đăng ký `CScriptedGameEvent::EventHandler` vào đúng bảng mà
  `netEventMgr::ProcessEventData` đọc trước khi nhảy vào handler. Stack event
  cài vtable chính. Hai slot Handle và Decide có chained fixup trỏ đến đúng
  phương thức. Handler chuyển tiếp hai tham chiếu người chơi, không có tham
  số xác thực hoặc session generation riêng.
- `Handle` đọc độ dài 32 bit, chỉ đọc payload nếu có độ dài 1–432 byte.
  Carrier 56 byte nằm trong giới hạn này. Cần thử nghiệm route và payload
  thật trước khi kết luận tương thích. Stock MPJ2 không bị sửa.
- `ClearSession` gọi `snSession::GetSessionId`. Đường tra endpoint kiểm tra
  thành viên và tra peer connection/endpoint của session gốc. Các địa chỉ
  này chỉ là ứng viên để quan sát. Chưa xác minh được phép nối từ connection
  của từng event đến session ID hay generation, kể cả qua migration.
- Đối chiếu Phase 9: Winstom 0.7.177 có dấu hiệu transport riêng. Việc này
  không cung cấp ABI hoặc nguồn metadata xác thực cho GTA v13.3.

## Thu mẫu

Dùng bản Phase 9 đã boot được nếu bản ký cho phép debugger attach. Cần Mac
có Xcode, iPhone đã ghép đôi và app ký để phát triển. Nếu Xcode từ chối
attach, dùng bản ký phát triển thích hợp hoặc chuyển log stock mới để phân
tích phần nào log ghi được. [Apple Developer Mode](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)
và [Apple Xcode debugger](https://developer.apple.com/documentation/xcode/diagnosing-and-resolving-bugs-in-your-running-app)
mô tả điều kiện và cách attach.

1. Attach đúng app đang mở trên iPhone và Pause trong Xcode. Dùng phiên
   Sandbox thử riêng vì debugger tạm dừng game khi trúng breakpoint.
2. Trong LLDB, import `v133_interaction/tools/observe_v133_lldb.py` bằng đường
   dẫn đầy đủ. Giữ thư mục `baselines` cùng cấp với `v133_interaction`.

   ```
   command script import "/path/to/v133_interaction/tools/observe_v133_lldb.py"
   prp-arm jobs_update
   continue
   ```

3. Khi LLDB dừng tại điểm đã đặt, chạy `prp-capture` và lưu dòng JSON. Lặp
   lại cùng phiên debug với `script_event_handler` và `script_decide` lúc
   người thử khác thực hiện tính năng Sandbox gốc phát sinh sự kiện.
   Có thể dùng `on_net_event` để lấy mẫu đối chứng.
4. Thử `clear_session` lúc rời phiên và `migrate_end` nếu có migration
   trong phiên thử. Nếu không trúng, Pause và chạy `prp-disarm`; ghi rõ
   điểm nào chưa quan sát được. Gửi các dòng JSON, thao tác đã làm và chế
   độ đang chạy. Không cần gửi địa chỉ hoặc token.

Observer kiểm tra UUID ARM64 và lệnh tại điểm lấy mẫu trong process, sau đó
dùng một hardware breakpoint tự xóa sau một lần trúng. Nó ghi nhãn luồng
trong cùng phiên attach và danh sách symbol đã biết. Không sửa code hoặc
payload, không chạy hàm game, và không thu khóa hay định danh người chơi.
Thiếu frame hoặc có cả hai đường gọi thì giữ kết quả chưa xác định.
Các mẫu stack chỉ xác minh context; cú trúng breakpoint không đo được nhịp
frame, lifetime hay metadata xác thực. Các cờ auth/generation luôn false.
[LLDB SBBreakpoint](https://lldb.llvm.org/python_api/lldb.SBBreakpoint.html)

## Tiêu chí trước khi kết nối PRP3

Cần mẫu scripted event có stack nhận từ mạng và mẫu giao nội bộ để đối
chiếu. Tiếp theo phải chứng minh connection của **chính event** gắn với
sender, session ID và generation còn hiệu lực, rồi chứng minh invalidation
khi rời phiên hoặc migration. Chỉ copy dữ liệu hợp lệ trong callback. Khi
chưa có bằng chứng này, carrier và các thao tác Police RP giữ tắt.
