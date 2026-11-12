# GTA V iOS — AI Development Lab (100 Roles)

Hệ thống đã tích hợp 100 vai trò kỹ thuật vào 10 nhóm. Đây là **cấu hình chuyên gia**, không phải 100 mô hình AI chạy song song.

## Tự động hóa đang hoạt động
- Mỗi push/PR thay đổi ai-lab: tự kiểm tra cú pháp Python, chạy unit test, chọn chuyên gia và xuất báo cáo JSON (GitHub Actions artifact).
- Lịch kiểm tra mỗi ngày: kích hoạt trên default branch sau khi merge Pull Request.
- Chạy theo nhiệm vụ: Actions > GTA AI Lab - Automated CI > Run workflow > nhập task. Nút Run workflow chỉ hiện sau khi workflow được merge vào default branch.
- AI review bằng Codex: workflow riêng, mặc định tắt. Cần biến repository Actions ENABLE_CODEX_REVIEW=true và secret OPENAI_API_KEY. Sử dụng API có thể phát sinh chi phí; không tự sửa code hoặc merge.
- Khi đã cài và xác thực Codex CLI ở máy tính, lệnh run có thể chạy tối đa ba vai trò **tuần tự**, quyền chỉ đọc.

## Lệnh công cụ
- python ai-lab/dispatcher.py plan --task "SIGSEGV crash after Menyoo vehicle spawn" --top 5
- python ai-lab/audit_ipa.py original.ipa --output ai-lab/reports/audit.json
- python ai-lab/compare_ipa.py original.ipa patched.ipa --output ai-lab/reports/diff.json
- python ai-lab/crash_triage.py crash.log --output ai-lab/reports/crash.json
- python -m unittest discover -s ai-lab/tests -v

## Quyền và giới hạn
- IPA audit: kiểm tra ZIP, Info.plist, phát hiện và đọc có giới hạn các Mach-O ARM64; chưa phân tích toàn bộ fat slices/code signing.
- Binary diff: so file theo CRC32 và size; không phải chứng minh tương đương mật mã.
- Crash triage: phân loại heuristic, không tự động symbolicate và không chứng minh nguyên nhân gốc.
- CI không biên dịch/ký IPA game thật; cần mã nguồn, Apple SDK, provisioning, thiết bị thử và workflow build phù hợp.
- Không tự thay đổi game binaries hoặc merge lên main. Chỉ phát hành khi đã test trên iPhone/iPad và có rollback.
- Không đưa API key, profile ký, IPA độc quyền hoặc nội dung riêng tư vào repository.

## Kích hoạt AI review (tùy chọn)
1. GitHub > Settings > Secrets and variables > Actions: tạo repository secret OPENAI_API_KEY.
2. Thêm repository variable ENABLE_CODEX_REVIEW, giá trị true.
3. Sau khi merge PR, vào Actions > GTA AI Lab - Optional Codex Review > Run workflow.
4. Đọc báo cáo trong Artifact, tự phê duyệt thay đổi bằng PR.
