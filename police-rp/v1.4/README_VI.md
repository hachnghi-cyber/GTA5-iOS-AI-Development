# GTA V iOS v12 — Police RP Only v1.4 (Diagnostic Bridge)

**Trạng thái: SOURCE + PROBE, CHƯA PHẢI IPA CHƠI ĐƯỢC.**

Định hướng giữ nguyên: GTA V iOS v12 **thường**, chỉ nghề cảnh sát và người chơi tự nguyện Police RP, không dùng Menyoo Online, không cần server Police RP phụ trợ, không ảnh hưởng nhiệm vụ bắt NPC.

V1.4 tập trung kiểm tra **dylib có nạp thật vào GTA5 v12 trên thiết bị iOS không**. Nếu dylib nạp, nó ghi marker `PoliceRPProbe-v14.txt` vào Documents (nếu được phép) và stderr. Không hook engine, không gửi gói Online, không còng tay.

**Xem `HUONG_DAN_V14.md` để làm theo từng bước.**

Đã kiểm thử offline: xác minh Mach-O/UUID, đóng gói thử, kiểm tra quyền tệp, parser kết quả; hồi quy mã nguồn nền. Workflow `.github/workflows/build-prp-v14-probe-ios.yml` được tạo nhưng chưa chạy trên macOS.

Điểm nghẽn để thực hiện gameplay vẫn là native callback game-thread và kênh mạng RAGE xác thực. Chưa có IPA Police RP Only hoàn chỉnh và chưa thử trên hai iPhone.
