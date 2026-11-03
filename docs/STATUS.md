# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G2 đã đạt theo hồ sơ; G3/G4 chưa được xác nhận trong checkout laptop.** Chủ dự án cho biết Phase 3 đang dở trên PC, chưa push. Nhánh **`phase4-offline` từ `d13360e`** đã triển khai phần CPU Phase 4 và kiểm chứng bằng fixtures. Chưa sinh silver thật hoặc train P1/P2. [Bàn giao PC/merge](PHASE4_OFFLINE_HANDOFF.md) · [workflow](PHASE4_OFFLINE_WORKFLOW.md).

[SOT v1.11](../SOURCE_OF_TRUTH.md), [ADR-P4-001](DECISIONS.md), [CONTRIBUTING](../CONTRIBUTING.md) quy định phạm vi/gates. [STATUS_HISTORY](STATUS_HISTORY.md) giữ nguyên mốc bàn giao Phase 2 và các kết quả trước. Không suy phần trăm dự án từ tests hoặc số module.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng và feasibility | done | G0/ADR-018, GPU/OCR pilot/lock ở hồ sơ trước |
| 1 | Data, OCR, evaluator, OOD seed | done | G1 theo AI protocol ADR-021; [kết quả](PHASE1_RESULTS.md), không phải human gold/final OOD |
| 2 | Teacher/API baselines | done | G2/ADR-025; [kết quả](PHASE2_RESULTS.md), code tại d13360e |
| 3 | Student/gold-only | in_progress (PC, owner-reported) | Code chưa có trên laptop; cần hoàn tất G3 và đối chiếu trainer khi tích hợp |
| 4 | Silver/chưng cất | in_progress (offline CPU) | Contracts/F0/F1/audit/selections local đạt tests; chưa local teacher/silver thật/training/G4 |
| 5 | Verifier/cascade/full OOD | planned | Chờ student bundles, calibration và validation |
| 6 | API/demo/final evaluation/deploy | planned | Serving vẫn chưa có model, chưa deploy |
| 7 | Báo cáo/release/tái lập | planned | Chờ final suite và release evidence |

## Hàng đợi và bàn giao local

| ID | Công việc | State | Kết quả / điều kiện gỡ |
|---|---|---|---|
| P2-001/002/003/004 | Teacher, OCR dev, pilot/baselines, replay/role freeze | done | Bảo toàn kết quả Phase 2, không gọi lại API |
| P3-001 và L1/L2 | Training feasibility/gold-only | in_progress (PC) | Owner hoàn tất; chưa kiểm tra code/checkpoint/G3 trên laptop |
| P4-OFF-001 | Silver contracts, pool builder, local result exchange | done (local) | 10 schema mới; no-gold/frozen split boundaries; adapter generation local chưa có |
| P4-OFF-002 | F0/F1, evidence/reasons, bundles/replay | done (local) | CPU fixtures đạt; thresholds vẫn chưa calibrated, semantic_check unknown |
| P4-OFF-003 | Audit/selection CLI | done (local) | Exact-batch approvals, matched strata/counts, 3 arms × 3 seeds; chưa train |
| P4-OFF-004 | Tests/docs/PC handoff | done (local) | 58 tests mới, full suite 354 passed; không commit/push |
| P4-PC-001 | Local teacher pilot và silver thật | blocked (execution) | Owner/PC: khôi phục artifacts, kiểm license/data/revision/VRAM/quality; đạt gate trước generation |
| P4-PC-002 | Training integration và core matrix | blocked (execution) | Hoàn tất G3, review contract adapter, freeze filter trên dev, audit holdout và train cùng budget/3 seeds |

## Kiểm tra mới nhất — laptop CPU

Môi trường mới **Windows Python 3.14.0**, `.venv` riêng: pydantic 2.14.2, pytest 9.2.0, Ruff 0.17.3, NumPy 2.5.4. Cài extras core/data/teacher/serve/dev; không đổi ML/OCR locks, không cài torch/transformers/Paddle vào venv CPU này. Đây không là lock tương thích GPU.

| Kiểm tra | Kết quả đã chạy |
|---|---|
| Full pytest `-q -p no:cacheprovider --tb=short` | **354 passed**, 1 Starlette/httpx deprecation warning |
| Phase 4 coverage | **58 cases mới**, synthetic archive/teacher/OCR và unit boundary tests; không là metric chất lượng |
| Ruff check / format --check | Đạt toàn repo tại lượt kiểm |
| Schema drift | **46 schemas match** |
| File policy / YAML | Đạt **235 candidate files** tại lượt kiểm; không là secret/license review |
| Git diff --check | Đạt |
| Docs / UTF-8 / links | Đạt trên 235 files; không có link nội bộ thiếu ngoài artifacts/data/cache/reports bị ignore; PROJECT_OVERVIEW giữ nguyên SHA256 |
| Doctor | `inference_ready=false`, `model_not_configured`; torch/transformers/PaddleOCR không có trong venv CPU |
| GPU, local teacher, training, Docker | Không chạy trong lượt laptop |
| GitHub CI/release | Không kiểm/chạy mới; không suy từ CPU checks thành CI đạt |

[Logs/summary thực](../artifacts/phase4/checks_offline_v1/summary.json) nằm trong artifacts ignored, không đi cùng Git. Test suite chạy ngoài sandbox Windows vì các lượt audit trước bị chặn socket/temp/hard link; dùng synthetic fixtures/MockTransport, không dùng `.env` thật hoặc gọi provider. Một workflow test Git chỉ stage trong temporary fixture repo riêng, không stage project.

## Quyền và kết quả nghiên cứu giữ nguyên

- Phase 2 ghi nhận 511 requests/150 ảnh, cost usage × price card **6,080008/20 USD**, replay 511/511 không calls/spend mới. Benchmark/fallback A3 có dev EM 76,28%; chi tiết và giới hạn ở [PHASE2_RESULTS](PHASE2_RESULTS.md). Không tái tính từ raw artifacts trong lượt này.
- API training export/Batch upload/online serving vẫn không được mở. Không dùng evaluation cache làm training labels. Nhánh silver dùng local open-weight sau gate, 4B chưa được chứng nhận bằng code CPU.
- Approval local Phase 4 phải bind đúng pool/batch và evidence. Fixtures không được dùng làm training thật; freeze synthetic không mở real batch. Gold audit tách filter; test/OOD/dev_calibrate không mở.
- Chưa có real-data filter accuracy/retention, student gain, human audit hoặc G4 evidence mới. `semantic_check=unknown`; OCR support không là semantic truth.

## Git và tích hợp PC

- Đã kiểm tra branch chưa tồn tại trước khi tạo **`phase4-offline`**, base/HEAD **`d13360e`**. Chỉ tạo/switch nhánh local; không đổi remote/Git identity.
- Thay đổi còn trong working tree: **không stage, không commit, không push, không author/co-author mới**. Owner tự review/commit/chuyển code. Chỉ merge nhánh chưa commit sẽ không mang theo code mới.
- Không sửa student, student configs, ML/OCR locks, core CLI, serving hoặc provider/ledger Phase 2. Các file chung cần hợp nhất thủ công với PC được liệt kê trong [handoff](PHASE4_OFFLINE_HANDOFF.md).
- Khi về PC: bảo toàn/lưu Phase 3 → tích hợp code Phase 4 → kiểm schemas/tests → nối trainer và smoke trên GPU → pilot teacher/calibrate/audit/train core matrix khi đủ gates. Không ghi đè toàn bộ STATUS/SOT của PC bằng bản laptop.
