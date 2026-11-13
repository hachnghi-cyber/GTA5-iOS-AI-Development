# CONTINUE HERE — GTA V iOS Roleplay

**Tài liệu mở đầu bắt buộc trong MỖI cuộc trò chuyện GPT-6 mới.**

## Nguồn sự thật
- Repository: https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development
- Integration branch: `feature/gta-ai-lab-100-agents` cho đến khi PR #1 được merge.
- Đọc lần lượt: root `AGENTS.md`, `ai-lab/projects/roleplay-ios/state.json`, `ai-lab/projects/roleplay-ios/ROADMAP.md`, `ai-lab/README.md`, `ai-lab/projects/roleplay-ios/RE_PROTOCOL.md`.
- Đọc các PR/Issue mới nhất, workflow Actions, log test liên quan; đối chiếu nhánh hiện tại. Không tin dữ liệu cũ hơn GitHub.
- `state.json` chứa việc đã kiểm chứng, việc chưa thử, blocker và `next_action`.

## Ưu tiên theo kế hoạch tuần tự P0–P9

Trước khi chọn task, **bắt buộc** đọc `SEQUENTIAL_EXECUTION_PLAN.md`,
`PHASE_GATES.json` cùng với `state.json`. Chạy
`python ai-lab/sequential_gate.py` để xác định **giai đoạn đầu tiên
chưa verified**. Không tự chọn một nhiệm vụ ở giai đoạn sau để
"tiến nhanh"; chỉ thực hiện bước thuộc giai đoạn hiện hành hoặc các
điều kiện nghiệm thu của nó.

Trạng thái hiện tại là **P0: chuẩn hóa repo/baseline/PR #7→#4→#9→#8**,
chưa hoàn thành khi các PR vẫn là draft. `P1` cần log hook/game-frame
và trusted identity ở GTA v12; `P9` tuyệt đối không được ký/phát hành
IPA nếu thiếu kiểm thử thiết bị và duyệt thủ công. CI host/ARM64
source-only không phải bằng chứng chạy Online.

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
