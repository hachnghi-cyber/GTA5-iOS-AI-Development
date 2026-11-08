# DFPV iOS v11.1 — làm lại từ video (bản nguồn thử nghiệm)

Đây là **mã nguồn mới hoàn toàn**, không sử dụng lại DLL vá R7–R10. Cần build trên GitHub Actions mới tạo được file `.dll` để cài thử. Chưa xác nhận tính tương thích thực tế bằng thiết bị iOS.

## Đúng hai góc trong xe

1. **Mặc định**: góc lái thứ nhất do GTA V tạo sẵn (camera nội thất).
2. **Tùy chỉnh**: camera thứ nhất góc rộng 120°, có thể nhìn vô lăng, tay lái, người và đồng hồ xe tùy loại xe.

Ấn **nút đổi camera** để chuyển qua lại chỉ hai góc trên. Nếu bản port không cho phép chặn nút này, trong chế độ mặc định script sẽ cố đưa camera quay lại góc trong xe mỗi khung hình. Phím **N** cũng chuyển hai góc. Khi xuống xe, camera tự nhả. Xe không phải ô tô/xe máy giữ nguyên game gốc.

**Dữ liệu lấy từ video**: xe máy FOV 120°, tiến 0,05m, hạ 0,09m, cúi −40,30° và camera neo vào xe. Ô tô lấy **vị trí góc lái mặc định của chính game** làm mốc; FOV 120°, tiến 0,04m, hạ 0,04m, cúi −14° là mốc thử nghiệm. Cả hai có thể chỉnh lại trực tiếp trong game. Giá trị từ video không đảm bảo phù hợp với mọi model xe/đồ mod.

## Vì sao khác cách Menyoo

Clip gốc chép `DynamicVehicleFirstPerson.asi` vào thư mục GTA V trên **Windows**, sau đó dùng **menu riêng `Dynamic Vehicle FPV`**, không phải menu Menyoo. Tệp `.asi` Windows x86 không chạy trực tiếp trên GTA V iOS ARM64. Bản này là script C# dùng **ScriptHookVDotNet2** của GTA V iOS v11.1, không sửa hoặc thay Menyoo. Nút Menyoo cũ giữ nguyên.

## Build trên GitHub từ iPhone

1. Tạo repository GitHub mới (hoặc nhánh riêng), upload **toàn bộ nội dung** gói nguồn này, gồm cả `.github/workflows/build-dfpv-ios.yml` và `refs/`.
2. Vào tab **Actions → Build clean DFPV video remake → Run workflow**.
3. Mở job **build**, kiểm tra bước compile thành công rồi tải **Artifact `DFPV_VIDEO_REBUILD_iOS_v11_1`**.
4. Mở artifact ZIP, lấy file `DFPV_VIDEO_REBUILD_iOS_v11.1.zip` được build bên trong. ZIP này có `scripts/DynamicVehicleFirstPersonIOS.dll` và `scripts/DFPV_Camera.ini`.

**Không được lấy thư mục nguồn `dfpv_video_rebuild` đưa vào game vì chưa có DLL mới.** Nếu GitHub báo lỗi build, gửi mình nguyên log bước `Compile` để sửa đúng lỗi rồi mới cài.

## Thay bản camera cũ (không mất save)

1. Trong phần quản lý script ScriptHook của launcher, **sao lưu** file `scripts/DynamicVehicleFirstPersonIOS.dll` cũ cùng các file cấu hình camera cũ của bạn; chỉ gỡ script camera DFPV cũ.
2. Cài duy nhất `scripts/DynamicVehicleFirstPersonIOS.dll` mới và `scripts/DFPV_Camera.ini` từ ZIP build. **Không xóa Menyoo, ScriptHook, IPA, dữ liệu game hay save.**
3. Vào Story Mode, ngồi xe, nhấn nút chuyển góc nhìn. Lần đầu chỉ có góc GTA mặc định, nhấn tiếp sẽ vào góc DFPV tùy chỉnh.

## Chỉnh trực tiếp trong game

- **F10** hoặc **LB + D-pad lên**: mở menu camera. Nhấn lại LB + lên để đóng và lưu.
- **D-pad lên/xuống**: chọn FOV, tiến/lùi, cao/thấp, góc cúi, NearClip.
- **D-pad trái/phải**: giảm/tăng giá trị.
- **A**: lưu vào `DFPV_Camera.ini` nếu launcher cho phép ghi.
- **B**: đóng menu. **F6**: tắt/bật toàn bộ script.
- Nếu game không cho lưu tệp, mở `scripts/DFPV_Camera.ini` trên máy tính và chỉnh lại thủ công; lần khởi động sau script đọc lại.

## Vẫn cần thử trên máy thật

- Thử **ô tô mui kín**, **xe thể thao mui thấp**, **xe máy thường**, **xe mô tô có kính chắn gió**, nhân vật mặc tóc/mũ mod.
- Test ra/vào xe, đổi camera, đổi nhân vật, mở/đóng Menyoo, thoát game rồi vào lại, phanh LT.
- Script cố tạm ẩn tóc/mũ theo component chuẩn của GTA rồi trả lại khi thoát. Với nhân vật mod thay nguyên model đầu hoặc kính xe mod lỗi, vẫn có thể xuất hiện vật thể chắn tầm nhìn; không thể khẳng định đã xử lý mọi loại xe khi chưa kiểm thử iOS.
- Chỉ hoạt động Story Mode; Online script tự nhả camera.
- Nếu bị crash, gỡ đúng DLL DFPV mới, giữ Menyoo và game gốc. Gửi `run.log`, `posthook.log`, crash log và ảnh để truy đúng nguyên nhân.
