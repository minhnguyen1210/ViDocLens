# Trạng thái ViDocLens

Cập nhật: **05/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G4 đã đạt local; Phase 4 hoàn tất theo SOT v1.14 / ADR-P4-003.** [Báo cáo Phase 4](PHASE4_RESULTS.md) · [G4 evidence](../artifacts/phase4/g4_report_reviewed_v2.json). Phase 5–7 chưa triển khai; API serving vẫn inference_not_ready.

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định workflow/Git; [history](STATUS_HISTORY.md) giữ lịch sử; [ADR](DECISIONS.md) ghi quyết định. Không suy phần trăm toàn dự án từ số phase/tests. Local done khác commit, push, CI và release.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu/môi trường | **done** | G0: GPU/OCR thật, hash locks và dựng lại; ADR-018 |
| 1 | Data, OCR, evaluator, OOD khởi đầu | **done** | G1 theo AI protocol ADR-021; [báo cáo](PHASE1_RESULTS.md), không là human gold/final OOD |
| 2 | Teacher, ledger/cache và API baselines | **done** | G2 live evidence; [báo cáo](PHASE2_RESULTS.md), ADR-025 |
| 3 | Student training / gold-only | **done (local)** | G3 **9/9** tiêu chí đạt; smoke/resume/reload, L1 + hai checkpoint × ba seed, raw metric replay và continuation provenance |
| 4 | Silver và chưng cất | **done (local)** | G4 **10/10 tiêu chí** pass; 9 matched runs, 12 results, human review thật và final replay; [báo cáo](PHASE4_RESULTS.md) · [gate](../artifacts/phase4/g4_report_reviewed_v2.json) |
| 5 | Verifier/cascade, calibration, full OOD | planned | Cần G4 model bundles và calibration/full OOD |
| 6 | API/demo thật, final eval/deploy | planned | Cần G5, runtime/host và release gates |
| 7 | Báo cáo, release/tái lập | planned | Cần final suite/reproducibility/release evidence |

## Công việc Phase 3 đã hoàn thành

| ID | Công việc | State | Evidence |
|---|---|---|---|
| P3-001 | Training feasibility, loss mask, save/load/resume | **done** | Preflight toàn G10/dev; smoke52 và resume50→52; adapter diff0, greedy/fresh-process reload khớp |
| P3-002 | L1/L2-k10 ba seed và selection | **done** | Ba seed17/42/2026 train đủ191 updates/3.053 unique QA; L1 + 6 dev runs đủ666 QA mỗi run; chọn step191 cho cả ba seed |
| P3-003 | Continuation, final audit và bàn giao | **done** | Contract/schema,20 continuation cases; parent/partial giữ nguyên; metric replay; mean/std/paired CI/compute, model card và docs |

Không train lại sau pause. Seed2026/step96 cũ có238/666 predictions được giữ riêng; chạy mới đủ666 ở `continuation_v1`, rồi step191. Parent `campaign_v1` vẫn `complete=false`/SIGINT exit-2; [manifest continuation](../artifacts/phase3/continuation_manifest_v1.json) bind10 completed runs và1 partial cũ. G3 đạt trên evidence hoàn chỉnh, không sửa lịch sử thành công giả.

## Kết quả dev Phase 3

Tập dev cố định100 components/666 QA, numeric379 QA. Chỉ dùng dev_select, không test/OOD/audit/dev_calibrate; training chỉ G10 gold, không API output.

| Arm được chọn | Step | Strict EM | Token F1 | ANLS | Numeric EM |
|---|---:|---:|---:|---:|---:|
| L1 zero-shot | — | 34,38% | 41,96% | 54,47% | 47,49% |
| L2 seed17 | 191 | 45.65% | 53.18% | 64.02% | 61.21% |
| L2 seed42 | 191 | 45.80% | 53.17% | 63.67% | 61.74% |
| L2 seed2026 | 191 | 46.55% | 54.21% | 64.24% | 62.01% |
| **L2 mean (3 seeds)** | — | **46.00%** | **53.52%** | **63.98%** | **61.65%** |

EM sample SD **0.483 điểm %**. Mean L2−L1 **+11.612 điểm %**, paired95% CI **[8.736; 14.467]** (2.000 group resamples, seed42). Bootstrap không bao gồm training variance; đây là dev selection, không phải final test hoặc ensemble.

Training peak reserved3,3008GiB trên RTX3060 12GB; max train sequence462/target105,0 truncate. Ba lượt train tổng108,10 phút cho updates; 12 matched runs ước tính7,21 training GPU-hours, chưa gồm label/OCR/eval/load/save/retry. [Chi tiết compute](PHASE0_BUDGET.md). Context2048 là ceiling, chưa stress-test worst-case mọi chuỗi2048.

## Kiểm tra local mới nhất — tích hợp Phase4

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python3.14.9 pytest | **475 passed, 10 skipped** tại integration v6 (trước final WSL run) |
| WSL ML-repro Python3.11.14 pytest | **485 passed**, CPU suite, CUDA_VISIBLE_DEVICES rỗng; final run v1 |
| Ruff check / format | Final WSL: đạt; 188 Python files |
| Schema drift | Final WSL: **71 schemas match** |
| File policy / YAML | Final WSL: đạt 334 candidates; không là secret/license scanner |
| Preservation | **1.523/1.523 files** khớp SHA/size: toàn artifacts Phase3, frozen split, PROJECT_OVERVIEW |
| Doctor / serving | `inference_ready=false`, `model_not_configured`; G4 không tự tích hợp API |
| Git index | Rỗng; không stage/commit/push |
| GitHub CI | main0060c32 run41628624494 đã success tại lần audit; chưa có CI cho working tree hiện tại |

[Windows integration v6](../artifacts/phase4/checks_integration_windows_v6/checks.json) ·
[final WSL v1](../artifacts/phase4/checks_final_wsl_v1/checks.json) bind source/config/schema hashes.
Final WSL pytest có một Starlette/httpx deprecation warning. CPU checks tách biệt với bằng chứng
GPU/training; kết quả execution và G4 được báo riêng bên dưới.

## Quyền và ranh giới còn hiệu lực

- Phase2:511 requests/150 ảnh,6,080008 USD theo usage trong cap20 USD; replay511/511 cache hits không thêm calls/spend. [G2 report](../artifacts/phase2/final_v1/report.json). Không phát sinh API spend ở Phase3; số dư không mở thêm phạm vi benchmark.
- Grant external bind đúng data/split/request keys Phase2; không tự mở test/OOD, dữ liệu mới hoặc serving. API output training export và Batch upload vẫn chưa cấp.
- Phase 4 local open-weight hoàn tất theo grants/pools đã bind; không dùng evaluation cache API để train. G4 không mở API training export, serving hoặc public hosting.
- G1 AI references giữ provenance; không coi là human gold/final OOD. Base model pretraining contamination chưa audit độc lập.

## Phase 4 — hoàn tất local

| ID | Công việc | State | Bằng chứng / điều kiện hoàn tất |
|---|---|---|---|
| P4-001 | Tích hợp offline trên main G3 | **done local** | Preservation 1.523/1.523 files; Phase 3 giữ nguyên |
| P4-002 | Teacher local license/snapshot/pilot | **done local** | Raw single-QA đạt pilot gate; 666 QA, EM36,49%, coverage96,25%; snapshot/replay đã bind |
| P4-003 | Full OCR / silver / filter freeze | **done local** | Train_fit 27.774 QA, OCR 4.073 ảnh, audit 3.454 QA; frozen filter và human review 100/100 replay pass |
| P4-004 | Mixed sampler/trainer/comparison | **done local** | 9 runs × 191 updates; step96/191 predictions; 12-result exporter/comparison replay pass |
| P4-005 | Holdout/human review/G4 | **done local** | G4 pass 10/10; [report](PHASE4_RESULTS.md), [checks](../artifacts/phase4/checks_final_wsl_v1/checks.json) |

Hai lỗi được giữ lịch sử: pilot_v1 bị dừng khi Transformers ghi đè greedy bằng sampling;
pilot_v2 khóa kwargs trực tiếp và có regression CPU trên stack thật. Parser legacy có thể
loại cả nhóm vì1item sai schema; `strict_item_reparse_v1` là view có provenance riêng,
không sửa raw/model output/cache, giữ valid siblings và fail đúng qid. Áp cùng policy cho
pilot/grid/audit/train trước quality metrics; không đọc gold để chọn parser.

## Pilot teacher và filter dev đã đo

Cùng cohort Phase 3: 666 QA/100 ảnh; cả hai cache được replay không gọi model thêm.
Raw giữ 641 answered, 23 unanswerable và 2 incomplete; không có runtime inference error.

| Candidate | Answered coverage | Strict EM | ANLS | Generation time | Gate |
|---|---:|---:|---:|---:|---|
| Structured + strict-item | 89,64% | 35,14% | 55,12% | 57,99 phút | Fail coverage 90% |
| **Raw single-QA** | **96,25%** | **36,49%** | **61,34%** | **10,83 phút** | **Pass 5/5** |

Raw EM = 243/666 so với L1 = 229/666. Đây là gate khả thi để chạy thí nghiệm;
teacher chưa vượt L2 mean 46,00%. GPU peak reserved raw 4.599.054.336 bytes;
time chỉ generation trên host dùng chung, không là latency serving hoặc end-to-end.
[Selection](../artifacts/phase4/teacher_selection_v1/selection.json) giữ cả candidate
thất bại; [raw report](../artifacts/phase4/teacher_selection_v1/raw_report.json) bind
plan/source/cohort/cache/G3. Không hạ ngưỡng sau khi thấy kết quả.

F1 chọn `tau-000` theo rule đã đăng ký: precision cao nhất, recall không thấp hơn
exact-only. Trên dev: 111/641 nhãn hợp lệ được giữ (**17,32%**), 78 nhãn đúng;
precision **70,27%**, recall **32,10%**, false accept 33 và false reject 165.
[Grid đầy đủ](../artifacts/phase4/execution_v1/grid/grid.json) và
[config đã freeze](../artifacts/phase4/execution_v1/labeling/freeze/config.json).
Các số dev này không đại diện chất lượng holdout; xem outcome holdout đo riêng bên dưới. Không chỉnh rule theo audit.

## Holdout, human review và G4 đã hoàn tất

Trên 3.454 QA audit, teacher có **3.315 answered, 120 unanswerable, 19 incomplete**;
OCR hoàn tất 504/504 ảnh với 22.387 spans. F1 freeze giữ 588/3.315 eligible:
precision **67,18%**, recall **32,54%**, retention **17,74%**, false accept **193**,
false reject **819** (1.214 correct eligible/395 correct kept). Đây là outcome audit;
không dùng để tune lại filter. OCR confidence bins chỉ là proxy của engine, không là
human quality hoặc chứng nhận đáp án đúng nghĩa trường.

Reviewer thật đã xem ảnh và điền đủ **100/100 judgments** (25 mỗi stratum) cùng
attestation; replay qua [human review summary](../artifacts/phase4/g4_report_reviewed_v2_human_review.json)
đạt. G4 report pass **10/10**. [Báo cáo kết quả](PHASE4_RESULTS.md) chứa metrics,
hạn chế và evidence chi tiết.

Worker Phase 4 đã dừng sau khi sinh nhãn, OCR, comparison và G4 hoàn tất. Worker cache
phụ v1 bị OOM sau 444/2.037 ảnh; partial/cache/logs được giữ nguyên. OCR recovery v2
và run chính đã hoàn tất pool đúng identity; các attempt dở không được tính thành full
run. [Recovery v2](../artifacts/phase4/ocr_cache_recovery_v2.json) và
[execution runbook](PHASE4_EXECUTION.md) lưu provenance.

## Bàn giao và bước tiếp theo

- **Phase 4:** complete local; G4 pass 10/10. [Báo cáo](PHASE4_RESULTS.md) · [gate](../artifacts/phase4/g4_report_reviewed_v2.json) · [comparison](../artifacts/phase4/execution_v1/comparison/comparison.json) · [final checks](../artifacts/phase4/checks_final_wsl_v1/checks.json).
- **Campaign recovery:** 9 matched runs, 12-result export và comparison complete. Parent campaign.json vẫn complete=false vì SIGINT có chủ đích sau lượt6; không sửa lịch sử. Run7 cũ tại75/191 được giữ với SHA manifest; run7 mới chạy từ step0 rồi hoàn tất cùng run8–9. [Continuation state](../artifacts/phase4/recovery_after_run6_v1/continuation.json).
- **Checks:** WSL CPU suite 485 passed; Ruff, format, doctor,71 schemas và repository policy pass. Serving vẫn model_not_configured/inference_ready=false; không có CI GitHub mới, Docker/release chưa xác minh.
- **Git:** working tree chứa thay đổi Phase4 để review; Git index trống. Không stage, commit hoặc push. Chủ dự án review rồi tự commit/push thủ công.
- **Bước tiếp:** không còn bước kỹ thuật Phase4. Phase5 là task riêng theo SOT, chưa tự bắt đầu.

Phase3 artifacts/source và PROJECT_OVERVIEW giữ nguyên. Parent campaign partial, interrupted run7, logs/cache/checkpoints được giữ như evidence; local completion không đồng nghĩa commit, push, CI hoặc release.
