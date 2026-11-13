# GTA V iOS Roleplay — Kế hoạch phát triển có thể tiếp nối

## Kiến trúc đích (thiết kế, CHƯA xác nhận đã tích hợp)
1. iOS app / existing GTA V port — dùng môi trường hợp pháp và có quyền sửa đổi.
2. Native compatibility layer — map phiên bản, ABI, hooks và input adapters.
3. RP client module — UI, nghề nghiệp, cảnh sát, còng, áp giải, nhà tù, EMS, taxi, giao dịch.
4. Versioned network protocol — handshake, session, sequencing, anti-replay, reliable state updates.
5. Authoritative RP server — xác thực danh tính, quyền sở hữu entity, trạng thái công việc, inventory/transactions và audit log.
6. CI and device verification — unit/integration tests, emulator mocks, signed iOS build (khi có Apple toolchain), on-device crash/performance.

## Lộ trình có điều kiện
- **M0: IPA fingerprint** (RP-001) — có SHA256, Mach-O UUID, Info.plist, dependency map và rủi ro.
- **M1: API mapping** (RP-002) — xác định native/game ScriptHook hỗ trợ thực tế, phân biệt iOS với Windows.
- **M2: Code consolidation** (RP-003) — xác định bản nguồn RP mới nhất, chưa đánh đồng mã đã viết với mã đã chạy.
- **M3: Networking POC** (RP-004) — giao thức versioned, authentication, ownership, anti-replay, server authoritative.
- **M4: Roleplay gameplay** (RP-005) — police interaction, cuff/uncuff, escort, jail, EMS, taxi, sync players.
- **M5: iPhone/iPad validation** (RP-006) — build link/sign, gameplay test, resource/crash regression and rollback.

## Tự động hóa theo tầng
- **Tầng 1 đã có trên PR #1:** role routing, Python CI, tests, optional read-only Codex review.
- **Tầng 2 bổ sung ở đây:** state.json, continuity checker, handoff artifact trong Actions.
- **Tầng 3 CHƯA kích hoạt:** agent chạy các issue triển khai bằng API/CI, tạo nhánh + PR sau khi chạy kiểm thử, giới hạn chi phí/tokens/quyền.
- **Tầng 4 CHƯA kích hoạt:** build/sign IPA và kiểm thử trên thiết bị; cần Mac runner + quyền ký + thiết bị thật.

## Tiêu chuẩn hoàn thành một nhiệm vụ
Mỗi PR phải có: input exact version/hash, bằng chứng, code diff, kiểm thử thật, những phép thử chưa thể chạy, regression risk, rollback, trạng thái `state.json` mới. Nhánh main chỉ merge sau review.

Tài liệu nguồn Cfx FiveM: https://docs.fivem.net/docs/client-manual/system-requirements/

## Quy trình thực thi tuần tự P0–P9 (bắt buộc từ 13/11/2026)

**Tài liệu chi tiết và nguồn sự thật:**
`ai-lab/projects/roleplay-ios/SEQUENTIAL_EXECUTION_PLAN.md`.

**Cổng máy đọc:** `PHASE_GATES.json`; chạy
`python ai-lab/sequential_gate.py --output ai-lab/reports/RP_PHASE_STATUS.json`.
Unit tests phải từ chối nhảy giai đoạn hoặc đánh dấu `verified` thiếu
evidence và người review. Tool chỉ kiểm tra bản khai, không xác minh log độc lập.

Thứ tự công việc cố định: **P0 chuẩn hóa PR/baseline → P1 engine hooks/trusted
identity → P2 network authenticated → P3 Police RP tối thiểu trên hai iPhone
→ P4 Police đầy đủ → P5 UI/touch/Việt hóa → P6 EMS/taxi/nghề phụ →
P7 economy/persistence → P8 stress/security/crash/performance →
P9 IPA ký/kiểm thử/phát hành thủ công**.

**P0 hiện tại vẫn chưa hoàn thành:** PR #7/#4/#9/#8 đều là draft và chưa
merge vào `main`; phải review/xử lý conflict (đặc biệt `state.json`)
và CI khi gom source. Dù thư viện ARM64 được build thành công, không nhảy
thẳng tới bước phát hành hoặc tuyên bố Police RP đã chạy Online.

Công việc tự động mỗi lần chỉ xử lý **P0**, hoặc chuẩn bị test/research trực tiếp
phục vụ gate P0; không mở hàng loạt chức năng vượt gate. Các bản nháp đã có
được giữ nguyên cho tới khi được review.

