# Police RP Only v0.6 — Engine integration

Xem tài liệu mới: **`../P2P/ENGINE_BINDINGS_REQUIRED.md`**.

Từ v0.6, Police RP không sử dụng server HTTP/TCP 7789. Cần kết nối:
1. Engine game-frame callback riêng, hoạt động khi v12 đang ở Online nhưng không khởi động ScriptHook/Menyoo.
2. Giao diện gửi/nhận payload 56 byte qua kênh GTA Online vốn đã xác thực người gửi và mã hóa.

`NativeBridge/police_rp_only.c` và `police_rp_adapter.c` vẫn quản lý riêng local ped và tự tháo còng nếu mất trạng thái. Chưa có điểm hook đã kiểm chứng hoặc bản IPA có thể cài. Không thử patch GTA5 tại địa chỉ chưa được xác minh.
