# GTA V iOS v13.3 — test nhanh Phase 8 (read-only startup probe)

**Cập nhật Phase 9, 16/11/2026:** hỗ trợ thêm IPA xuất từ 3u SHA-256
`7ae987a7770610ae42024095861096f8eca45ec39db1a89c223e9d6f2c0c26d7`.
Executable vẫn phải khớp SHA/UUID v13.3. Artifact mới chứa thêm mã carrier/mailbox
ARM64 chưa nối engine; log vẫn dùng tên Phase8 để tương thích và ghi
`source_revision=phase9-carrier-unbound`. Đây vẫn chỉ là phép thử startup.
Xem `../../WINSTOM_V133_PHASE9_SENDER_CARRIER.md` ở thư mục dự án để đọc bằng chứng mới.

**Lưu ý quan trọng:** Đây là bản thử **khởi động và nạp dylib**, KHÔNG phải Police Roleplay hoàn chỉnh. Không có còng, áp giải hoặc gửi sự kiện Online. Mục tiêu thực tế đầu tiên là xác nhận native probe của chính v13.3 chạy được trong iPhone mà không ảnh hưởng chế độ chơi gốc.

## Build và lấy dylib

1. Mở GitHub repository `hachnghi-cyber/GTA5-iOS-AI-Development` → Actions → `GTA v13.3 - iPhone Launch Probe (NO GAME IPA)`.
2. Chọn workflow run thành công, tải artifact `GTA-v13.3-Phase8-iPhone-STARTUP-PROBE-NO-IPA`.
3. Giải nén, cần `PoliceRPV133Probe.dylib`, `patch_exact_v133_probe.py`, `README_TEST_VI.md`, `sha256.txt`.
4. Artifact không chứa GTA5, IPA hoặc asset có bản quyền; game của người dùng vẫn nằm cục bộ.

## Tạo IPA nhanh bằng kéo-thả (Windows)

1. Tải artifact **GTA-v13.3-Phase8-iPhone-STARTUP-PROBE-NO-IPA** từ GitHub Actions; giải nén toàn bộ.
2. Trên máy tính Windows cài **Python 3** (cần lệnh `py -3` hoặc `python`). **Kéo file `GTAV-v13.3.ipa` gốc thả vào `Make_Phase8_IPA_Windows.bat`** nằm trong thư mục artifact.
3. File `GTAV-v13.3-Phase8-Probe-UNSIGNED.ipa` sẽ được tạo **bên cạnh IPA gốc**, nếu và chỉ nếu hash và Mach-O đúng. Không xóa hoặc ghi đè file gốc.
4. Dùng công cụ ký IPA riêng của bạn để **ký lại cả app + embedded dylib cùng một Apple Team ID**, sau đó mới cài lên iPhone. Chữ ký cũ hết hiệu lực khi sửa executable. <https://support.apple.com/guide/security-pdf/app-code-signing-process-sec7c917bf14/web>

Trên **macOS hoặc Linux**, dùng `sh Make_Phase8_IPA_macOS_Linux.sh /duong/dan/GTAV-v13.3.ipa` (cần Python 3). Tất cả thao tác đóng gói IPA thực hiện **trên máy tính của bạn**, không tải IPA/game assets lên GitHub.

Đây là **IPA thử startup read-only**; không có còng tay hay RP Online. Không coi file unsigned là đã cài được.

## Tạo IPA thử, giữ bản gốc

Dùng **đúng** `GTAV-v13.3.ipa` gốc của người dùng, SHA-256 IPA:
`7a5e23358e4a72a03322fe016ea08adde1ee6189b0c66f86e656a48649057b89`.
Giải nén artifact vào cùng thư mục với IPA, cài Python 3 rồi chạy:

```bash
python3 patch_exact_v133_probe.py --ipa GTAV-v13.3.ipa --bridge PoliceRPV133Probe.dylib --out GTAV-v13.3-Phase8-Probe-UNSIGNED.ipa --enable-file-sharing
```

Nếu script dừng vì hash/ZIP/thiếu header slack: **không tiếp tục và không ép vá offset**. Script chỉ thêm một lệnh tải dylib trong load commands của GTA5, chèn dylib vào Frameworks, giữ nguyên toàn bộ tài nguyên game khác. Thay đổi load command làm chữ ký cũ không hợp lệ.

Ký lại **toàn bộ app và embedded dylib** bằng chứng chỉ/provisioning của chính bạn (ví dụ bằng công cụ ký IPA phù hợp), rồi cài vào máy thử. Backup save trước khi thay app. Trường hợp máy báo integrity/signing failure không phải crash gameplay, hãy kiểm tra ký mã trước.

## Thử trên một iPhone

1. Đầu tiên khởi động, kiểm tra màn hình launcher và Story Mode có vào được không. Chưa cần hai điện thoại.
2. Khi dùng --enable-file-sharing, mở Files → Trên iPhone của tôi → GTA V → PoliceRP-v13.3-Phase8.txt (tên thư mục phụ thuộc app sau ký). Nếu không thấy, tìm log console `[PRP_V133_PHASE8]` hoặc trong sandbox app Documents: `PoliceRP-v13.3-Phase8.txt`.
3. Log hợp lệ phải có `gta5_uuid_matches=1`, `engine_game_thread_verified=0`, `authenticated_network_sender_verified=0`, `rp_network_enabled=0`.
4. Chỉ khi khởi động ổn định mới thử Online với **1 người** và sau đó phòng riêng **2 người** nhằm xác nhận game gốc không bị hỏng. Chưa có hành động RP mới để bấm.
5. Nếu văng, gửi crash report, run.log/posthook.log, iOS version và có/không thấy log `[PRP_V133_PHASE8]`. Không thử offset hoặc dylib khác.

## Giới hạn/không được hiểu nhầm

- Build ra dylib iPhone arm64 trên macOS runner không đồng nghĩa IPA đã được ký và chạy trên máy thật.
- `gta5_uuid_matches=1` chỉ chứng minh đúng executable, **không** chứng minh callback game-thread/transport.
- Không đo FPS, không tác động AI/NPC hoặc người chơi khác, không bật Menyoo/ScriptHook Online.
- Đây là bước an toàn để chẩn đoán boot/load. Mục tiêu Police RP Online vẫn cần sự kiện `PRP3 greet` thật từ A→B với metadata sender/session do engine xác thực.

**Rollback:** gỡ bản thử và cài lại IPA v13.3 gốc đã ký; khôi phục backup nếu cần. Tệp gốc và asset không bị script sửa tại chỗ.
