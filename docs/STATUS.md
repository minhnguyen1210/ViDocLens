# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0, G1 và G2 đã đạt. Phase 2 hoàn tất local theo SOT v1.10.** Key trong `.env` đã dùng thành công; pilot và A1/A2/A3/A5 chạy đủ **511 requests / 150 ảnh duy nhất**, tổng chi phí usage × price card **6,080008 USD trong cap 20 USD**. Replay 511/511 cache hits không thêm API calls/spend. [Báo cáo đầy đủ](PHASE2_RESULTS.md) · [gate local](../artifacts/phase2/final_v1/report.json).

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định Git/task; [history](STATUS_HISTORY.md) giữ các mốc trước; [ADR](DECISIONS.md) ghi quyết định. Không suy phần trăm toàn dự án từ số phase/tests. Hoàn tất Phase 2 không đồng nghĩa đã train student hoặc deploy sản phẩm.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu/môi trường | **done** | G0: GPU/OCR pilot thật, locks dựng lại; [runbook](PHASE0_ENVIRONMENT.md), ADR-018 |
| 1 | Data, OCR, evaluator, OOD khởi đầu | **done** | G1 theo AI protocol ADR-021; [báo cáo](PHASE1_RESULTS.md), [gate local](../artifacts/phase1/g1_ai_gate_v2.json) |
| 2 | Teacher, ledger/cache và API baselines | **done** | G2: live pilot/baselines, metric/cost, cache replay, role freeze; ADR-025 |
| 3 | Student training / gold-only | planned | **Bước kế tiếp:** training smoke/save/reload/resume trên 12 GB, L1/L2 dev baselines |
| 4 | Silver và chưng cất | planned | Cần G3 và gate local label teacher; output API hiện không được dùng train |
| 5 | Verifier/cascade, calibration, full OOD | planned | Cần model bundles, routing calibration và full OOD validation |
| 6 | API/demo thật, final eval/deploy | planned | Cần G5, runtime/host và release gates |
| 7 | Báo cáo, release/tái lập | planned | Cần final suite, reproducibility và release evidence |

G1 bằng AI không là human gold/final OOD. Serving vẫn `inference_ready=false`; teacher CLI không đồng nghĩa backend sản phẩm đã triển khai.

## Hàng đợi

| ID | Công việc | State | Kết quả / điều kiện |
|---|---|---|---|
| REPO-001/002 | Workflow và push đầu tiên | done | Chủ dự án tự push; history giữ evidence/CI trước Phase 2 |
| P2-001 | Contract, permissions, prompt, model/price candidates | **done (local)** | Pydantic/schema; no-gold input; scope theo exact request keys; ADR-023 |
| P2-002 | Provider, cache, budget, retry, Batch, evaluator/CLI | **done (local)** | Offline cases đạt; Responses thật đã chạy; Batch upload chưa thuộc quyền được cấp |
| P2-004 | OCR dev và manifest pilot/baselines | **done** | OCR 100/100; 50 train + 100 dev, 511 groups; plan tái tạo trùng hashes |
| P2-003 | Live pilot/baselines, replay, metric và role freeze | **done** | 9/9 criteria của [G2 report](../artifacts/phase2/final_v1/report.json) đạt; cấu hình A3 khóa theo policy định trước |
| P3-001 | Student training feasibility | planned | Dùng stack ML đã khóa; loss mask/gradient, train smoke, save/reload/resume và số đo VRAM trước full L2 |

## Kết quả Phase 2

Pilot **50 ảnh / 344 QA / 59 groups** đều hợp lệ. Mỗi baseline dùng đúng **100 dev components / 666 QA / 113 groups**; không mở test/OOD/dev_calibrate/audit để chọn teacher. Gold dev chỉ evaluator đọc sau khi đủ predictions.

| Arm | Input/model | Strict EM | Token F1 | ANLS | USD |
|---|---|---:|---:|---:|---:|
| A1 | GPT-5.4, OCR text | 57,66% | 68,87% | 80,69% | 1,214753 |
| A2 | GPT-5.4, ảnh | 73,72% | 85,54% | 89,10% | 1,677962 |
| A3 | GPT-5.4, ảnh + OCR | **76,28%** | **87,53%** | **90,01%** | 1,750404 |
| A5 | GPT-5.4 mini, ảnh + OCR | 70,27% | 81,26% | 86,65% | 0,520879 |

Pilot tốn thêm 0,916010 USD. Đây là chi phí theo usage và price cards, chưa đối soát invoice tài khoản. Một A5 schema error chứa **6 QA** được tính lỗi trong toàn bộ 666 QA, không bỏ mẫu hoặc retry để tăng điểm. Null/error/missing đều giữ denominator. Các metric là dev subset, không phải final test.

**Benchmark/fallback chọn A3**: `gpt-5.4-2026-03-05`, image+OCR, prompt `teacher_vqa_v2`, detail high, reasoning none, output cap 4096, store false. A3−A2 = +2,55pp EM, paired 95% CI [+0,43; +4,75]pp. A5 rẻ hơn nhưng giảm 6,01pp, vượt ngưỡng fallback 2pp đã khóa. Fallback serving vẫn disabled. [Role freeze](../artifacts/phase2/final_v1/role_freeze.json), ADR-025.

## Quyền và điều kiện cho phase sau

| Mục | Hiện trạng | Điều kiện tiếp theo |
|---|---|---|
| API budget | 6,080008/20 USD; 511 attempts; reserved/uncertain=0 | Giữ ledger; số dư không mở thêm phạm vi benchmark |
| External processing | Grant owner đã xác nhận data/terms/retention, bind đúng archive/split/511 keys | Không tự mở sang test/OOD, dữ liệu mới hoặc online serving |
| Credential | `.env` đã dùng thành công, ignored; runtime không log key | `--env-file .env` sau permission gates; file không đi vào Git |
| Batch / API training export | **Chưa cấp**, flags false | Không upload Batch hoặc dùng evaluation cache train student |
| Label teacher | Strategy local open-weight ADR-014; Qwen3-VL-4B còn candidate | License/revision/VRAM/quality pilot phải đạt trước Phase 4; nếu fail giữ gold-only |
| GitHub/deploy | Thay đổi Phase 2 ở local; CI mới chưa chạy; serving chưa ready | Chủ dự án tự commit/push; deployment thuộc Phase 6 |

Template permission trong Git vẫn deny/cap0; approval thật nằm trong `artifacts/phase2/approval.json` bị ignore. Không có blocker G2 còn mở; điều kiện label/serving thuộc các phase sau theo SOT, không bị coi đã đạt.

## Kiểm tra local mới nhất

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python 3.14.9 pytest | **289 passed, 7 skipped**; NumPy cases chạy đủ WSL |
| WSL ML-repro Python 3.11.14 pytest | **296 passed** |
| Teacher / credential / finalization fixtures | 61 / 8 / 4 cases trong suite, không thay thế live evidence |
| Ruff check / format | Đạt; **105 Python files** |
| Schema drift | **36 schemas match** |
| File policy / YAML | Đạt **212 candidates** tại lượt kiểm; không là secret/content/license scan |
| Docs / diff | UTF-8, liên kết local và `git diff --check` đạt; role config khớp report, plan tái tạo sau freeze vẫn trùng hash |
| Live cache replay | **511/511 hits**, result hashes trùng; 0 calls/spend mới; không cần credential |
| Doctor | `inference_ready=false`, `model_not_configured` đúng hiện trạng |
| GitHub CI | CI cũ tại 03ac245 đã đạt ([run](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41479278954)); **chưa có CI cho Phase 2** |
| GPU/Docker | Không chạy thêm GPU/student/Docker tests; OCR CPU dùng stack đã khóa |

[Evidence checks](../artifacts/phase2/checks_live_v2/summary.json). Warning Starlette/httpx đã biết còn tồn tại. PowerShell runner đã kiểm AST syntax nhưng chưa chạy interactive; campaign này dùng CLI với `.env`. Không cài dependency, đổi driver, tải thêm model/dataset, reboot hoặc mở hosting.

## Bàn giao

- Local branch `codex/phase2-teacher-pipeline`, base `0226b94`; **không stage/commit/push, không thay remote**. GitHub CI/release là trạng thái riêng.
- SOT v1.10, ADR-025, role config, README/CHANGELOG, access register, workflow/results và budget notes khớp kết quả thực. G0/G1 evidence, frozen split, prompt/plan/policy và `PROJECT_OVERVIEW.md` giữ nguyên.
- Artifacts local bị ignore: [plan](../artifacts/phase2/api_plan_v1/manifest.json), [G2 report](../artifacts/phase2/final_v1/report.json), [role freeze](../artifacts/phase2/final_v1/role_freeze.json), [checks](../artifacts/phase2/checks_live_v2/summary.json). Report có hashes live/replay manifests; usage/raw/parsed giữ trong cache/ledger.
- Việc kế tiếp là **Phase 3 / P3-001**, sau đó L1 và L2-k10 trên dev theo SOT. G2 hoàn tất không mở quyền API training export và không tự bắt đầu sinh silver.
