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


## Thu một mẫu game loop từ Windows qua USB

Bản Phase 9 đã cài và ký phát triển cho phép attach. Trên iOS 18.6, CodeLLDB
trên Windows dừng trong handshake với debugproxy chưa có tiến trình. Đường
attach trực tiếp vào PID của GTA đã chạy được theo giao thức debug chuẩn.
Tool chỉ đọc header Mach-O và các lệnh được allowlist, dùng một hardware
breakpoint ở `jobs_update`, rồi gỡ breakpoint và detach trước khi xuất JSON.
Nó không cài IPA hoặc sửa bộ nhớ GTA. [GDB Remote packets](https://www.sourceware.org/gdb/current/onlinedocs/gdb.html/Packets.html)

Với iPhone đã tin cậy máy tính, Developer Mode đã bật, DeveloperDiskImage
đã mount và scene Sandbox đang ở foreground, chạy từ thư mục dự án:

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py <bundle-id-GTA-da-cai>
```

Nếu debugproxy ngắt ngay ở `qSupported` trước attach, kiểm tra DeveloperDiskImage
sau khi reconnect/reboot. Trong lần thử 2026-11-16, ba lần handshake bị
`WinError 10053`; sau lệnh dưới, `jobs_update --stock-job` đã lấy mẫu thật.
Đây là điều kiện khôi phục đã quan sát, chưa chứng minh mọi lỗi 10053 cùng nguyên nhân.

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python -m pymobiledevice3 mounter auto-mount
```

Lệnh dùng cơ chế developer chính thức, yêu cầu Developer Mode và có thể tải
image từ Apple. Không cần cài lại IPA. Mẫu local job thật và giới hạn lần đo
được lưu tại `baselines/v133-stock-job-device-20261116.json`.

Bundle ID phải là của bản GTA đã cài. Công cụ tự tra PID và giữ debugproxy
trên loopback. Timeout khi app ở background đã được thử và breakpoint
được gỡ trước khi thoát. Kết quả chỉ có nhãn luồng theo mẫu, PC trúng điểm
đo, và LR khớp lệnh gọi trực tiếp đã đối chiếu. Đây là bằng chứng callback
chạy, chưa đo nhịp frame hoặc xác minh luồng nhận scripted event.

## Windows USB: scripted-event observation (source-only extension)

The same existing Python USB observer can now sample four **exact-build,
read-only** entry points individually. This is useful when only a Windows
computer is available. It requires the development-signed application already
running, USB trust, Developer Mode, and a working debugproxy connection.

From the repository root, in PowerShell:

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py com.macport.gtav --site on_net_event --wait-seconds 30
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py com.macport.gtav --site script_event_handler --wait-seconds 30
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py com.macport.gtav --site script_decide --wait-seconds 30
```

Use the actual bundle identifier if signing added a supported suffix.
Start the controlled Sandbox session **before** invoking the script.
Each invocation attaches, validates the running Mach-O UUID and the four
allowlisted ARM64 instruction words, installs one hardware breakpoint,
continues for at most 30 seconds, clears the breakpoint, and detaches.
The stop temporarily pauses the game. This tool is intended for a test
session and should not be used with unrelated players.

Capture a baseline without peers, then repeat with a cooperating peer
performing an ordinary in-game event. Preserve the output JSON and a
short description of each action, including whether the peer was present.
A stop at `on_net_event`, `script_event_handler` or `script_decide`
**does not** by itself establish network origin, sender authentication,
game session generation, custom payload delivery or valid Roleplay behavior.
The observer deliberately reports these as unverified. It reads no event
payload, entity memory, account tokens or player identifiers.

The command `--stock-job` is only permitted with
`--site jobs_update`. The existing default `jobs_update` mode remains
unchanged for old command lines. Valid `--wait-seconds` are 1 through 60.

To graduate from this PC-only trace to engine transport integration, capture
a genuine receive stack with LLDB (or an equivalent *validated* call stack),
then separately establish a session-bound sender identity and its lifetime.
Without that evidence, Police RP gameplay remains disabled.

## Receive context — phân biệt đường nhận với dispatch nội bộ

Tại đúng entry của `script_event_handler`, tùy chọn mới đọc tối đa bốn frame
đã đối chiếu và frame nguồn. Nó kiểm tra tám hash thân hàm trước khi đặt
hardware breakpoint, đọc các tham chiếu sender/destination và so connection ID.
Không đọc payload, khóa, tên hay xuất ID/con trỏ. Xem `ENGINE_INTEGRATION_MAP.md`
để biết ABI, lifetime và giới hạn. Đây là mã đã test bằng fixture; chưa có
mẫu runtime của tùy chọn này.

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py <bundle-id-GTA-da-cai> --site script_event_handler --receive-context --wait-seconds 30
```

Phép đo: dùng bản đang ký phát triển, Sandbox foreground; lấy mẫu không peer
rồi với peer hợp tác tạo một sự kiện game bình thường. Không bơm custom packet.
`context_status=observed` cùng `observed_path=engine_receive_dispatch` cho biết
chuỗi frame nhận khớp. `engine_source_association_observed=true` chỉ cho biết
tham chiếu và connection ID tại điểm dừng khớp. `local_sendbuffer_dispatch`
chứng minh đó là nhánh nội bộ nên không tính là nhận remote. Timeout hay một
frame không khớp không chứng minh transport không hỗ trợ; ghi nguyên trạng
và đối chiếu call path khác trước khi sửa profile.

Mọi cờ authenticated sender, session generation, custom RP event vẫn false.
Exit code 1 nếu không trúng breakpoint hoặc context không đầy đủ. Lỗi đọc
vẫn đi qua gỡ breakpoint và detach; không đổi sang software breakpoint.

## Session context

Tùy chọn `--session-context` dùng tại `jobs_update`. Công cụ kiểm tra hash
của hai wrapper `NETWORK_*_GET_IN_PROGRESS` và getter chung trước khi đặt
breakpoint. Khi PC và caller khớp, nó chỉ đọc bit 0 ở hai vị trí mà getter
dùng cho phiên chính và phiên chuyển tiếp. Dữ liệu xuất gồm hai cờ boolean.

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py <bundle-id-GTA-da-cai> --site jobs_update --session-context --wait-seconds 10
```

Mẫu thật ngày 2026-11-17 ghi `main=false`, `transition=true`. Dùng phép đo
để phân biệt trạng thái lúc vào phòng và lúc chơi trong phiên thử có peer.
Phiên quan sát này chưa có mẫu từ `script_event_handler`, vì vậy chưa thể
gắn hai cờ trạng thái với một scripted event cụ thể.

## Phase 19: theo một event qua hàng đợi bằng USB

Chạy trong Sandbox thử riêng trên bản đã ký phát triển. Nếu có người thứ hai,
dùng thao tác game gốc đã thống nhất trước để kích hoạt lưu lượng đối chứng.

Nếu cả hai iPhone đều cắm USB, thêm `--udid <mã-thiết-bị-đích>` để tra PID và
attach trên cùng một máy. Xem mã cục bộ bằng `pymobiledevice3 usbmux list`
và dùng mục có `ConnectionType: USB`.

```powershell
uv run --python 3.13 --with pymobiledevice3==11.56.0 python ai-lab/projects/roleplay-ios/v133_interaction/tools/observe_v133_windows_usb.py <bundle-id-GTA-da-cai> --queue-context --wait-seconds 30
```

Trong một lần attach, observer lấy mẫu lúc `Unpack` chuẩn bị đưa event vào
queue, xác nhận queue mà `Dispatch` đã đọc cùng event ở `DispatchEvent`, rồi
kiểm tra event tại điểm `OnNetEvent` chọn sender. Hai điểm cuối phải cùng luồng.
Nếu `DispatchEvent` trả về trước, observer ghi `returned_before_predispatch`
và dừng. Nếu trúng event khác, bộ đo trả trạng thái mismatch. Mỗi lần attach
chỉ theo một event và gỡ các hardware breakpoint trước khi detach.

`queue_object_link_candidate_only` là dấu vết liên hệ theo địa chỉ đối tượng
trong một lần đo. `native_candidate` ghi kết quả đối chiếu connection với
netPlayer đã chọn. Các trường xác thực sender, thế hệ phiên và quyền RP
vẫn tắt. Timeout hoặc mismatch giới hạn phạm vi của mẫu đo.

`enqueue_transport` ghi một byte chỉ báo dưới dạng `set`, `clear` hoặc
`unobserved`. Công cụ kiểm tra thân hàm, frame `HandleReceivedPacket → Unpack`
và connection manager trước khi đọc byte, khi cả hai frame vẫn còn sống.
Giá trị chỉ áp dụng cho event ở mốc enqueue. Để gắn nó với mốc nhận, mẫu còn
phải qua kiểm tra queue và `OnNetEvent`. Xác thực transport và ràng buộc phiên
cần bằng chứng riêng.
