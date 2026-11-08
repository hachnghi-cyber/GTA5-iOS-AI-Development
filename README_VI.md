# Dynamic Vehicle First Person Camera — iOS v11.1 (bản chuyển đổi độc lập R2)

Đây là **bản lập trình lại độc lập** dùng API ScriptHookVDotNet 2, không sửa
hoặc chứa tệp `.asi` Windows của tác giả ikt. Đây **không** phải bản port
hoàn chỉnh của DynamicVehicleFirstPerson 1.3.2. Các hiệu ứng đặc thù phụ thuộc
memory patch của mod gốc chưa được tái tạo.

**Trạng thái:** Mã nguồn đã được kiểm tra tĩnh với IPA bạn cung cấp. Không có
.NET SDK trong môi trường này để tạo DLL; chưa kiểm thử được trên iPhone. Không
gọi là "tương thích hoàn toàn" cho đến khi có kết quả build và test thực tế.

## Yêu cầu

- GTA V iOS v11.1 với **GTAV-ScriptHook-Pack** mới và ScriptHookV .NET hoạt động.
- Thiết bị được hỗ trợ chạy .NET mod theo cấu hình của port; thường khuyến nghị 6 GB RAM trở lên.
- Chỉ dùng Story Mode để thử nghiệm; chưa được chứng minh an toàn trong Online.

## Cách xây dựng gói DLL

1. Giải nén ZIP mã nguồn rồi tải các file ở **bên trong thư mục** lên repo GitHub của bạn, giữ nguyên cấu trúc `refs/` và `.github/workflows/`.
2. Mở **Actions** → **Build Dynamic Vehicle FPV for GTA V iOS v11.1** → **Run workflow**.
3. Tải artifact `DFPV_iOS_v11_1_R2_TEST` và giải nén để lấy `DFPV_iOS_v11.1_R2_TEST.zip`.
4. Trong launcher GTA V v11.1, cần cài `GTAV-ScriptHook-Pack.zip` trước. Vào ScriptHook → **IMPORT SCRIPT**, chọn `DFPV_iOS_v11.1_R2_TEST.zip` hoặc chọn DLL trong `scripts/` nếu bản launcher không nhận ZIP. Đặt `DFPV_iOS.ini` cùng thư mục DLL nếu muốn lưu profile.
5. Bật ScriptHook trong Trainer → Add-ons nếu đang tắt; khởi động lại trò chơi, vào **Story Mode** và đổi sang góc nhìn thứ nhất khi ngồi trong xe.

## Điều khiển

| Điều khiển | Tác dụng |
|---|---|
| Chuyển sang góc nhìn thứ nhất trong xe | Camera tự bật khi ScriptHook đang bật |
| LB + D-pad phải | Bật/tắt camera độc lập |
| LB + D-pad lên | Chuyển camera tiếp theo; mặc định cân bằng, rộng 115°, thể thao |
| LB + D-pad trái | Ép camera hoạt động trong xe ngay cả khi chưa ở góc thứ nhất |
| LB + D-pad xuống | Tắt camera khẩn cấp và khôi phục góc nhìn GTA V |
| LB + nút X | Mở menu chỉnh camera trong game |
| F6 (bàn phím ngoài) | Bật/tắt mod |
| F7 (bàn phím ngoài) | Ép dùng camera dù game chưa ở góc thứ nhất |
| F8 (bàn phím ngoài) | Đổi cấu hình |
| F9 (bàn phím ngoài) | Khẩn cấp: tắt và trả lại camera GTA V |
| F10 (bàn phím ngoài) | Mở/đóng menu camera |
| F11 (bàn phím ngoài) | Chuyển kiểu nhìn quanh |
| N / B (bàn phím ngoài) | Chuyển camera / tạm dừng tự cân giữa |

Trong menu, dùng **D-pad lên/xuống** để chọn mục; **D-pad trái/phải** để thay
đổi giá trị; **A** để chọn; **B** để đóng. Menu hiển thị bằng phụ đề game (chưa
có panel UIKit riêng). Không mở menu trong lúc thực hiện nhiệm vụ nhạy cảm.

## Có trong bản thử nghiệm

- Camera tại vị trí đầu người lái; tương thích logic ghế lái trái/phải về mặt tọa độ.
- FOV 92° / 100° / 115° mặc định, chỉnh 50–130° trong menu, thay đổi vị trí và các góc lệch camera.
- Quán tính tăng tốc/phanh/vào cua/bề mặt, rung nhẹ theo vận tốc, khóa đường chân trời.
- Ba cách nhìn quanh bằng cần analog: Direct, Classic, Directional; nút dừng tự cân giữa.
- Mỗi mẫu xe hoặc biển số có thể giữ cấu hình độc lập với tối đa 10 camera. Có chức năng thử lưu ra `DFPV_iOS.ini` cạnh DLL khi có quyền ghi; nếu không được, chỉ giữ trong RAM.
- Tùy chọn DOF theo tốc độ, mặc định **tắt** để tránh ảnh hưởng hiệu năng. Lỗi DOF sẽ tự tắt phần hiệu ứng này.
- Khi ngắm bắn trong xe, trả về camera gốc của game để hạn chế lệch mục tiêu.
- Tự giải phóng camera khi ra xe, chết, pause, cutscene, chuyển góc, mất quyền camera hoặc gặp lỗi.
- Không can thiệp nhị phân GTA5, libgtacompat, ScriptHookV hay Menyoo.

## Chưa tương đương mod PC 1.3.2

- Menu hiện dùng phụ đề và nút gamepad, chưa phải menu gốc của ikt / chưa có nút chạm UIKit riêng.
- Chưa có native hide-head chuẩn và tránh xuyên hình toàn diện; một số kiểu xe/nhân vật có thể lộ đầu hoặc lệch vị trí.
- Chưa tái tạo hỗ trợ vô lăng Manual Transmission, lọc cửa kính khi nhìn qua vai và các memory patch của bản PC.
- DOF và đường ngắm trong phiên bản iOS mới là triển khai tương đương, chưa được kiểm chứng với engine v2699.
- Chưa xác minh hoạt động khi các mod camera khác đang chạy. Chưa thử thực tế trên iPhone.
- Nếu mod không xuất hiện, cần kiểm tra `ScriptHookVDotNet.log`, `posthook.log`, `disabled-scripts.txt`.

## Khôi phục khi có lỗi

Tắt mod trong Trainer → ScriptHook → Mods (nếu được hỗ trợ), hoặc xóa
`mods/scripthook/scripts/DynamicVehicleFirstPersonIOS.dll` trong phần Files.
Sau đó khởi động lại game. IPA nguyên gốc vẫn giữ nguyên.

Đối chiếu: GTA V v11.1 dùng `.shv.dylib`/ScriptHookV .NET do posthook; Windows
`.asi` là PE32+ x86-64 và bị launcher từ chối. Bản này sử dụng DLL .NET độc lập.
