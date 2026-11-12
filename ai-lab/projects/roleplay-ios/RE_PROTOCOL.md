# Reverse Engineering IPA — Protocol & Limits

1. **Nguồn dữ liệu:** chỉ dùng IPA đã có quyền phân tích, lưu SHA-256, tên file, app version, Mach-O UUID và tool version. Không commit IPA hoặc private binaries.
2. **Phân tích tĩnh:** ZIP manifest, Info.plist, entitlements, code signature, ARM64 Mach-O load commands, LC_UUID, dylib imports/exports, Objective-C metadata, strings, cross-reference, call graph.
3. **Chứng cứ vs giả thuyết:** symbol đã xác minh; API bridge suy luận; ABI/chữ ký thử nghiệm; decompiled pseudocode không phải mã nguồn tác giả.
4. **Tái tạo có kiểm soát:** ưu tiên mã mới (C/C++/ObjC++/Swift) và các interface/test adapters; không ghi đè bản gốc.
5. **Kiểm tra compatibility:** engine version, vtable, calling conventions, thread boundaries, object lifetime, resource/camera/network hooks, input translation.
6. **Safety:** không giả lập kết quả test, không trích xuất chứng chỉ, private secrets hoặc phân phối nội dung độc quyền.
7. **Chuyển tiếp:** cập nhật `state.json` bằng hash/UUID/đường dẫn tương đối và links đến báo cáo kiểm thử hợp lệ; đưa bản vá lên nhánh tính năng, PR review trước merge.

**Không thể cam kết lấy lại toàn bộ mã nguồn gốc từ IPA.** Thực tế chỉ có thể xây dựng database symbols và tái tạo phần hành vi cần thiết bằng mã mới. Xây dựng server RP iOS tương tác với engine GTA V port không mặc nhiên tương thích FiveM.exe hay giao thức FiveM gốc.
