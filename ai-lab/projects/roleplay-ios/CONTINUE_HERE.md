# CONTINUE HERE — GTA V iOS Roleplay

**Tài liệu mở đầu bắt buộc trong MỖI cuộc trò chuyện GPT-6 mới.**

## Checkpoint v13.3 hiện tại

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
Ưu tiên native multiplayer, không yêu cầu người dùng vận hành server RP riêng.
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
