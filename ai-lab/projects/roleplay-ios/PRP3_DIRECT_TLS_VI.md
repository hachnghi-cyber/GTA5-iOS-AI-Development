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
