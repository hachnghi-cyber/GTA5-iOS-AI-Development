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
