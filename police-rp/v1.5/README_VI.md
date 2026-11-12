# Police RP Only v1.5 — Duty State Probe (không phải mod RP)

**Mục tiêu duy nhất:** đo xem 2 biến nghề `s_iMacportWork` và trạng thái nhận ca
`s_bMacportWorkOnShift` trong GTA5 v12 thay đổi ra sao khi chơi Story và Online.
Dữ liệu ghi vào `Documents/PoliceRPDuty-v15.txt`, chỉ thay đổi khi giá trị thay
đổi hoặc mỗi 30 giây để xác minh bộ đếm timer còn hoạt động.

Đây là **bản chẩn đoán chỉ đọc**. Không bật Menyoo, không bật ScriptHook Online,
không tạo NPC, không gửi gói mạng, không còng hay dịch chuyển người chơi.
Không áp dụng địa chỉ cho IPA khác phiên bản UUID `6A498E32-E70C-334C-BCA3-AFFD35E8D171`.

## Kiểm thử mã nguồn

```
python3 -m unittest discover -s Tests -p 'test_duty_v15.py' -v
```

Các bài thử xác minh parser và chuỗi trạng thái. Không thay thế kiểm thử iPhone.

## Build iOS trên GitHub Actions

1. Đưa `Diagnostics/PoliceRPDutyProbe.c` vào repo, và workflow
   `.github/workflows/build-prp-v15-duty-ios.yml`.
2. Chạy workflow **Police RP v1.5 - iOS native police duty read-only probe**.
3. Tải artifact `PRP-v15-iOS-arm64-DUTY-PROBE-NOT-GAMEPLAY`.
4. Gửi `PoliceRPProbe.dylib` vào ChatGPT để kiểm tra Mach-O và tạo IPA chẩn đoán
   dựa trên **v12 THƯỜNG bản gốc** (phải ký lại sau khi tạo).

Nếu dùng iPhone và không muốn upload từng thư mục, dùng gói ZIP nhỏ và workflow
`import-police-rp-v15-IPHONE.yml` bên ngoài ZIP.

## Kiểm thử trên iPhone (sau khi nhận IPA chẩn đoán v1.5)

1. Sao lưu dữ liệu game, ký và cài IPA test.
2. Mở game, đứng yên khoảng 5 giây.
3. Chọn nghề Cảnh sát Los Santos rồi nhận ca. Đợi 5 giây.
4. Kết thúc ca hoặc đổi nghề. Đợi 5 giây.
5. Lặp lại thử nghiệm trong phiên Online riêng nếu Story Mode ổn định.
6. Mở Tệp > Trên iPhone > GTA V > Documents > `PoliceRPDuty-v15.txt`
   (tên thư mục Documents có thể hiển thị khác theo app).
7. Gửi tệp txt. Không cần gửi mã mời hoặc mật khẩu phòng.

Ví dụ log:
```
[PRP_DIAG_V15] dylib_loaded=1 gta5_uuid_verified=1 hooks=0 network_events=0 police_gameplay=0 timer=main_queue_1s
[PRP_DUTY_V15] tick=1 job=-1 shift=0 police_active=0 label=none
[PRP_DUTY_V15] tick=15 job=0 shift=1 police_active=1 label=cop_ls
[PRP_DUTY_V15] tick=25 job=0 shift=0 police_active=0 label=cop_ls
```

Các giá trị trên chỉ là ví dụ, không phải kết quả thực tế.

Đọc log tự động:
```
python3 Tools/check_duty_v15.py PoliceRPDuty-v15.txt
```

Nếu chỉ có dòng DIAG không có dòng DUTY: thư viện được nạp nhưng main queue
không chạy callback; cần thay đổi phương án chẩn đoán, không kết luận sai offset.
Nếu log có giá trị bất thường: dừng kiểm thử, quay lại IPA gốc.

## Giới hạn

- Việc đọc biến native là thử nghiệm; chưa được xác minh trên hai iPhone.
- Không có Native Hook thực thi Police RP và không có đồng bộ mạng.
- Chưa có IPA Police RP bắt người được.
- Đường dẫn Mach-O chỉ dùng với đúng GTA5 v12 đã kiểm tra; phải ký lại IPA
  khi thay đổi thư viện hoặc load command.
