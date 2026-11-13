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

## P0 cổng chống CI cũ được dùng cho commit PR mới (13/11/2026)

Một lượt kiểm tra review lấy trạng thái mới nhất từ GitHub REST có thể chạy
đồng thời với push mới. Khi đó source audit đã kiểm tra commit A nhưng
review API lại trả về commit B. Trước đây bộ kiểm tra chỉ xác nhận
`head.sha` có định dạng hợp lệ; nay đã thêm **`head_matches_ci_event`**
để ràng buộc SHA mới nhất với commit từ **cùng sự kiện GitHub Actions**.
Trên sự kiện push, `PR_HEAD_SHA` là `github.sha`; trên
`pull_request`, `PR_HEAD_SHA` dùng `github.event.pull_request.head.sha`
(thay vì synthetic merge commit). Nếu thiếu hoặc khác SHA thì
`source_review_ready=false`, không tự merge và không nâng P0.

Ba test mới kiểm tra: PR được push commit mới trong lúc job chạy dù đã có
review cho commit mới; SHA CI thiếu; SHA CI không hợp lệ. Bằng chứng:
<https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43394341355>
— 95/95 Python unit tests, audit P0 không có blocker, 7/7 C programs
ở mỗi cấu hình host normal/UBSan/ASan+UBSan. Review hiện vẫn
`blocked-review` **duy nhất vì `independent_head_approval`**,
không có quyền phát hành tự động. iPhoneOS ARM64 dylib build ở
<https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43394341359>
chỉ là thư viện độc lập, không phải IPA/gameplay.

## P0: review có hiệu lực, loại trừ bot, bỏ qua comment (13/11/2026)

Rà soát API GitHub phát hiện hai trường hợp sai ở
`ai-lab/p0_review_readiness.py`:

- `COMMENTED`/`PENDING` của **cùng reviewer** từng bị dùng thay
  thế `APPROVED` hoặc `CHANGES_REQUESTED`. Một bình luận sau khi
  phê duyệt không phải lệnh rút phê duyệt; bình luận sau khi yêu cầu
  sửa cũng không xóa yêu cầu sửa. Bộ chọn giờ chỉ lấy quyết định
  mới nhất trong `APPROVED`, `CHANGES_REQUESTED`, `DISMISSED`.
- `APPROVED` từ bot hoặc tài khoản chỉ đọc không được tính như
  review độc lập có thẩm quyền. Chỉ chấp nhận `user.type=User`
  và `author_association` thuộc `OWNER`, `MEMBER`, `COLLABORATOR`
  trên **đúng CI event head SHA**. So sánh login tác giả không phân
  biệt hoa/thường. Đây là gate thận trọng, **không thay thế** GitHub
  branch-protection hoặc quyết định của người duyệt.

Đã thêm các test hồi quy cho comment sau approve/request-changes,
dismissed review, approve lại sau request-changes, bot, người lạ và
tên đăng nhập khác cách viết. Nguồn tham chiếu:
https://docs.github.com/en/pull-requests/reference/pull-request-reviews
và
https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews.

**Rủi ro còn lại:** PR #10 chưa có reviewer độc lập. Dù CI xanh,
`P0` vẫn `in-progress`. Không tự tạo review để vượt gate.

## P0 cross-PR source integration và build Apple SDK (13/11/2026)

Đã kiểm thử thực tế source C của PR #4 và PR #9 **trong cùng một chương
trình host**, thay vì chỉ chạy các regression riêng lẻ. Test
`test_p0_combined_selection.c` xác minh quy trình chọn mục tiêu gần,
host kiểm tra lại khoảng cách sau khi mục tiêu di chuyển, đồng bộ
`PRP_OP_STATE` chỉ cho người nhận đúng ID và opt-out giải phóng local ped.
Lệnh compile và assertions nằm trong
`ai-lab/tests/test_p0_combined_target_bridge.py` và được chạy với
compiler host thông thường cùng Clang ASan+UBSan.
Bằng chứng: [CI 43399382390](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43399382390)
**104/104 Python tests**, các 7 chương trình C host đều đạt
trong ba cấu hình.

Đã tạo **workflow ARM64 bridge tích hợp** riêng:
`.github/workflows/gta-rp-ios-arm64-bridge.yml`.
[Build 43399591380](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43399591380)
thành công, cùng lúc biên dịch nguồn P2P/NativeBridge/Integration,
kiểm tra Mach-O `ARM64 DYLIB`, deployment min iOS 16.3,
SDK 18.5 và các symbol `_prp_bridge_frame`,
`_prp_host_find_nearest_cuff_target`, `_prp_inbox_push`.
Thư viện `libPoliceRPBridge.dylib` SHA-256:
`5da9aabdf9dc1ce0ddc6df83afeff4e13eec1cb0f01c5a2971b6abe79eff3381`.
Tệp bằng chứng và cách tái lập:
`P0_INTEGRATED_BRIDGE_PROOF.md`.

**Giới hạn bắt buộc:** đây là chương trình C với game snapshot/carrier
giả lập và dylib iPhoneOS độc lập **chưa tích hợp GTA5**; chưa chứng minh
entrypoint RAGE v12, carrier có xác thực, 2 iPhone chơi RP, ký hay IPA.
`P0` vẫn `in-progress` cho tới khi review và merge có chứng cứ.


## P0 audit hoàn chỉnh cho mọi thay đổi trên PR #10 (13/11/2026)

Phát hiện và sửa **thiếu bao phủ file** của công cụ provenance: phiên bản
trước kiểm tra 38 file sao chép từ PR #7/#4/#9/#8 và 21 claim gốc, nhưng
không kiểm tra các file do riêng nhánh P0 tạo ra. Một file CI mới hoặc
test thay đổi trên preview có thể không bị phát hiện.

Bộ kiểm tra `ai-lab/p0_integration_audit.py` giờ yêu cầu Git history
từ base SHA `d83bcd049649856411595b8cbf7d5c7c4288311e`
(`fetch-depth: 0` trong CI) và đọc diff thực
`git diff --name-status -z --no-renames BASE HEAD`:

- **38 path của PR nguồn**: kiểm tra Git blob; riêng workflow AI Lab có
  dual-hash review override đã khai báo.
- **9 path riêng của PR #10**: pin Git blob SHA-1 của từng file và trạng thái
  `A` (tạo mới), gồm code kiểm tra, test, workflow Apple ARM64,
  báo cáo tích hợp và test bridge tổng hợp.
- **1 `state.json`**: phải là thay đổi `M`; kiểm tra **nội dung có ngữ
  nghĩa**: baseline, 21 claim gốc và backlog. Không được tính là đã test iPhone.
- **1 `P0_SOURCE_PROVENANCE.json`**: self-manifest không thể pin hash
  của chính nó mà không dẫn đến tham chiếu đệ quy; bắt buộc đúng path,
  đúng schema, review và đúng tổng số file.

**Tổng 49 path.** Mọi path không khai báo, path bị xóa, hash file tạo
riêng sai, Git base thiếu hoặc trạng thái Git khác quy định đều
`blocked`. Chi tiết nằm trong report `RP_P0_AUDIT.json`.

Bằng chứng: <https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43401470546>
— **110/110 Python tests**, 7 C tests ở cả ba chế độ,
`p0-source-consistent`, `expected_total_changed_paths=49`,
`integration_only_count=9`, `blocking_checks=[]`.

### Phạm vi kiểm tra thủ công còn bắt buộc

Cổng CI này chứng minh **nội dung mã so với manifest và đường thay đổi Git**,
không chứng minh nội dung đó an toàn về mặt kiến trúc. Reviewer vẫn phải
đọc kỹ 9 file tạo riêng, `state.json`, manifest tự mô tả và
workflow CI; xác nhận phụ thuộc, quyền Actions và kế hoạch merge không
đưa trùng bản sao của PR #7/#4/#9/#8. Không tự hoàn thành P0 chỉ vì
CI đã xanh.


## P0 — Sửa lỗi giữ án tù khi cảnh sát rời phiên (13/11/2026)

**Phát hiện trên mã C thật, không suy đoán:** trước bản vá,
`prp_host_remove_peer()` gọi `set_free()` với **mọi** trạng thái
do cảnh sát tạo, kể cả `PR_JAILED`. Trong khi đó
`prp_host_update_peer()` đã ghi rõ án tù hoàn tất thuộc phiên RP,
không phụ thuộc cảnh sát tiếp tục làm việc. Đường `PRP_OP_CONSENT`
với `consent=0` cũng có lỗi tương tự.

**Bản vá tối thiểu** trong
`police-rp/v1.4/P2P/prp_p2p.c` giới thiệu
`revoke_officer_authority()`, được gọi khi cảnh sát nghỉ ca/mất
chứng thực nghề, rút consent hoặc ngắt kết nối. Hàm này:

- Nhả **CUFFED / ESCORTED** ngay, giữ hành vi fail-open.
- Giữ **JAILED**, giữ nguyên `release_at_ms`, nhưng xóa
  `officer_id` (chuyển sang session-owned) và tăng generation.
- Vì `officer_id=0`, một tài khoản khác nhận lại **cùng numeric
  player ID** không thể gửi `PRP_OP_RELEASE` để chiếm quyền cũ.
  Đối với án tù đã mất người quản lý, hệ thống hiện chỉ tự hết hạn
  theo đồng hồ host. **Phóng thích thủ công bởi cảnh sát khác cần
  thiết kế phân quyền mới**; không tự cho phép trước khi xác minh
  authenticated connection epoch.
- Nếu **người đang bị giam** tự rời phiên, trạng thái của chính
  người đó vẫn bị xóa; không giữ tù trên peer đã disconnect.

Regression được thêm vào `test_duty_exit.c`: cảnh sát phụ ID 30
khác host ID 10; cuff → escort → jail → disconnect; tái sử dụng
ID 30 không được thả tù; hết hạn; cuff/escort giải phóng khi
disconnect/opt-out; opt-out sau khi đưa vào tù không hủy án;
và tù nhân rời phiên xóa trạng thái của chính họ. Thời gian host
được tăng đơn điệu, vị trí verified được làm mới đúng lúc.

**Cổng provenance mới:** PR #10 có **50 đường dẫn**, gồm
38 tệp từ PR nguồn (35 giữ nguyên byte, **3 review_overrides**
có original/review hash và lý do), 10 integration-owned
(9 added, **1 modified** test C so với base), `state.json`
và recursive manifest. CI không được bỏ qua thay đổi behavior ở
`prp_p2p.c`.

Bằng chứng trên commit `ba45dc8a8321080aa996ce1a1a70f12d5b643c2d`:
[AI Lab CI #43408204816](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43408204816)
**112/112 Python unit tests** (bao gồm C host),
**7/7 C executables mỗi chế độ normal, UBSan, ASan+UBSan**;
P0 audit `p0-source-consistent`, không có blocker.
[Apple ARM64 bridge #43408205275](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43408205275)
và
[ARM64 core #43408204874](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43408204874)
đều thành công (unsigned source dylib, không phải GTA IPA).

**Chưa xác minh:** danh tính player incarnation/connection epoch từ
RAGE v12, chống replay consent toàn diện khi ID được dùng lại, gameplay
trên 2 iPhone, signed IPA. Review thủ công phải quyết định rõ về
thay đổi behavior (jail còn đến khi timeout, không chuyển giao manual
release khi officer rời ca) trước khi merge. P0 vẫn `in-progress`.


## P0 — Cổng host từ chối cảnh sát đang bị giam/còng (13/11/2026)

**Lỗi phát hiện khi review nguồn:** `prp_host_receive()` xác thực native
police job, shift, consent nhưng bỏ qua tình trạng của **chính người ra
lệnh** trong `h->states[sender_slot]`. Cảnh sát bị `PR_CUFFED`,
`PR_ESCORTED` hoặc `PR_JAILED` vẫn có thể tạo lệnh còng người khác
nếu engine còn báo on-shift. `prp_host_find_nearest_cuff_target()` cũng
vẫn đề xuất mục tiêu cho người đang bị khống chế.

**Bản vá nguồn** tại `police-rp/v1.4/P2P/prp_p2p.c` (commit
`c683676c37e0f1a78cd5bc45baa23488348aab69`): chỉ đề xuất
mục tiêu khi trạng thái cảnh sát là `PR_FREE`; host từ chối mọi lệnh
cảnh sát bằng `PRP_ERR_STATE` khi người gửi đang bị còng, áp giải hoặc
giam giữ. Lệnh `PRP_OP_CONSENT` vẫn được xử lý trước chính sách này
để người chơi được tự opt-out/fail-open. Code không cần offset/hook RAGE
hoặc quyền giả lập từ nick người chơi.

**Regression C bổ sung** trong `test_duty_exit.c`: cảnh sát phụ ID30 còng
cảnh sát chủ phòng ID10; người bị còng không được đề xuất mục tiêu hay
còng dân ID20. Thử tiếp trạng thái ESCORTED rồi JAILED, tất cả phải
bị từ chối; opt-out của người bị giam vẫn được chấp nhận. Sau khi
được giải phóng, consent trở lại và native police duty vẫn verified,
người chơi có thể tiếp tục bắt dân trong phạm vi. Test không giả lập
2 iPhone hay RAGE authenticated network.

### Kiểm thử: phân biệt đã chạy với chưa chạy

- **Đã xác nhận build iPhoneOS ARM64** cho nguồn bản vá ở
  [Core #43437315349](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43437315349)
  và [Bridge #43437315332](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43437315332).
  Chỉ xác nhận mã C đã liên kết thành dylib unsigned, không chạy test.
- **Regression mới chưa thực thi được**: GitHub Actions CI
  [#43437355926](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43437355926)
  và Source Watch #43437355937 báo failure **trước khi cấp runner**.
  GitHub REST trả về `runner_id=0`, `runner_name=""`, `steps=[]`,
  không có job log. Một lượt rerun job riêng (attempt 2) cũng fail
  trước khi thực thi. Tới commit `4a15b065`, **cả macOS build và Ubuntu
  validation** báo lỗi startup cùng dấu hiệu. Không được coi là lỗi
  assertion, compiler hay source audit; cũng **không được coi là test pass**.
- **CI đã xanh cuối cùng cho nguồn cũ** là
  [#43408725121](https://github.com/hachnghi-cyber/GTA5-iOS-AI-Development/actions/runs/43408725121)
  (112 Python tests, 7 C tests mỗi cấu hình), nhưng commit cũ
  `cb5bbfe6` **chưa có** policy restrained-officer này. Không tái sử
  dụng kết quả cũ để chứng minh bản vá mới.
- Đã thử fallback kiểm thử trên runner macOS nhưng runner cũng không
  được khởi tạo. Do chưa có bằng chứng execution, workflow Mac
  `gta-rp-ios-arm64-bridge.yml` đã được **khôi phục đúng Git blob
  `00fd23242e63a4bc11f88beaaebce26fab4a1439`**, là bản từng
  build ARM64 thành công, để không giữ một thay đổi CI không kiểm chứng.

**Cổng tiếp theo:** cần khôi phục khả năng cấp runner (kiểm tra GitHub
Actions status, repository Actions settings, spending/billing nếu có)
rồi chạy lại 112+ Python tests, 7 C x3, audit đủ 50 changed paths và
ARM64 builds **trên đúng head PR**; sau đó mới xét review độc lập và
merge. Không đánh dấu P0 verified hoặc tạo IPA. Sự cố cấp runner cần
người có quyền GitHub account/repository kiểm tra nếu vẫn lặp lại.
