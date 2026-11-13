# P0 — Integration preview, not merged into main

Source parent: `d83bcd049649856411595b8cbf7d5c7c4288311e` (2026-11-13).

| Source PR | Immutable head SHA |
|---|---|
| [#7](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/7) | `5ca26698fad9425cf5c059674f3c984a5bd3b00f` |
| [#4](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/4) | `784c9e257e84707e3896982c280002697f5344ea` |
| [#9](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/9) | `e32415c3184cdaca1338613a425014dd57552c27` |
| [#8](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/pull/8) | `61d42522b7efa9df196a08f31ed8acc9697c150f` |

Combined 38 non-state file blobs using the PR order #7 → #4 → #9 → #8. The only shared changed path between PRs is `ai-lab/projects/roleplay-ios/state.json`. Main also changed `ai-lab/tests/test_continuity.py` since PR #4 split: this preview deliberately uses the PR #4 fix that makes the negative test independent of current evidence.

`state.json` starts from the PR #4 P0 phase/state and retains the v12 IPA/executable SHA256 and UUID; it adds unique verified facts, provenance, PR #9 snapshot and offline opt-out metadata and source-only release documentation. RP-006 source-level release-readiness engineering is **in-progress** (from PR #8), while P9 actual signed IPA release is **not-started** and P0 gate remains **in-progress**. This distinction was corrected after checking all source PR backlogs; it does not imply readiness to release.

## Review gate

- Verify the complete diff, all source file ownership and the reconciled `state.json`.
- Verify combined Python/C host tests including sanitizers, iPhoneOS ARM64 **unsigned source library** and phase/release gates.
- Examine any CI failures and fix on this preview branch only; do not merge `main` or the underlying PRs automatically.
- Real GTA v12 authenticated game-frame and network carrier, two-device gameplay and IPA signing are not verified. No IPA or assets have been uploaded.

Rollback: delete this standalone preview branch/PR after review. Original branches and main remain untouched.

## Đối chiếu nguồn tự động trên preview (P0 sub-gate)

- Manifest: `P0_SOURCE_PROVENANCE.json`, pin 4 commit source của PR #7/#4/#9/#8 và 38 git blob SHA-1 (định dạng Git; **không** phải SHA-256 của IPA).
- Kết quả audit: **37/38** path giữ nguyên git blob của PR gốc; **1 path** `.github/workflows/gta-ai-lab-ci.yml` được thay đổi *có khai báo* chỉ để thêm bước kiểm tra P0 và artifact. Cả hash trước/sau và lý do được pin trong `review_overrides`. Không được chấp nhận những sửa đổi không khai báo.
- `state.json`: giữ đầy đủ **21/21** mục verified_fact độc nhất với `claim`, `evidence` và `scope` y nguyên từ bốn PR; baseline IPA/executable SHA-256 và Mach-O UUID giữ nguyên; `device_tested=false`, `actual_build_artifact=null`.
- GitHub Actions run <https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43371346949>: **75/75 Python tests** và P0 source audit thành công (`p0-source-consistent`, `blocking_checks=[]`), ngoài ra 7/7 chương trình test C chạy thành công trong từng cấu hình normal, UBSan và ASan+UBSan. Build iPhoneOS ARM64 trong workflow riêng vẫn là **dylib độc lập, không phải IPA**.
- Bản xác minh này chỉ chứng minh nội dung mã nguồn, test host và tính nhất quán metadata. **Không xác minh tính tương thích gameplay GTA Online.**

### Checklist review thủ công trước khi chuyển P0→P1

- [ ] Chủ dự án xem diff của PR #10 và bốn nhánh nguồn, kiểm tra quyền/phạm vi phân phối mã.
- [ ] Quyết định thứ tự duyệt PR #7→#4→#9→#8; không merge chồng từng PR thiếu kiểm tra vì `state.json` xung đột trên bốn PR.
- [ ] Chọn chiến lược merge: hoặc review riêng rồi hợp nhất với xử lý conflict, hoặc review nhánh preview như một changeset tổng hợp; tuyệt đối tránh duplicate commits/double-merge.
- [ ] Kiểm tra test CI trên merge tip cuối và rà warning, ABI, dependency/rollback.
- [ ] Chỉ sau khi phê duyệt và có kết quả kiểm tra `main`, cập nhật `PHASE_GATES.json` P0=verified kèm bằng chứng và reviewer.

**Chưa hoàn thành P0:** PR #10 đã chuyển sang **Ready for review** (không phải đã merge); chưa có review phê duyệt từ người khác, P0 vẫn `in-progress`. Bước sau khi P0 được duyệt: P1 xác minh game-frame callback và danh tính Online bằng log iPhone v12 thật. Không tự merge, tự ký hoặc xuất bản IPA.

## P0 bổ sung: bảo toàn tiến độ backlog khi hợp nhất PR

Rà đối chiếu task-level `state.json` cho PR #7/#4/#9/#8 phát hiện
`RP-006` ở PR #8 đã `in-progress` nhưng preview vẫn `not-started`.
Đã khôi phục trạng thái **`in-progress` chỉ cho công việc tạo bộ kiểm tra
phát hành**, bổ sung nguồn PR #7 identity gate vào RP-001 và mô tả
bridge/consent của PR #9 vào RP-003. Cổng phát hành cuối P9 vẫn
`not-started`; `auto_release_allowed=false`.

Manifest `P0_SOURCE_PROVENANCE.json` hiện pin `required_task_progress`.
`ai-lab/p0_integration_audit.py` bắt buộc mỗi task giữ đúng status,
bằng chứng, mốc mô tả và các khóa metadata quan trọng của PR #9.
Các unit test mới cố ý loại bỏ lần lượt status RP-006, nguồn
`release_readiness.py`, metadata `consent_outage_retry` để xác minh CI
thật sự từ chối mất tiến độ khi merge.

Các kiểm tra P0 chỉ xác thực dữ liệu khai báo của repository, chưa tự
xác minh IPA/gameplay; review hợp nhất và P1 vẫn phải theo gate riêng.

## P0 review-readiness: kiểm tra live trạng thái GitHub (13/11/2026)

Đã bổ sung `ai-lab/p0_review_readiness.py` và 12 unit test độc lập,
chạy ngay sau `RP_P0_AUDIT.json` trong GitHub Actions của nhánh review.
Bộ kiểm tra gọi **chỉ đọc** GitHub REST API để xác minh: PR #10 đang mở,
không còn Draft, nhánh/base SHA vẫn đúng manifest, GitHub báo mergeable,
audit 38 file + 21 nguồn bằng chứng đạt, và có **ít nhất một reviewer
khác tác giả** phê duyệt đúng commit mới nhất (không chấp nhận approval cũ
hoặc `CHANGES_REQUESTED` còn hiệu lực). Không làm thay đổi `PHASE_GATES.json`.

Khi lần đầu chạy ở chế độ Draft, CI #43378573784 đạt **92 Python tests**
và phát hành `RP_P0_REVIEW_STATUS.json` có kết quả `blocked-review`,
chỉ rõ `not_draft` và `independent_head_approval` còn chặn. Sau đó
PR #10 đã được đưa sang **Ready for review**, không merge `main`,
không cấp quyền phát hành IPA. Những lần CI tiếp theo phải xác minh
lại bằng GitHub REST và vẫn chặn khi chưa có approval độc lập.

**Quyền kiểm tra không phải quyền merge:** script luôn trả
`auto_merge_allowed=false` và
`p0_phase_verified_by_this_check=false` ngay cả khi có reviewer phê duyệt.
Review cuối phải xem cả source diff, cổng test, xung đột và kế hoạch rollback.
