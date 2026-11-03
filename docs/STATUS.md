# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G2 đạt theo hồ sơ; G3/G4 chưa được xác nhận trong checkout laptop.** Chủ dự án đang làm Phase 3 trên PC, source chưa có ở đây. `phase4-offline` có bản đầu tại **`3ae2c4f`** do owner commit/push; phần bổ sung ADR-P4-002 đang **local, chưa stage/commit/push**. Đã hoàn thiện bốn nhóm tooling còn thiếu có thể kiểm CPU: local teacher orchestration, dev threshold grid, human audit workflow và core result comparison. Chưa chạy Qwen GPU, sinh silver thật, chọn ngưỡng thật, human review ảnh thật hoặc train P1/P2.

[SOT v1.12](../SOURCE_OF_TRUTH.md) · [ADR-P4-001/002](DECISIONS.md) · [workflow F0/F1](PHASE4_OFFLINE_WORKFLOW.md) · [công cụ bổ sung](PHASE4_LOCAL_TOOLS.md) · [bàn giao PC](PHASE4_OFFLINE_HANDOFF.md). Nhật ký cũ giữ trong [STATUS_HISTORY](STATUS_HISTORY.md), gồm snapshot offline v1 trước bổ sung. Code done, CPU checks, commit, push, CI và release là các trạng thái riêng.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Foundation/feasibility | done | G0/ADR-018; GPU/OCR pilot và locks trong hồ sơ trước |
| 1 | Data/OCR/evaluator/OOD seed | done | G1 theo AI protocol ADR-021; [kết quả](PHASE1_RESULTS.md), không là human gold/final OOD |
| 2 | Teacher/API baselines | done | G2/ADR-025; [kết quả](PHASE2_RESULTS.md), code d13360e |
| 3 | Student/gold-only | in_progress (PC, owner-reported) | Chưa có source/checkpoint/G3 mới trên laptop; owner hoàn tất và tích hợp |
| 4 | Silver/chưng cất | in_progress | Tooling CPU đã có; Qwen adapter chưa smoke; còn real pilot/data/audit/training/G4 |
| 5 | Verifier/cascade/full OOD | planned | Chờ student bundles/calibration/validation |
| 6 | API/demo/final evaluation/deploy | planned | Inference chưa ready, chưa deploy |
| 7 | Báo cáo/release/tái lập | planned | Chờ final suite và release evidence |

## Task và bàn giao local

| ID | Công việc | State | Kết quả / điều kiện gỡ |
|---|---|---|---|
| P4-OFF-001 | Contracts/pool/local result exchange | done (code) | Bản đầu đã owner commit/push; frozen G10 boundaries không đổi |
| P4-OFF-002 | F0/F1/bundles/replay | done (code) | Numeric/raw/occurrence guards; semantic_check unknown; bổ sung atomic publish |
| P4-OFF-003 | Audit/nine experiment selections | done (code) | Exact-batch approval, P1-full/P1-size/P2 × 3 seeds; chưa training |
| P4-OFF-004 | Tests/docs/handoff | done (local) | SOT/ADR/status/history/runbooks/schema cập nhật; bổ sung chưa commit |
| P4-OFF-005 | Local teacher orchestration + adapter code | done (local CPU scope) | Snapshot/config/plan, grouped question-only requests, parser, raw transactional attempts, retry/resume; lazy Qwen GPU adapter **chưa smoke** |
| P4-OFF-006 | Dev threshold grid/selection | done (local code) | Đủ 4 thresholds trên cùng inputs; replay/hash checks, rationale/freeze; không tự chọn ngưỡng thật |
| P4-OFF-007 | Human audit workflow | done (local code) | Seeded four-stratum blind JSON packet/template/import; chưa người review ảnh thật, chưa có annotation UI |
| P4-OFF-008 | Results/fair comparison | done (local code) | 12-result contract, same data/profile/updates/exposure checks, missing denominator, seed mean/std, paired group bootstrap/CSV/slices |
| P4-PC-001 | Local teacher smoke/pilot/silver thật | blocked (execution) | Owner/PC khôi phục model/data, xác minh revision/license/quyền/VRAM/quality, exact-plan grant; mở quality gate trước silver generation |
| P4-PC-002 | Training integration/core matrix | blocked (execution) | Owner hoàn tất G3/source PC; nối selections/raw targets + per-qid exposure/result exporter; dev freeze/holdout audit rồi train/evaluate cùng budget/3 seeds |

F2/F3, label correction và semantic-constrained filter vẫn là extension/phase sau trong SOT; không đưa vào core bằng việc viết code laptop. Không thể hoàn tất G4 chỉ với mock backend hoặc fabricated training results.

## Kiểm tra đã chạy

Windows Python **3.14.0**, `.venv` CPU cục bộ; pytest9.2.0, pydantic2.14.2, Ruff0.17.3, NumPy2.5.4. Không cài torch/Transformers/Paddle, không sửa CUDA/ML/OCR locks. Không coi đây là compatibility lock GPU.

| Kiểm tra | Kết quả |
|---|---|
| Full pytest `-q -p no:cacheprovider --tb=short` | **400 passed**, 1 Starlette/httpx deprecation warning; 46 cases bổ sung trên 354 cũ |
| CLI sau khi bổ sung command `config` | **4 passed**; config/plan không import ML và workflow grid→freeze→review→comparison |
| Ruff check / format --check | Đạt; **132 Python files** formatted |
| Schema drift | **59 schemas match** (13 mới) |
| File policy/YAML | Đạt **262 candidate files**; không là secret/license review |
| Diff whitespace | `git diff --check` đạt |
| UTF-8 / links | **234 text files**, không BOM/replacement character hoặc missing repo-doc target; ignored data/artifact paths loại khỏi link existence check |
| Historical overview | Giữ nguyên SHA256 `d7d16d8d5400540c4e529cd07de92e1abf41c688584dbbf599ab5c67a6d3cf63` |
| Doctor | `inference_ready=false`, `model_not_configured`; không torch/Transformers/Paddle/NVIDIA runtime được phát hiện |
| GPU/model/data/training/Docker | Không chạy trong lượt laptop; Docker CLI có mặt không chứng minh runtime/deploy |

[Evidence local](../artifacts/phase4/checks_offline_v2/summary.json) lưu command logs và phạm vi, nằm trong artifacts ignored. Full pytest log lưu output tail của session đã hoàn tất; CLI recheck riêng sau thay đổi nhỏ. Tests dùng synthetic fixtures/MockTransport; không gọi paid provider hoặc đọc `.env`. Chạy ngoài sandbox Windows cho temp/hard-link và API TestClient sockets. Test Git workflow chỉ dùng temporary fixture repo, không stage project.

## Quyền và hạn chế

- Phase 2 giữ kết quả lịch sử: 511 requests/150 ảnh, cost theo usage **6,080008/20 USD**, replay không calls/spend mới; không tái thực thi trong lượt này. API training export/Batch upload/serving external vẫn disabled.
- Runner local chỉ dùng snapshot có sẵn, không download/public hosting. Snapshot và owner grants là attestation/hash, không tự chứng minh license/nguồn revision/quality. Grant generation và approval training tách biệt; holdout cần freeze. Model 4B/GPU adapter chưa được xác minh trên host thật.
- Grid/human/comparison đã có code, chưa có metrics nghiên cứu mới. Blind review cần người xem ảnh; fixture flag không được đổi thành evidence thật. Fairness checks kiểm manifest, không chứng minh trainer đã làm đúng. Missing/error/abstain vẫn ở denominator, bootstrap không tự bao gồm training variance.
- Test/OOD/dev_calibrate không mở trong Phase 4 workflow; gold chỉ trong evaluator. F1 không sửa raw label hoặc chứng nhận semantic truth. Data/cache/grants/weights/artifacts không đi cùng Git checkout.

## Git và bước tiếp theo

- Branch hiện tại **`phase4-offline`**, base Phase2 **`d13360e`**, HEAD **`3ae2c4f90965e6c4fb9c4cc42880a7a19a3bfff2`**. Bản đầu đã owner push; [CI của đúng commit này](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41601272656) từng được xác minh success (Python3.11/3.12). Đây **không** là CI của phần bổ sung chưa commit.
- Lượt này assistant chỉ sửa worktree/kiểm tra: **không stage, commit, push, publish, đổi identity hoặc thêm author/co-author**. Không có release mới. Owner tự review/stage/commit/push bổ sung rồi kiểm CI của commit mới.
- Không sửa student/student configs, ML/OCR locks, core CLI, serving, Phase 2 provider/ledger hoặc PROJECT_OVERVIEW. Shared docs/exporter/schema cần hợp nhất nội dung khi về PC; không copy nguyên STATUS/SOT laptop đè tiến độ PC.
- Trên PC: bảo toàn Phase3 code/checkpoints → merge toàn bộ commits Phase4 → chạy CPU/schema checks → nối trainer/result exporter và smoke GPU → local teacher quality pilot/quyền → silver thật, dev grid/freeze, holdout human audit → L2/P1/P2 ba seed và comparison → xét G4 bằng evidence. Chi tiết file ownership/commands ở [handoff](PHASE4_OFFLINE_HANDOFF.md).
