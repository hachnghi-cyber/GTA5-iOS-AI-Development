# CONTINUE HERE — GTA V iOS Roleplay

**Tài liệu mở đầu bắt buộc trong MỖI cuộc trò chuyện GPT-6 mới.**

## Checkpoint v13.3 hiện tại

Một iPhone có tiến trình GTA cài riêng và LiveProcess cùng tồn tại.
Trong cửa sổ Sysmon 8 giây, GTA5 báo CPU 0 ở 16/16 mẫu, còn LiveProcess
báo CPU trên 0 ở 16/16 mẫu. Cần kiểm tra hai cửa sổ cùng hoạt động và
cùng phòng trước khi dùng cấu hình này để đo nhận sự kiện GTA.
Xem `baselines/v133-livecontainer-standalone-cpu-20261119.json`.

Điểm đo `leave_session_call` đã bổ sung đối chiếu ID phiên theo hai getter
đã kiểm tra mã trên đúng v13.3. Log chỉ ghi ID lúc đầu có giá trị hay không
và quan hệ ở mốc sau: giữ nguyên, bằng 0, đổi hoặc thiếu ID ban đầu.
182 bài kiểm thử host đã qua. Cần lấy mẫu thật trong phòng chỉ mời.

Điểm đo USB `leave_session_call` theo lời gọi `snSession::Leave`, giá trị
trả về và quyết định dọn phiên trong `Update` trên cùng lần attach. Nó
kiểm tra slot chính đang thiết lập ở đầu, rồi đối chiếu manager, slot và
tác vụ ở mốc sau. Profile xác minh trên binary v13.3 và 181 bài kiểm thử
host đã qua. Cần chạy điểm đo mới trên iPhone trong phòng chỉ mời.

Trên iPhone, một lượt rời phòng chỉ mời xác nhận `ClearSession` được gọi
từ `Update`. Lượt khác bắt đúng nhánh status 3 và đích nhảy bỏ qua
`DropSession`, trong cùng frame và thread. Cả hai slot đã mất trạng thái
thiết lập tại điểm quyết định. Mốc sớm hơn trên binary là
`LeaveSession → snSession::Leave`, nhận slot chính và con trỏ trạng thái
của tác vụ rời phiên. Cần đo mốc này để xác định phiên bị thu hồi.
178 bài kiểm thử host đã qua. Xem
`baselines/v133-private-leave-path-iphone-20261119.json`.

Binary v13.3 có hai đường gọi `ClearSession` trực tiếp. Trong `Update`,
`DropSession` gọi shutdown và init trên slot chính trước `ClearSession`.
Observer hai mốc `drop_session_call` hết thời gian trong lượt rời phòng chỉ
mời. Observer `clear_session` giờ đối chiếu LR với lệnh gọi đã kiểm tra mã
để phân biệt `Update` và `UpdateTransition`. Cần lấy nhãn này trên iPhone
để xác định nhánh rời phòng thực tế. 176 bài kiểm thử host đã qua.
Xem `baselines/v133-drop-session-boundary-iphone-20261119.json`.

Một iPhone đã xác nhận điểm vào `ClearSession` khi rời phòng GTA chỉ mời.
Trong phòng riêng, slot chính đã thiết lập dù bit tiến trình của slot chính
báo false. Sau hai lần rời phòng về Sandbox, cả hai slot đều chưa thiết lập.
Phép đo `SwapSessions` ở lượt đầu hết thời gian. Xem
`baselines/v133-private-session-leave-iphone-20261119.json`.
Lượt đo xác nhận điểm vào hàm, chưa xác định phiên cụ thể bị dọn, generation
hoặc luồng của callback nhận. Cần peer GTA thứ hai để đối chiếu đường nhận.

Bản iPhone có giao diện tùy chọn `RP riêng` cho một cặp danh tính của kit LAN.
`prepare_private_rp.py --panel` bật nút Tham gia/Rời RP, Chào hỏi và Yêu cầu
giấy tờ. Người chơi xác nhận tham gia bằng nút; giao diện chờ ACK cùng
snapshot trước khi bật tác vụ. Source CI và build iPhoneOS ARM64 của
`103c23b` đã đạt. Gói cục bộ `GTAV-v13.3-Private-RP-Panel-103c23b-UNSIGNED.ipa`
đã qua CRC, kiểm tra Mach-O và đối chiếu từng mục với IPA gốc.
Bản ký đã qua phép thử với Windows qua LAN. Một lượt xác nhận Chào hỏi
và Yêu cầu giấy tờ theo cả hai chiều. Lượt riêng xác nhận Tham gia/Rời RP
theo hai nonce kế tiếp. Xem `baselines/private-rp-iphone-panel-20261119.json`.
Cần peer GTA thứ hai để xác minh game binding và thử tác động lên nhân vật.

Server đóng các client TLS sau khi ngừng nhận kết nối mới và trước khi
đợi listener đóng hẳn. Kiểm thử hồi quy dùng một kết nối mTLS còn mở.
172 bài kiểm thử host đã qua. Bản iPhone `103c23b` dùng được với server này.

Server kiểm tra lại kết nối sau mỗi lần chờ đọc TLS. Kiểm thử hồi quy dùng
hai kết nối mTLS liên tiếp của cùng một tài khoản, xác nhận kết nối cũ
không đổi consent hoặc nonce của lần vào mới. 170 test host đã qua.
Thay đổi nằm ở server.

Phép đo `session_swap` qua USB sau khi người thử báo đã vào Sandbox hết
cửa sổ 55 giây. Chưa có mẫu hoán đổi slot hoặc bằng chứng về thế hệ phiên.
Cần phiên GTA riêng với peer thứ hai để đối chiếu đường nhận và lúc rời phiên.

Server ABI 3 tách lần vào TLS khỏi lần vào phiên GTA. Khi nguồn game báo
rời phiên hoặc đổi generation, server giải phóng custody, hủy consent và
giữ nonce trên kênh TLS hiện tại. 169 test host và C FFI đã qua. Kiểm thử
vòng đời dùng dữ liệu GTA mô hình. Cần peer GTA thứ hai để xác minh nguồn.

Server và probe có kênh PRP3 tùy chọn cho Chào hỏi và yêu cầu kiểm tra giấy
tờ. Gửi chỉ khi hai bên đã opt-in và xác nhận bằng kết nối người nhận.
Build ARM64 `0c38348` đã đạt. IPA chẩn đoán chưa ký
`GTAV-v13.3-Private-RP-Social-Probe-0c38348-UNSIGNED.ipa` đã kiểm tra ZIP và
Mach-O. Bản ký đã chạy trên iPhone và qua hai chiều với Windows. Xem
`baselines/private-rp-iphone-social-20261119.json`. Cần peer GTA thứ hai
để đo đường nhận native và ghép danh tính với nhân vật.

Server đã kiểm tra hai lần gia nhập hiện tại trước khi đưa dữ liệu cặp vào
luật còng/áp giải. 163 test host đạt, gồm từ chối tráo người và dùng mẫu
cũ sau reconnect; dữ liệu game trong test là mô hình. Adapter game thật
cần nối mỗi danh tính RP với đúng nhân vật trong phiên GTA riêng.

Server host ABI 2 xác minh nguồn ca độc lập theo lần kết nối và tự thu hồi
quyền/giải phóng custody khi bỏ ca, dữ liệu quá cũ hoặc nguồn lỗi. 161 test
Python và C FFI đạt; kiểm thử ca server dùng dữ liệu mô hình. Build lại DLL
trước khi chạy server. Chưa nối nguồn game thật, giao thức iPhone giữ nguyên.

Đã đo ca cảnh sát thật trong Sandbox. `MacportWorkStatus` dùng chỉ số job
và cờ ca riêng với metadata network job. Probe mới đọc `cop_ls` và
`on_shift=true` cùng lúc trường network job báo rỗng. Sau bỏ ca, phép đo
trả `job=none`, `on_shift=false`. Xem
`baselines/v133-local-work-duty-iphone-20261119.json`; chưa cấp quyền online.

Một iPhone thật và Windows đã qua kiểm thử server riêng. Log USB của iPhone
ghi `consent_round_trip_passed`; PC thấy đủ kết nối, tham gia, rời RP và ngắt
kết nối. Xem `baselines/private-rp-iphone-consent-20261119.json`. Mốc tiếp
theo là xác minh game thread trong Sandbox riêng và ghép đúng người chơi.

Trên cùng bản cài, hai mẫu trong Sandbox dừng đúng ở `jobs_update` và caller
đã xác minh. Hai bit tiến trình đều bật, chưa có slot phiên đã thiết lập;
metadata job ở trạng thái chưa nhận ca. Profile queue v3 tới được điểm đo
enqueue và hết 7 giây mà không bắt frame. Xem
`baselines/private-rp-authority-build-sandbox-20261119.json`. Cần mốc nhận/bỏ
ca thật và một peer GTA thứ hai để đối chiếu nguồn sender.

Chế độ chẩn đoán `--consent-probe` kiểm tra thêm đường iPhone gửi lệnh. Nó
yêu cầu ACK và snapshot cùng nonce khi tham gia và rời RP. Xem hướng dẫn LAN
trong `PRIVATE_RP_SERVER_VI.md`. Build `2455bc3` đã đạt CI và tạo IPA chưa ký
`GTAV-v13.3-Private-RP-Consent-Probe-2455bc3-UNSIGNED.ipa`.

Đã nối mã client iOS với giao thức server riêng và thêm cấu hình mTLS cho
iPhone. Hai client dùng cùng codec C đã qua kiểm thử với server qua TLS thật
trên Windows. Tổng 154 test Python đạt. Build iPhoneOS ARM64 và source CI
của `99ed120` đã đạt. IPA chẩn đoán chưa ký đã tạo và đối chiếu từng mục ZIP.
Hướng dẫn cài và kiểm thử nằm trong `PRIVATE_RP_SERVER_VI.md`. Chưa có xác
nhận hành động trong game.

Server riêng đã có mã chạy được trên Windows/Linux: xem `PRIVATE_RP_SERVER_VI.md`.
152 test Python đạt, gồm 15 test server mTLS thật với hai client host và lõi C.
Game observations trong test là mô phỏng; cấu hình mặc định chưa cấp duty/custody.
Đã sửa client xóa snapshot cũ khi disconnect/hủy transaction. Hai tiến trình
client cũng đã chạy qua CLI mặc định, đồng bộ opt-in và thu hồi khi rời phiên.

Yêu cầu mới ngày 2026-11-18: dùng **server RP riêng cho v13.3**. Hướng này
thay thế ưu tiên không vận hành server riêng trước đây. Tiếp tục từ mTLS và
lõi Police RP đã có; kiểm thử hai client host trước khi nối nhân vật/game thread.

Checkpoint miền định danh (parent `8749804`): thêm 15 opcode trên binary gốc,
143 kiểm tra connection-chain và 137 test Python đạt. Transport `netPeerId`
ở đầu `netPeerAddress` khác `rlPeerInfo` ID ở +0x1d0. Observer scripted yêu cầu
cả hai phép đối chiếu đúng miền, cùng ba code guard bổ sung. Chưa xác thực
game player, chưa có mẫu thiết bị mới. CI parent: 44128501576/44128501608/44128501617 đạt.

Checkpoint toàn vẹn packet (parent `66961ca`): profile v3 thêm bốn code guard
cho key lookup/HMAC/decrypt. Audit xác minh 47 opcode, 9 call target và nhánh
HMAC bắt buộc trước AES/điểm trả thành công. 133 test Python đạt. Đây là
phân loại đường packet, chưa xác thực game player. Tiếp tục truy vết metadata
key-exchange/peer bằng binary trên host; phép thử USB là một gate riêng.

Checkpoint endpoint/channel (parent `35bbb15`): probe received-frame đối chiếu
connection với bảng channel của endpoint trong cùng lần dừng. Thêm 17 opcode
đã kiểm tra trên binary gốc; 126 test Python đạt. Chưa có mẫu iPhone cho phép
đối chiếu mới. Xem `ROLEPLAY_CONTINUE.md`; chưa bật adapter hay quyền RP.

Ưu tiên checkpoint sửa producer Phase 19 trong `ROLEPLAY_CONTINUE.md`:
điểm enqueue cũ tạo connection-error event. Profile v2 dùng hai producer
received-frame đã đối chiếu vtable trên binary, có 124 test Python đạt;
chưa có preflight hay mẫu iPhone cho profile mới.

Mốc mới: sửa lỗi giữ dữ liệu phiên cũ khi `rp_rage_scope_begin` thất bại;
kiểm thử đối chứng C11 và 121 test Python đạt. Xem `ROLEPLAY_CONTINUE.md` và
`state.json:last_work.scope_renewal_fail_closed`. Hiện chưa có USB để lấy mẫu
callback thật; người dùng xác nhận chưa thể kết nối lại.

Checkpoint tiếp nối yêu cầu **Operation RAGE Breakthrough** nằm ở
`ROLEPLAY_CONTINUE.md`; sơ đồ receive/local ở `ENGINE_INTEGRATION_MAP.md`.
Ưu tiên cũ về native multiplayer đã được thay bằng yêu cầu server riêng ở trên.
Mốc 2026-11-17: đã thu hai mẫu timeout 30s (`script_event_handler`,
`on_net_event`) và mẫu `jobs_update` trúng đúng caller sau khi mount DDI.
Xem `baselines/v133-usb-receive-attempts-20261117.json`; chưa có receive hit.
Mẫu `--session-context` trên iPhone cùng ngày ghi phiên chính `false`,
phiên chuyển tiếp `true` tại `jobs_update`. Xem
`baselines/v133-usb-session-context-20261117.json`.
PR #19 đã qua build iPhoneOS ARM64 và ghi nhận thử nghiệm E3 PC → iPhone
với ACK và phản hồi gọi native. Xem checkpoint `844ea9c` của PR #19.
Observer USB có `--receive-context` để kiểm tra call chain và liên hệ sender;
tiếp tục cùng hai điểm đo Phase 17 trong phiên có peer thử nghiệm.
Windows có thêm `--queue-context`, dùng bộ tương quan từ gói Phase 19 để theo
một event qua enqueue, dispatcher và điểm chọn sender trong `OnNetEvent`.
Lệnh và tiêu chí đọc kết quả nằm trong `V133_SCRIPTED_EVENT_OBSERVER_VI.md`.
iPhone đã qua bước kiểm tra 8 vùng mã và đặt/gỡ hai hardware breakpoint.
Mẫu hàng đợi thật còn chờ phòng Sandbox thử riêng.

Tiếp tục trên PR #16, nhánh `feature/winstom-rp-ipa-audit-20261116`.
Đọc `state.json` và `WINSTOM_V133_PHASE9_SENDER_CARRIER.md` để dùng lại bằng chứng
GTA v13.3 và Winstom 0.7.177. Bản IPA chẩn đoán cục bộ đã qua kiểm tra ZIP và Mach-O.
Probe đã chạy trên iPhone, vào Sandbox và ghi được hai đường gọi thực tế. Đọc
`V133_PHASE9_DEVICE_STARTUP.md` để nối tiếp đúng mốc. Cần xác minh ABI và metadata
của scripted event trước khi nối adapter RAGE. Runbook lấy mẫu bằng hardware
breakpoint nằm ở `V133_SCRIPTED_EVENT_OBSERVER_VI.md`. Không cần đổi IPA Phase 9
nếu chữ ký hiện tại cho phép debugger attach. Host Windows đã bắt được
`jobs_update` qua USB trên đúng bản đã ký. Xem mục Windows trong runbook để
tiếp tục từ điểm này. Còn chờ scripted receive trong phiên Sandbox có peer.

## Hướng transport RP độc lập

`PRP3_DIRECT_TLS_VI.md` ghi bản tham chiếu TLS hai chiều chạy được trên host.
Probe ARM64 đã build, người dùng đã ký/cài, và iPhone ↔ Windows đã trao
đổi GREET/DOCUMENTS qua TLS thật. Đọc log đã lọc trong baseline Phase 10. Giữ nguyên gate
v13.3 và không dùng ID TLS như slot hay danh tính engine nếu chưa đối chiếu.

## Luật Police RP

`V133_POLICE_AUTHORITY_VI.md` ghi mô-đun quyết định nhận ca, còng, áp giải,
ghế xe và án tạm thời. Biên ánh xạ 1:1 đã có ở mức source. Cần nguồn
snapshot game thật và bằng chứng ghép đúng người chơi trước khi nối
engine vào kênh TLS.

## Nguồn sự thật
- Repository: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development
- Integration branch: `feature/gta-ai-lab-100-agents` cho đến khi PR #1 được merge.
- Đọc lần lượt: root `AGENTS.md`, `ai-lab/projects/roleplay-ios/state.json`, `ai-lab/projects/roleplay-ios/ROADMAP.md`, `ai-lab/README.md`, `ai-lab/projects/roleplay-ios/RE_PROTOCOL.md`.
- Đọc các PR/Issue mới nhất, workflow Actions, log test liên quan; đối chiếu nhánh hiện tại. Không tin dữ liệu cũ hơn GitHub.
- `state.json` chứa việc đã kiểm chứng, việc chưa thử, blocker và `next_action`.

## Cách phát triển liên tục
1. Đọc commit/PR trạng thái mới nhất và kiểm tra quyền công cụ GitHub.
2. Chọn duy nhất một nhiệm vụ khả thi từ `backlog`, ưu tiên đang dở rồi tới task chưa bị chặn. Không đoán nội dung IPA chưa có.
3. Phân tích/thiết kế, viết mã nguồn độc lập hoặc bản vá nhỏ, bổ sung test và tài liệu.
4. Chạy được kiểm thử nào thì ghi log thật; đánh dấu rõ những thử nghiệm không chạy được.
5. Lưu code/test/report vào nhánh chức năng; tạo/update PR, không tự merge.
6. Cập nhật `state.json` trong cùng PR: kiểm chứng mới, dấu vết commit, hash bản gốc, công việc tiếp theo và blocker.
7. Kết thúc bằng **Handoff**: nhánh/commit, thay đổi, kiểm thử đạt/thất bại, vấn đề chưa giải quyết, một bước tiếp theo.

## Prompt dán trong cuộc trò chuyện GPT-6 mới

> @GitHub Hãy tiếp tục phát triển dự án GTA V iOS FiveM-style Roleplay tại repository hachnghi-cyber/GTA5-iOS-AI-Development. Đọc nhánh feature/gta-ai-lab-100-agents (hoặc main nếu đã merge), root AGENTS.md, ai-lab/projects/roleplay-ios/CONTINUE_HERE.md, state.json và các PR/Issue mới nhất. Xác định nhiệm vụ tiếp theo chưa bị chặn, thực hiện phân tích/viết code/kiểm thử trong phạm vi công cụ cho phép, tạo PR và cập nhật state.json. Không tự merge, không tuyên bố đã test trên iPhone khi chưa có chứng cứ. Báo cáo commit, log test, blocker và bước kế tiếp.

## Giới hạn
- Chat thông thường không tự chạy vô hạn khi đóng ứng dụng. GitHub Actions và dịch vụ agent được cấu hình riêng mới hoạt động theo lịch/sự kiện.
- Một IPA phân phối chứa mã máy đã biên dịch, không bảo đảm tái tạo mã nguồn gốc. Dùng thông tin phân tích để xây dựng **mã nguồn mới** có thể bảo trì.
- FiveM client theo tài liệu Cfx là Windows. iOS RP dạng *FiveM-style* không đồng nghĩa tương thích chính thức với FiveM server.
- Không commit IPA/game assets có bản quyền, dSYM riêng, khóa ký, tài khoản hay API key.
