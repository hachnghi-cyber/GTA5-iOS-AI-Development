# CONTINUE HERE — GTA V iOS Roleplay

**Tài liệu mở đầu bắt buộc trong MỖI cuộc trò chuyện GPT-6 mới.**

## Checkpoint v13.3 hiện tại

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
ghế xe và án tạm thời. Mô-đun chưa nối engine hoặc kênh TLS chẩn đoán.

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
