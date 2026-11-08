# Phân tích DynamicVehicleFirstPerson 1.3.2 với GTA V iOS v11.1

Ngày: 08/11/2026. Phạm vi: phân tích tĩnh trên hai tệp người dùng cung cấp.

## Tệp gốc và SHA-256

- `GTAV-v11.1(2).ipa`: `a3f7b847c332c0f54c596d817013a64394bb826cced9b229d3e5fe3c51905992`
- `c5ec6b-DynamicVehicleFirstPerson-1.3.2-Release.zip`: `6fea26906d53c11d346961f954822de8abd4a224e1b2734808cc6fd1085af83e`

## Sự khác biệt nền tảng

- `DynamicVehicleFirstPerson.asi` là PE32+ x86-64/Windows; phụ thuộc `KERNEL32.dll`, `USER32.dll`, `SHELL32.dll`, `ole32.dll`, `ScriptHookV.dll`.
- IPA chứa `GTA5` Mach-O ARM64, `ScriptHookV.dylib`, `libgtacompat.dylib`, `Menyoo.shv.dylib` và Mono runtime. Không có loader có thể thực thi trực tiếp mod PE32+ x86-64.
- Trong mã chuỗi của `libgtacompat.dylib`, launcher tuyên bố rõ plugin `.asi` Windows không chạy và gợi ý cài `.NET` mod thông qua ScriptHook Pack.
- Trong `ScriptHookV.dylib` có đường nạp `*.shv.dylib`, nhịp ScriptHook và bridge ScriptHookV .NET. Runtime .NET yêu cầu bộ ScriptHook Pack bên ngoài IPA.
- Mod gốc đặt trong README điều khoản **không sửa và không phân phối lại gói gốc**. Dự án thử nghiệm bên cạnh là code tự viết từ đầu, không dùng lại binary ASI hay mã nguồn độc quyền của tác giả.

## Bản thử nghiệm độc lập

`DynamicVehicleFirstPersonIOS.2.cs` sử dụng `GTA.World.CreateCamera` và `GTA.Native.Function.Call` của SHVDN v2. Bản R2 đã bổ sung: camera cabin, FOV chỉnh 50–130°, quán tính theo trục xe, rung nhẹ theo tốc độ, ba chế độ nhìn quanh, menu phụ đề điều khiển bằng gamepad, cấu hình theo model/biển số với tối đa 10 camera mỗi cấu hình, lưu cấu hình nếu thư mục có quyền ghi, DOF tùy chọn, nhường camera cho game lúc ngắm bắn/cutscene, và cơ chế dừng khi lỗi. Có chặn Online ở phiên bản hiện tại.

Nguồn tham khảo API:

- https://github.com/scripthookvdotnet/scripthookvdotnet/blob/main/source/scripting_v2/GTA/Camera.cs
- https://github.com/scripthookvdotnet/scripthookvdotnet/blob/main/source/scripting_v2/GTA/World.cs
- https://www.gta5-mods.com/scripts/dynamic-vehicle-first-person

## Những gì đã xác minh

1. `unzip -t` cho IPA thành công (thông qua `zipfile.testzip()`).
2. IPA gốc không bị sửa, gói thử nghiệm không chứa `.asi` của tác giả.
3. Các native hash được gọi trực tiếp trong C# đều hiện diện trong `ScriptHookV.dylib` của chính IPA này (kiểm tra chuỗi tên symbol bằng `tests/test_contract.py`).
4. Đã phát hiện `IS_SCRIPTED_CAM_RENDERING` không hiện trong binary, đã thay bằng `GET_RENDERING_CAM` có sẵn.
5. Cấu trúc dấu ngoặc trong mã nguồn đã cân bằng, các tên API camera .NET được dùng có trong assembly tham chiếu ScriptHook Pack đã đối chiếu.
6. **5/5** bài kiểm tra tĩnh đạt. Phép thử này không thay thế việc biên dịch hoặc chạy thử trên máy thật.

## Chưa thể xác nhận

- Không có .NET SDK được cài trong container phân tích nên **chưa biên dịch DLL tại đây**; có workflow GitHub Actions để thực hiện bước này.
- Chưa nạp script bằng bộ ScriptHook Pack thật trên v11.1, và chưa có phép thử thực tế trên iPhone.
- Chưa kiểm chứng camera với Menyoo, lúc nhiệm vụ cắt cảnh, với tất cả loại phương tiện, hoặc FPS/thời lượng chơi dài.
- Menu mới dùng phụ đề và nút điều khiển gamepad; không phải menu PC gốc và chưa xác minh ánh xạ cảm ứng iPhone.
- Chưa chứng minh hàm lưu cấu hình qua lớp ánh xạ file của port hoạt động trên thiết bị thật.
- DOF đã có cơ chế điều chỉnh tùy chọn nhưng chưa thử về hình ảnh/FPS; chế độ ngắm bắn tạm trả camera gốc, chưa có xử lý aim chuyên sâu như bản Windows.
- Chưa tái hiện được native hide-head chuẩn, tránh xuyên hình trên mọi loại xe, hiệu ứng terrain shake của mod gốc, tương tác Manual Transmission và các memory patch phụ thuộc phiên bản game.

Trạng thái: **mã nguồn bản thử nghiệm; chưa phải mod hoàn toàn tương thích, chưa có IPA/ DLL được kiểm nghiệm**. Ưu tiên thử DLL riêng, không chèn IPA, để tránh gây văng cho người đang chơi v11.1.
