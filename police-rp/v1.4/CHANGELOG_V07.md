# Police RP v0.7 — 12/11/2026
- Thêm bridge game-thread + authenticated P2P, không dùng Menyoo online.
- Host cập nhật peer snapshot và xóa peer khi rời phòng.
- Không nhận network packet thiếu bit `authenticated_delivery` từ transport.
- Chặn sender spoof / replay theo P2P, không nhận room/host không trùng.
- Người chơi chưa opt-in không bị khóa controls; khi đổi phòng opt-in reset.
- Dự kiến chỉ hiệu lực với GTA5 ARM64 v12 chính xác UUID/hash.
- Mô phỏng 2 máy, sanitizer test; CHƯA có game hook, engine transport hay IPA chạy thực tế.
