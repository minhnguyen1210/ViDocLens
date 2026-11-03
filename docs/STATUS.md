# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G2 đạt theo hồ sơ; G3/G4/G5 chưa được xác nhận trong checkout laptop.** Phase 3 đang làm trên PC theo owner, source/checkpoints mới chưa có ở đây. Phase 4 đã được owner commit/push đến **`2fa55cd`**; nhánh **`phase5-offline`** được tạo từ đúng base này. Tooling Phase 5 CPU đã triển khai và kiểm bằng fixtures; thay đổi còn **local, chưa stage/commit/push/CI/release**.

[SOT v1.13](../SOURCE_OF_TRUTH.md) · [ADR-P5-001](DECISIONS.md) · [workflow Phase 5](PHASE5_OFFLINE_WORKFLOW.md) · [handoff PC](PHASE5_OFFLINE_HANDOFF.md). Snapshot STATUS trước lượt này giữ nguyên trong [STATUS_HISTORY](STATUS_HISTORY.md). Không suy model accuracy, calibration thật hoặc deployment từ code/tests.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Foundation/feasibility | done | G0/ADR-018; GPU/OCR pilot và locks trong hồ sơ trước |
| 1 | Data/OCR/evaluator/OOD seed | done | G1 theo AI protocol ADR-021; không là human gold/final OOD |
| 2 | Teacher/API baselines | done | G2/ADR-025; [kết quả](PHASE2_RESULTS.md), không cấp serving grant mới |
| 3 | Student/gold-only | in_progress (PC, owner-reported) | Owner hoàn tất, bảo toàn và tích hợp source/checkpoints/G3 |
| 4 | Silver/chưng cất | in_progress | Tooling laptop tại 2fa55cd; còn GPU smoke/pilot/silver/audit/core training/G4 thật |
| 5 | Verifier/cascade/full OOD | in_progress (offline CPU) | Tooling/tests local xong; real dev calibration/fallback integration/human OOD/G5 còn mở |
| 6 | API/demo/final evaluation/deploy | planned | Model API chưa ready; chờ G5 và host thật |
| 7 | Báo cáo/release/tái lập | planned | Chờ final suite/release evidence |

Phase 4 offline và điểm nối trainer được giữ ở [handoff Phase 4](PHASE4_OFFLINE_HANDOFF.md), [công cụ Phase 4](PHASE4_LOCAL_TOOLS.md). Những câu “bổ sung chưa commit” trong snapshot/handoff cũ là lịch sử; base hiện tại đã có phần bổ sung. Không thay implementation Phase 4 trong lượt này.

## Task Phase 5 và điều kiện bàn giao

| ID | Công việc | State | Kết quả / điều kiện gỡ |
|---|---|---|---|
| P5-OFF-001 | Contracts / question-only dev pool | done (local CPU) | 22 schemas mới; pin model/filter/fallback/G4/split hashes, fixture boundary; dev_calibrate cần freeze |
| P5-OFF-002 | P3-check / P3-snap | done (local CPU) | Numeric/sign/unit/occurrence guards; field cue + geometry pass/fail/unknown; unique/margin, recheck, before/after/evidence/source hash |
| P5-OFF-003 | Bundle / privileged dev evaluator | done (local CPU) | Immutable checksum/replay, missing denominator, EM/F1/ANLS/coverage, correction/harm/abstention, paired group CI |
| P5-OFF-004 | Cascade library / failure handling | done (local CPU scope) | Injected backend; local default, exact-request external gates, teacher verify, SQLite reserve/cache, circuit/remaining timeout; chưa adapter API thật |
| P5-OFF-005 | Routing grid / explicit freeze | done (local CPU) | Counterfactual dev_calibrate cost/coverage/Pareto, unknown usage null, same protocol/cache regime, replay/rationale/code-bound policy |
| P5-OFF-006 | OOD exchange / final preregistration | done (local CPU) | Blind packets, ≥20% second review, delayed same-human rule, human adjudication, overlap hashes; final manifest không mở gold/execution |
| P5-OFF-007 | Tests / docs / PC handoff | done (local) | 66 new CPU tests; SOT/ADR/status/history/changelog/workflow/handoff và schemas đồng bộ |
| P5-PC-001 | Real verifier evaluation / freeze | blocked (execution) | Owner hoàn tất G3/G4, khôi phục dữ liệu/OCR/bundles và exporter; đo dev_select/human error analysis trước chốt rule |
| P5-PC-002 | Fallback adapter / real calibration | blocked (execution) | G2 fallback profile + quyền exact request/budget/giá mới; adapter kiểm image/raw/timeout/usage; teacher-all dev_calibrate sau freeze, chọn operating point và đo live |
| P5-PC-003 | Human OOD / G5 review | blocked (execution) | Owner chuẩn bị nguồn mới có quyền, dedup/size/diversity/PII, người review/adjudicate; artifacts thật để preregister và xét G5 |

Không triển khai training, live inference, probability calibrator, annotation UI, final test evaluator hoặc serving/deploy trong lượt này. Bộ heuristic hỗ trợ taxonomy hạn chế; unknown phải abstain. P3 semantic support không chứng nhận semantic truth. Không có metrics nghiên cứu mới hoặc người review ảnh thật trên laptop.

## Kiểm tra đã chạy

Môi trường local Windows Python **3.14.0**, pytest **9.2.0**, Pydantic **2.14.2**, Ruff **0.17.3**, NumPy **2.5.4** theo venv đã kiểm kê. Không đổi dependency/ML/OCR locks, CUDA hoặc driver.

| Kiểm tra | Kết quả |
|---|---|
| Full pytest `-q -p no:cacheprovider --tb=short` | **466 passed**, 1 Starlette/httpx deprecation warning; 400 baseline + 66 Phase 5, 31,37s |
| Ruff check | Đạt |
| Ruff format --check | Đạt; **152 Python files** |
| Exported schema drift | **81 schemas match**; 59 cũ giữ nguyên + 22 mới |
| File policy / YAML | Đạt **304 candidate files**; không thay cho secret/license/content review |
| Diff whitespace | `git diff --check` đạt |
| UTF-8 / doc links | **281 text files**, không BOM/replacement character hoặc missing repo-doc target; ignored payload links không yêu cầu tồn tại |
| Scope diff | Source student/filtering/teacher/serving, root CLI và configs không đổi so HEAD |
| Historical overview | SHA256 giữ nguyên `d7d16d8d5400540c4e529cd07de92e1abf41c688584dbbf599ab5c67a6d3cf63` |
| Doctor | `inference_ready=false`, `model_not_configured`; không torch/Transformers/Paddle/NVIDIA runtime được phát hiện |
| GPU/model/real data/API/Docker | Không chạy trong lượt laptop; Docker CLI có mặt không chứng minh runtime/deploy |

[Evidence local](../artifacts/phase5/checks_offline_v1/summary.json): full pytest log, lint/format/schema/doctor, file policy, docs/scope/Git-state summary. Logs nằm trong artifacts ignored, không đưa lên Git. Full pytest chạy ngoài sandbox Windows để dùng temp/hard-link/TestClient sockets; fixture Git tests chỉ dùng temporary repo, không stage project. Không đọc `.env`, gọi paid API, tải dataset/weights hoặc bật public hosting.

## Giới hạn cần giữ khi merge

- Binding/hash/attestation không tự chứng minh G4, giá/provider license, quyền ảnh hoặc reviewer là người. PC phải đối chiếu manifests thật; không đổi fixture flag để dùng fixtures như nghiên cứu.
- Runtime mới chưa có HTTP/model adapter, không nối API/Phase 2 grant/ledger. Timeout cần backend honor I/O deadline; SQLite bảo vệ reservation race nhưng cap phụ thuộc upper-bound giá đúng. Unknown cost giữ reserve; overrun ghi đủ actual và abstain, không giấu billing.
- Routing là counterfactual từ recorded predictions; stage-time sums không là latency end-to-end. Rule score không là probability. Thay model/filter/verifier/router code sau freeze cần run/version/freeze mới.
- OOD packet không tải/nhúng ảnh hoặc suy nhãn. Review thật, near-duplicate/all-source/rights/size/diversity vẫn cần owner. Seed AI cũ không là unseen final set; cùng người delayed blind không là inter-annotator agreement.
- Preregistration luôn `execution_enabled=false`, `g5_certified=false`; không mở test CSV/gold. G5 còn cần evidence thật, Phase 6 thực hiện API/final suite/deploy.
- Git không mang theo data, OCR, model weights, grants, cache/ledger hoặc artifacts trên PC. Không copy nguyên docs laptop đè tiến độ PC.

## Git và bước tiếp theo

- Branch **`phase5-offline`**, HEAD/base **`2fa55cd066c74a77ff7ed600150dffbea5bb844e`**. Đã kiểm chưa có branch trước khi tạo. Phase 5 mới chưa có commit; index không stage.
- Phase 4 base đã owner push; [CI của base](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41606135261) từng được xác minh success ở lượt trước (Python3.11/3.12). **Chưa có CI cho Phase 5 mới.** Không release hoặc public hosting mới.
- Assistant tạo branch và sửa worktree theo yêu cầu; **không stage/commit/push/publish, đổi Git identity hoặc thêm author/co-author**. Owner tự review, commit/push nhánh khi muốn; tránh bỏ sót file mới untracked.
- PC: lưu/backup Phase 3 → nhánh tích hợp → merge Phase 4 đến 2fa55cd → merge Phase 5 → hợp nhất shared docs/exporter và regenerate schemas → CPU checks → nối exporter/backend và thực hiện real gates theo [handoff](PHASE5_OFFLINE_HANDOFF.md). Chưa thể bảo đảm merge sạch khi chưa đọc diff PC.
