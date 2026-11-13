# GTA V iOS v12 Roleplay — Kế hoạch tuần tự, có cổng nghiệm thu

**Phiên bản kế hoạch:** 2026-11-13 · **Phạm vi:** GTA V iOS ARM64 v12 / Police RP → Roleplay mở rộng.  
**Quy tắc:** xử lý theo thứ tự **P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9**. Chỉ đánh dấu giai đoạn `verified` khi toàn bộ tiêu chí nghiệm thu có bằng chứng thật; không coi CI giả lập là bằng chứng chạy GTA trên iPhone. Không tự merge, ký hoặc công bố IPA.

## Bản đồ hiện trạng thực tế (không dựa vào suy đoán)

- **P0 đang thực hiện:** baseline v12 đã có metadata; `main` chưa hợp nhất các bản nháp. Các PR: #7 nhận dạng binary, #4 kiểm kê/lõi Police RP, #9 bridge snapshot, #8 cổng kiểm tra phát hành.
- **Đã có mã nguồn:** Police RP v1.4 C11, P2P/NativeBridge, mailbox, engine bridge giả lập, mô phỏng carrier, lựa chọn người chơi, kiểm thử GCC/Clang/ASan/UBSan; đã có build thư viện source-only cho iPhoneOS ARM64.
- **Chưa có bằng chứng:** hook game-frame và metadata authenticated RAGE Online trong GTA5 v12, local-ped native callback đủ an toàn, tích hợp live, 2 iPhone vào cùng phiên RP, IPA đã ký và kiểm thử.
- **Fingerprint bất biến v12 (metadata):** IPA SHA256 `23c039cb59e24f0107243a32252a3a60fbca1c934ac482d285109c323132f0dc`; GTA5 executable SHA256 `d252115585d8f81987fa88138e89e190d42a7ca8134421f0a5f639af27c8585b`; Mach-O UUID `6A498E32-E70C-334C-BCA3-AFFD35E8D171`. Một bản build khác phải được fingerprint lại, không áp dụng offset/hook cũ bằng suy đoán.

## P0 — Chuẩn hóa repository, baseline và PR (ĐANG LÀM)

**Mục tiêu:** thống nhất đúng một đường phát triển và nguồn sự thật, tránh việc các nhánh ghi đè `state.json`, xung đột source và tuyên bố đã phát hành nhầm.

**Công việc theo thứ tự:**
1. Kiểm tra `AGENTS.md`, `CONTINUE_HERE.md`, `ROADMAP.md`, `state.json` trên `main` và từng PR.
2. Đối chiếu nguồn đã có ở PR #4/#9, test C/Python, `ldylib` iPhoneOS, bản chứng minh build, fingerprint và các dependencies.
3. Review từng PR theo thứ tự đề xuất **#7 → #4 → #9 → #8**, xử lý conflict/cherry-pick riêng biệt. Không merge khi chưa có review/quyền; PR #9 phải build lại với nguồn cuối PR #4.
4. Chạy unit tests, C host tests, sanitizers, CI source watch; kiểm tra `state.json` không bịa thử nghiệm thiết bị; tạo bản ghi commit/SHA/evidence.

**Đầu ra:** nhánh integration sạch; ma trận PR→commit→test; baseline và danh mục API có nguồn dẫn; tài liệu bàn giao.

**Gate P0:** fingerprint và merge/diff được review, toàn bộ CI liên quan thành công trên integration tip, không còn xung đột `state.json`, rõ người duyệt. **Chưa đạt:** PR nháp vẫn chưa merge.

## P1 — Xác minh ABI, game-frame callback và danh tính Online (BLOCKED)

**Đầu vào bắt buộc:** P0 đã verified; IPA v12 có quyền phân tích, bản thực thi đúng SHA/UUID, log diagnostic ở thiết bị được phép.

**Việc làm:**
1. Phân tích read-only Mach-O/dyld và symbol/callgraph để xác định điểm callback **game-thread** của v12, thứ tự tick, lifetime/ownership và rủi ro reentrancy.
2. Chứng minh nguồn tin cậy cho `session_id`, `local_player_id`, `host_player_id`, danh sách 32 peer, trạng thái connected, vị trí, job/duty và thay host; không lấy từ nickname/payload giả mạo.
3. Gắn adapter typed C/ObjC++ vào `PRP_GameSnapshot`, `prp_bridge_frame` và callback chỉ thao tác local ped; kiểm tra ABI, timestamp, lần reset, null/sai version.
4. Log có định danh bản build và symbol/offset đã chứng minh; thử vào/ra phiên và reconnect, kiểm chứng fail-open: không giữ còng khi mất snapshot.

**Đầu ra:** `integration/engine_v12_adapter` hoặc bản patch độc lập có logging, ABI contract, crash traces.

**Gate P1:** log từ máy thật chứng minh frame callback thực và danh tính cả host/client xác thực; đối chiếu đúng executable SHA/UUID; không có crash/lệch thread ở bài thử. **Hiện bị chặn:** chưa xác minh hook.

## P2 — Carrier có xác thực, protocol và lifecycle 32 người (BLOCKED bởi P1)

**Việc làm:** chọn carrier riêng đã được xác minh (RAGE authenticated message route hoặc backend độc lập có danh tính/session cryptographically bound, không UDP thô/đoán event ID). Duy trì `PRP6` payload 56 byte và carrier PRC1 theo version; negotiate version, opt-in/out, sender provenance, host authority, sequence/replay, bảo vệ độ dài, frame budget/mailbox 64 slot, TTL, timeout và host migration; kiểm thử packet loss/duplicate/reorder/fuzz. Không đọc game natives trong network callback.

**Đầu ra:** adapter mạng iOS↔RP với protocol manifest, transport mock + log xác thực thật, security review.

**Gate P2:** hai endpoint thiết bị trao đổi consent và heartbeat qua carrier đã xác minh; sender/session không lấy từ payload; gói giả, replay, session cũ bị từ chối; các thao tác ngắt kết nối nhả khóa local an toàn. **Chưa có carrier thực tế.**

## P3 — Vertical slice Police RP tối thiểu, 2 iPhone (BLOCKED bởi P2)

**Phạm vi chỉ có:** bật/tắt Police RP, duty verified, hiển thị chọn người chơi thật gần nhất, còng/tháo còng, mất kết nối tự nhả, nút điều khiển tối thiểu. Không mở thêm EMS/taxi hoặc hệ thống tiền tệ.

**Việc làm:** nối host target selector với danh tính peer đã xác minh; xác nhận request + host revalidate consent/khoảng cách/quyền; đồng bộ trạng thái chỉ cho local ped; nút cảm ứng không xung đột nút game/Trainer; hai thiết bị chơi cùng phiên.

**Gate P3:** video/log đồng thời của **hai iPhone**: cùng session, A cảnh sát chọn B là người chơi thật, B opt-in, A còng B, cả hai thấy trạng thái đúng, tháo còng/phục hồi điều khiển, thử opt-out/disconnect/host migration. Chỉ chấm đạt trên thiết bị thật.

## P4 — Police RP đầy đủ: áp giải, giam giữ, phóng thích (BLOCKED bởi P3)

**Việc làm:** mở rộng state machine `FREE→CUFFED→ESCORTED→JAILED→FREE`, range/zone attestation từ host, jail timer giới hạn, reset khi nghỉ ca, animations và vehicle interactions theo native đã xác minh; chống double action/replay, kiểm thử đồng thời nhiều cảnh sát, host migration và jail expiry.

**Gate P4:** 2 thiết bị thực thi tuần tự và các nhánh lỗi; không giữ người chơi bị khóa vĩnh viễn; tùy chọn NPC hiện có không hỏng.

## P5 — HUD, touch, Việt hóa và trải nghiệm iOS (BLOCKED bởi P4)

**Việc làm:** menu RP ngoài game, chọn/đổi nghề, danh sách tên người chơi (display only), xác nhận opt-in, cảnh báo phạm vi/đồng ý, biểu tượng trạng thái còng/áp giải/timer giam giữ; hỗ trợ Safe Area, iPhone/iPad, overlay gamepad, tiếng Việt mặc định của riêng RP; không phá nút Menyoo/Ẩn HUD/Pause, không ép bật trong Online.

**Gate P5:** input/UI tests + video test màn hình iPhone/iPad; nút bấm không bị chắn, chuyển gamepad/touch đúng, no-crash trên chuyển game mode.

## P6 — EMS, Taxi và nghề nghiệp phụ (BLOCKED bởi P5)

**Thứ tự nội bộ:** EMS revive cho người chơi → taxi offer/accept/fare → role-specific permissions → sau đó mới bổ sung nghề nghiệp khác. Mỗi nghề cần protocol event riêng, host xác minh vị trí/trạng thái/consent, hiệu ứng local ped và chống lặp.

**Gate P6:** mỗi nghề có 2-device acceptance script, không thể revive/thu tiền nhiều lần qua replay hoặc đồng bộ trễ, không ảnh hưởng Police/NPC.

## P7 — Kinh tế, tài sản, inventory và persistence (BLOCKED bởi P6)

**Việc làm:** thiết kế authoritative ledger/backend, định danh người chơi bảo mật, durable transaction ID, idempotency/atomicity, inventory, quyền sở hữu xe/nhà, migrations, rollback/backup; không nhét vào gói game stock; bắt đầu bằng in-memory test rồi staging server riêng.

**Gate P7:** replay/dupe/đứt mạng không nhân bản tiền/vật phẩm, test transactional recovery và version migration, bằng chứng đo được.

## P8 — Ổn định, bảo mật, hiệu năng và tối ưu (BLOCKED bởi P7)

**Việc làm:** audit memory/ASan/UBSan, bounds/race/deadlock, drop/flood, lỗi đồng bộ 2→32 người, FPS/memory/thermal, crash logs; kiểm tra nhiều bản iOS/iPhone/iPad phù hợp yêu cầu thiết bị; regression Story/Online, trainer/menu, localization, saves; perf baseline trước/sau và rollback.

**Gate P8:** báo cáo test matrix gồm build fingerprint, device/iOS, log, mức tiêu thụ, cách tái hiện, không có lỗi chặn phát hành; không khẳng định hỗ trợ thiết bị chưa thử.

## P9 — Build, ký, kiểm thử và phát hành IPA (BLOCKED bởi P8 + phê duyệt)

**Việc làm:** chỉ đóng gói IPA v12 được phép sử dụng, so khớp SHA/UUID, sao lưu IPA gốc, build/link các dylib đúng ABI, kiểm tra Mach-O dependencies/entitlements, ký lại trên môi trường được cấp quyền, cài trên máy thử, smoke tests + 2-device RP, kiểm tra binary diff và rollback; tạo release notes và hướng dẫn.

**Gate P9:** mã nguồn + logs build/sign + fingerprint IPA output + installation/device crash logs + manual approval. Cổng `RP_RELEASE_READINESS.json` ở PR #8 phải được review; **không tự động xuất bản IPA, không đưa tài sản độc quyền hoặc chứng chỉ lên GitHub**.

## Vòng lặp chuẩn cho từng giai đoạn

1. **Phân tích:** đọc đúng commit/IPA/log + issue/PR, chọn 1 yêu cầu nhỏ thuộc giai đoạn đang hoạt động.
2. **Thiết kế:** xác định API/ABI/điểm tin cậy, failure modes và test có thể thực thi.
3. **Thực hiện:** sửa nhỏ trên feature branch, lưu bản gốc và tránh thay đổi phần ngoài phạm vi.
4. **Chứng minh:** unit/C host/sanitizer/CI, nếu cần thiết thì iPhone logs; kết quả nào chưa test ghi **unverified**.
5. **Review + bàn giao:** code diff, test artifact, SHA/UUID, các blocker, rollback, cập nhật `state.json`; chỉ nâng giai đoạn sau khi gate được duyệt.
6. **Dừng đúng chỗ:** nếu gate phụ thuộc dữ liệu engine/thiết bị chưa có, không giả lập evidence; có thể chuẩn bị tài liệu/test harness của **chính giai đoạn đó**, không tự nhảy sang gameplay/release.

## Quy tắc điều phối AI tự động

- Mỗi lần chạy: đọc `state.json`, tệp này, `PHASE_GATES.json`, PR/CI mới nhất; xem **giai đoạn sớm nhất chưa verified** là ưu tiên duy nhất.
- Các sửa đổi chỉ nằm trong feature branch/PR nháp; không tự merge, không tiêu thụ API tính phí, không upload IPA hoặc chứng chỉ.
- Không tạo PR trùng cho cùng việc; ưu tiên cập nhật PR #4/#9 hiện có khi không xung đột; PR #7/#8 cần review theo gate P0.
- Mọi yêu cầu báo hoàn thành phải có đầu vào/bản build/số test/citation commit chính xác, thiết bị thật thì có log thật.
- Các bài test giả lập và binary ARM64 source-only hỗ trợ tiến độ kỹ thuật, **không chuyển P1/P2/P3 sang verified**.

## Mốc ưu tiên đầu tiên

**Ngay bây giờ = P0:** kiểm tra/đối chiếu #7, #4, #9, #8; thống nhất nhánh integration, test, và phê duyệt merge. **Sau P0 = P1:** nghiên cứu engine hook & trusted Online carrier có bằng chứng. Không triển khai EMS/taxi/economy trước bản Police RP tối thiểu đạt hai thiết bị.
