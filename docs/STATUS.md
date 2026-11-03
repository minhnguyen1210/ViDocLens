# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0, G1, G2 và G3 đã đạt local. Phase 3 hoàn tất theo SOT v1.12 / ADR-026–027.** [Báo cáo Phase 3](PHASE3_RESULTS.md) · [G3 evidence local](../artifacts/phase3/g3_report_v1.json) · [workflow](PHASE3_WORKFLOW.md). Phase 4–7 chưa triển khai; serving vẫn `inference_ready=false`.

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định workflow/Git; [history](STATUS_HISTORY.md) giữ lịch sử; [ADR](DECISIONS.md) ghi quyết định. Không suy phần trăm toàn dự án từ số phase/tests. Local done khác commit, push, CI và release.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu/môi trường | **done** | G0: GPU/OCR thật, hash locks và dựng lại; ADR-018 |
| 1 | Data, OCR, evaluator, OOD khởi đầu | **done** | G1 theo AI protocol ADR-021; [báo cáo](PHASE1_RESULTS.md), không là human gold/final OOD |
| 2 | Teacher, ledger/cache và API baselines | **done** | G2 live evidence; [báo cáo](PHASE2_RESULTS.md), ADR-025 |
| 3 | Student training / gold-only | **done (local)** | G3 **9/9** tiêu chí đạt; smoke/resume/reload, L1 + hai checkpoint × ba seed, raw metric replay và continuation provenance |
| 4 | Silver và chưng cất | planned | G3 đã gỡ; còn gate local label teacher/quyền labels/quality/VRAM |
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

## Kiểm tra local mới nhất

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python3.14.9 pytest | **331 passed,9 skipped** |
| WSL ML-repro Python3.11.14 pytest | **340 passed**, CPU suite, CUDA_VISIBLE_DEVICES rỗng |
| Student / continuation cases | 24 / 20; mask/causal loss/RNG/checkpoints và provenance/path/partial/config LF-CRLF |
| Ruff check / format | Đạt;125 Python files |
| Schema drift | **40 schemas match** |
| File policy / YAML | Đạt239 candidates tại lượt kiểm; không là secret/license scanner |
| Runtime lock sau resume | **71/71 packages match**, [environment v2](../artifacts/phase3/environment_v2.json) |
| GPU / raw metric replay | Smoke/resume/reload,3 full training runs,7 complete dev runs và G3 audit đạt |
| Doctor / serving | `inference_ready=false`, `model_not_configured`; backend sản phẩm thuộc Phase6 |
| GitHub CI / Docker | Chưa xác minh CI mới hoặc Docker trong lượt Phase3 |

[Checks v3](../artifacts/phase3/checks_v3.json) bind source SHA; Starlette/httpx warning đã biết còn tồn tại. Không cài dependency, thay driver, tải model/dataset mới, reboot hoặc mở hosting trong Phase3. Lượt cuối chỉ chỉnh docs sau khi code checks/G3 pass; không chạy thêm inference.

## Quyền và ranh giới còn hiệu lực

- Phase2:511 requests/150 ảnh,6,080008 USD theo usage trong cap20 USD; replay511/511 cache hits không thêm calls/spend. [G2 report](../artifacts/phase2/final_v1/report.json). Không phát sinh API spend ở Phase3; số dư không mở thêm phạm vi benchmark.
- Grant external bind đúng data/split/request keys Phase2; không tự mở test/OOD, dữ liệu mới hoặc serving. API output training export và Batch upload vẫn chưa cấp.
- Label strategy Phase4 là local open-weight có gate riêng; Qwen3-VL-4B còn candidate. Không dùng evaluation cache API để train.
- G1 AI references giữ provenance; không coi là human gold/final OOD. Base model pretraining contamination chưa audit độc lập.

## Bàn giao và việc kế tiếp

- **Local done:** Phase3/G3 đủ evidence. Nhánh `codex/phase3-student-training`, base`d13360e`; source/docs mới còn local.
- **Git:** assistant không stage/commit/push, không đổi remote. Chủ dự án tự review, commit và push theo CONTRIBUTING. CI mới/release chưa được xác minh.
- **Artifacts:** checkpoint/optimizer/processor, raw predictions, data và private reports bị ignore, không nằm trong GitHub checkout. `PROJECT_OVERVIEW.md`, frozen split và G0–G2 evidence giữ nguyên. [Model card](MODEL_CARD.md) chứa checkpoint hashes; [handoff](PHASE3_HANDOFF.md) giữ lịch sử pause, không phải việc còn dang dở.
- **Tiếp theo:** khi chủ dự án yêu cầu Phase4, mở gate local label teacher: xác minh license/revision/quyền training labels, profile VRAM và quality pilot; rồi triển khai silver/filter/matched P1/P2 theo SOT. Không chạy Phase4 trong lượt này. Không còn blocker G3.

Kiểm tra bàn giao cuối:20/20 source hashes khớp checks_v3;12 tài liệu UTF-8/liên kết local đạt; git diff --check đạt; Git index rỗng; không còn process Phase3 train/predict/campaign/audit trong WSL. Parent campaign checksum vẫn khớp pause event.
