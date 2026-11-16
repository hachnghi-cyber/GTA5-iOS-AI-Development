# PRP3 qua kênh RP trực tiếp

Winstom 0.7.177 có dấu hiệu tách đồng bộ gameplay RP khỏi callback game,
cùng các lớp quản lý phiên và transport. Kết quả tĩnh đó chưa chứng minh
giao thức thực tế của Winstom. Xem `WINSTOM_V133_PHASE9_SENDER_CARRIER.md`.

Kênh thử của dự án lấy ý tưởng tách transport và tự ghép cặp hai đầu:
một đầu kết nối trực tiếp tới đầu kia qua TCP, xác thực TLS 1.3 hai chiều
với CA riêng và SHA-256 của chứng chỉ peer đã biết ở cả hai đầu. Hai đầu
so đối chiếu ID RP, phiên và generation qua hello sau xác thực. Sender
lấy từ ghép cặp chứng chỉ. PRP3 40 byte giữ nguyên và chỉ có GREET/DOCUMENTS.
Mỗi đầu giữ nonce tăng dần qua nhiều lần reconnect trong cùng generation.
Đổi generation hoặc phiên sau khi khởi động lại tiến trình.
[Python ssl](https://docs.python.org/3/library/ssl.html#ssl.CERT_REQUIRED)

Module `v133_interaction/tools/prp3_direct_tls.py` là bản tham chiếu host.
Không cần relay trung tâm cho đường kết nối trực tiếp này. Listener phải
có thể tiếp cận qua mạng thử riêng. Bộ test dùng hai socket TCP loopback,
TLS thật và chứng chỉ sinh trong thư mục tạm. Phần chạy không cần thư viện
Python ngoài chuẩn. Test cần `cryptography==50.0.2` để sinh chứng chỉ.

```sh
python -m pip install cryptography==50.0.2
python -m unittest discover -s ai-lab/projects/roleplay-ios/v133_interaction/tests -p 'test_prp3_direct_tls.py' -v
```

ID ghép cặp TLS là danh tính RP. Trước khi enqueue vào mailbox trên iPhone,
cần adapter native và phép nối riêng từ ID RP đã xác thực đến tay chơi đang
đồng ý tham gia trong đúng phiên game. Giữ gate proximity, consent, game
thread và authority của dự án. Thử tiếp iPhone ↔ máy tính, sau đó xác nhận
hai iPhone trong Sandbox riêng. Chưa tích hợp hook hay bật gameplay RP;
IPA chẩn đoán hiện tại vẫn chỉ kiểm tra khởi động.


## Phép thử iPhone ↔ Windows

`PRPV133TLSProbe.m` được gọi từ startup probe chỉ khi UUID khớp. Nó đọc
cấu hình riêng qua Documents, xác thực TLS 1.3 và trao đổi GREET/DOCUMENTS
một lần trong kênh chẩn đoán. Identity PKCS#12 và trust anchor chỉ dùng
cho phép thử, không cài root CA vào máy. Các tệp ghép cặp hết hạn sau 20
phút. [Apple Network TLS](https://developer.apple.com/documentation/network/tls-options)

1. Build dylib ARM64 từ Actions. Dùng packer với bản v13.3 gốc và
   `--enable-file-sharing --enable-tls-probe`, sau đó ký lại IPA và các dylib.
2. Kết nối iPhone và máy tính vào cùng mạng LAN riêng. Từ thư mục repo,
   sinh bộ ghép cặp mới trong thư mục **ngoài repo**:

   ```powershell
   uv run --python 3.13 --with cryptography==50.0.2 python ai-lab/projects/roleplay-ios/v133_interaction/tools/run_ios_tls_probe.py prepare C:/path/to/new-private-kit --ip 192.168.1.50
   ```

   Thay IP ví dụ bằng địa chỉ LAN của máy Windows. Chỉ chuyển tệp
   `PRP3TLS-Probe-PRIVATE.json` vào Documents của app đã ký qua USB File
   Sharing. Tệp chứa identity thử, không đính kèm khi chia sẻ kết quả.
3. Chạy lệnh trên với `serve C:/path/to/new-private-kit` thay cho
   `prepare ... --ip ...`. Khi Windows báo sẵn sàng, mở app trên iPhone.
   Nếu iOS hỏi quyền mạng nội bộ, chọn cho phép để thực hiện phép thử.
   Có thể lấy log ngay từ launcher, không cần vào phòng chơi.
4. Kết quả chỉ đạt hai chiều khi host báo `paired_client_greet_received=true`
   và log mới `PoliceRP-v13.3-TLS-Probe.txt` có
   `result=greet_sent_documents_received` cùng `paired_tls_verified=1`.
   Kiểm tra dấu thời gian để tránh dùng log cũ. Xóa cấu hình thử sau khi
   thu log, hoặc tạo bộ ghép cặp mới cho lần thử tiếp.

Lần kiểm thử host giải mã PKCS#12 sinh từ kit rồi dùng một client Python
đối chứng với responder trên socket TLS thật. Hành vi Security/Network
framework, quyền mạng nội bộ và thiết bị iPhone cần kiểm chứng riêng.
