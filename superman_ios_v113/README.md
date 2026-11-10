# Superman iOS v11.3 — ARM64 prototype v0.1 (chưa kiểm thử máy thật)

Đây là **bản viết lại độc lập**, dựa trên chức năng và thông số của gói
Superman by TamedMods mà người dùng cung cấp. Không biên dịch lại hay chạy
`Superman.asi`: tệp `.asi` gốc là **Windows x86-64** và không chạy trực tiếp
trong GTA V iOS ARM64.

## Tính năng đã viết trong mã nguồn

| Nút trên màn hình | Tác dụng dự kiến |
|---|---|
| S | Bật/tắt Superman; mặc định **tắt** |
| BAY | Bật/tắt chế độ bay (tắt thì phục hồi trọng lực) |
| TIẾN (giữ) | Bay theo hướng camera |
| LÊN / XUỐNG (giữ) | Tăng/giảm độ cao |
| NHANH (giữ cùng TIẾN) | Tăng tốc khi bay, không tác động chạy bộ |
| HEAT (giữ) | Vẽ hai tia đỏ-vàng + bắn viên đạn vô hình có sát thương hạn chế |
| SÓNG | Đẩy các NPC, xe ở gần, hồi chiêu 2,4 giây |
| NỆN | Sóng xung kích ngắn, đẩy lên cao hơn |

Các nút này gọi trực tiếp luồng xử lý mod, **không giả phím J/K/L/M** của trò chơi.
Giữ `S` 0,6 giây để chuyển chế độ **di chuyển nút**, kéo nút rồi giữ `S`
lần nữa để lưu/thoát. `S` còn xuất hiện khi mod tắt; các nút khác được ẩn.

Mod có giới hạn an toàn: chỉ hoạt động khi `NETWORK_IS_SESSION_ACTIVE` trả về
false; khi chuyển Online tự tắt, ngừng bay và phục hồi trọng lực. Không viết
đè lên cấu hình Trainer, Menyoo hoặc các nút cảm ứng gốc. Khi bật máy lần đầu,
Superman **không tự chạy**.

### Chưa có trong v0.1

- Không có freeze breath, chạy siêu tốc, hệ thống chiến đấu/takedown/camera
  và hơn 200 tuỳ chọn PC của TamedMods.
- Không mô phỏng cả năm loại laser: hiện chỉ là Heat Vision.
- Hiệu ứng hiện là đường tia 3D cơ bản và vật lý đẩy; **chưa phải particle
  phức tạp như bản Windows**.
- Các nút bàn phím vật lý F10/R/Space **chưa được liên kết trực tiếp**; thay thế
  bằng nút cảm ứng tên sức mạnh. `CustomTouch` cũ được giữ nguyên nếu bản IPA
  đầu vào đã có, nhưng không cần dùng nút J để kích hoạt Superman.
- Chưa kiểm tra shader, hoạt ảnh Superman, tác động FPS, tải dài hoặc tương
  thích trên iPhone/iPad thực tế. Bản v0.1 là **mã nguồn thử nghiệm**, không
  tuyên bố là một mod đã chạy được.

## Cách dùng GitHub Actions trên iPhone

1. Trong repository của bạn, tạo thư mục `superman_ios_v113/` rồi tải các file
   `.cpp`, `.hpp`, `.mm`, `.sh`, `.py`, `.json`, `README.md` vào đúng đường dẫn.
   Không tải `Superman.asi` lên GitHub (đây là DLL Windows, không cần thiết).
2. Tạo file ở **đúng đường dẫn của repository**:
   `.github/workflows/build_superman_ios.yml` (không để trong
   `superman_ios_v113/.github`). Sao chép workflow đi kèm.
3. Mở **Actions → Build Superman iOS ARM64 (source only) → Run workflow**.
4. Nếu build thành công, tải artifact `SupermanIOS-v11.3-ARM64-dylib-ADHOC`,
   trong đó có `libSupermanIOS.dylib` arm64. File này **chưa phải IPA**.

Trên máy macOS hoặc Linux có Python 3.10+, tích hợp vào bản v11.3 mà bạn có
quyền sử dụng bằng lệnh:

```bash
python3 superman_ios_v113/install_unsigned.py \
  --ipa GTAV-v11.3.ipa \
  --dylib libSupermanIOS.dylib \
  --sfx-zip '16b0b2-Superman_by_TamedMods_v1.0.zip' \
  --output GTAV-v11.3-Superman-UNSIGNED.ipa
```

`--sfx-zip` là tuỳ chọn: nếu bỏ qua, vẫn tạo bản thử nghiệm nhưng âm thanh sẽ
không có trừ khi `Superman_SFX/*.wav` nằm trong thư mục dự án. File âm thanh
`takeoff.wav`, `heat_vision.wav`, `thunder_clap.wav`, `ground_pound.wav` dùng
**chính tệp người dùng cung cấp**; tôn trọng quyền phân phối của tác giả, không
đưa các WAV lên repo GitHub public.

> **QUAN TRỌNG:** IPA sau khi chèn dylib là **UNSIGNED**. Nó không cài được
> trước khi toàn bộ app và dylib được ký lại bằng chứng chỉ phù hợp (SideStore
> hoặc công cụ ký IPA hợp lệ). Giữ bản IPA gốc và dữ liệu save dự phòng.
> Không dùng `Superman.asi` để Import Script nữa.

## Đảm bảo cấu trúc IPA

`install_unsigned.py` chỉ chấp nhận đúng SHA-256 đã được kiểm tra của:

- File gốc `GTAV-v11.3(1).ipa`, hoặc
- Bản `GTAV-v11.3-CustomTouch-UNSIGNED-TEST.ipa` được tạo trước đó.

Nó chèn **một LC_LOAD_DYLIB** vào khoảng đệm Mach-O nếu có đủ khoảng trống,
thêm `libSupermanIOS.dylib`, một file JSON và tối đa bốn file WAV. Các mục IPA
cũ khác được đối chiếu nguyên byte; tool sẽ từ chối IPA không khớp, đã có mod,
không còn khoảng trống, hoặc output tồn tại. Không thay engine `GTA5` logic,
`libgtacompat.dylib`, `ScriptHookV.dylib`, Menyoo, Trainer, launcher, hay các
layout cảm ứng đã có.

Điều này xác minh **cấu trúc ZIP và nhị phân tĩnh**, không chứng minh app sẽ
khởi động hoặc hoạt động đúng trên iPhone.

## Kiểm thử trên Linux/macOS trước khi build

```bash
g++ -std=c++17 -Wall -Wextra -DSUPERMAN_MATH_ONLY \
  superman_ios_v113/GameplayCore.cpp superman_ios_v113/tests/test_math.cpp \
  -o /tmp/superman_math_test
/tmp/superman_math_test

GTA_V11_3_IPA='/đường/dẫn/GTAV-v11.3.ipa' \
  python3 -m unittest discover -s superman_ios_v113/tests -v
```

Kiểm thử cần trên iPhone 13 Pro Max: vào Story Mode, xem nút S xuất hiện,
bật BAY và nhấn TIẾN/LÊN/XUỐNG, dùng HEAT, SÓNG/NỆN gần NPC và xe, sau đó
tắt S xem trọng lực trở lại. Test tiếp khả năng vào Online và khởi động lại
để kiểm tra xung đột với Menu Menyoo/CustomTouch. Nếu văng: gửi crash log,
`run.log`, `posthook.log` và tên IPA gốc để xác định đúng hash.

## Tham khảo kỹ thuật đã đối chiếu

- [Native ScriptHookV SDK (`scriptRegister`, `nativeInit`, `nativeCall`)](https://github.com/DevBlocky/ScriptHookV_Template/blob/master/inc/main.h)
- [Native database của citizenfx](https://github.com/citizenfx/natives)
- [GET_GAMEPLAY_CAM_ROT](https://github.com/citizenfx/natives/blob/master/CAM/GetGameplayCamRot.md)
- [SET_ENTITY_VELOCITY](https://github.com/citizenfx/natives/blob/master/ENTITY/SetEntityVelocity.md)
- [APPLY_FORCE_TO_ENTITY](https://github.com/citizenfx/natives/blob/master/ENTITY/ApplyForceToEntity.md)
- [SHOOT_SINGLE_BULLET_BETWEEN_COORDS](https://github.com/citizenfx/natives/blob/master/MISC/ShootSingleBulletBetweenCoords.md)

Không có mã nguồn C++ gốc TamedMods trong gói ZIP; chỉ có `.asi` đã biên dịch.
Các chức năng viết ở đây là bản triển khai mới, có thể khác nhiều so với mod
TamedMods PC và **cần thử máy thật** trước khi phát hành.
