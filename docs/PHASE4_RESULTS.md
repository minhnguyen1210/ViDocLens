# Kết quả Phase 4 — ViDocLens

Tạo từ evidence ngày 2026-11-05T03:49:58.606862+00:00. G4: **pass**.

G4 đã đạt đủ các tiêu chí, gồm human review thật.

## Phạm vi và bảo toàn

Giữ nguyên G3, artifacts và frozen split Phase 3; L2 được adopt từ evidence cũ. Dev có 100 components/666 QA. Silver train ngoài G10 có 4.073 ảnh/27.774 QA; audit holdout có 504 ảnh/3.454 QA. Test, OOD và dev_calibrate không được dùng để chọn teacher, filter, checkpoint hoặc huấn luyện trong Phase 4.

## Teacher local

Model `Qwen/Qwen3-VL-4B-Instruct`, revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`; image + question, không có gold trong input. Dùng cùng teacher/pool cho các silver arms.

Candidate được chọn: `raw_single_v1`; strict EM 36.49%, ANLS 61.34%, coverage 96.25%. Generation 10.83 phút; peak reserved 4.283 GiB. Đây là gate khả thi, không chứng minh teacher vượt L2; giữ nguyên failure và raw output. Thời gian là generation trên host dùng chung.

| Sinh nhãn | QA | Requests | Answered | Generation phút đã đo | Requests thiếu số đo | Peak reserved GiB |
|---|---:|---:|---:|---:|---:|---:|
| train_fit | 27774 | 27774 | 26593 | 407.69 | 0 | 4.287 |
| audit_holdout | 3454 | 3454 | 3315 | 57.91 | 0 | 4.287 |

Thời gian sinh nhãn lấy từ từng request trong manifest, không gồm load weights, OCR, I/O, pilot thất bại hoặc retries ngoài các run này. Không gọi đây là tổng wall time hay chi phí toàn dự án. Logs/cost của các lần chạy dở giữ trong [STATUS_HISTORY](<STATUS_HISTORY.md>).

## Filter và audit holdout

F1 đã freeze trên dev: tau=0.0, tối đa 3 dòng; không sửa digit/target. Không thay rule theo holdout hoặc kết quả H2.

| Population | QA | Eligible | Kept | Precision | Recall | Retention | False accept | False reject |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Toàn audit holdout | 3454 | 3315 | 588 | 67.18% | 32.54% | 17.74% | 193 | 819 |
| by_answer_type: hybrid | 568 | 568 | 65 | 61.54% | 36.70% | 11.44% | 25 | 69 |
| by_answer_type: numeric | 1907 | 1907 | 334 | 71.26% | 26.74% | 17.51% | 96 | 652 |
| by_answer_type: text | 840 | 840 | 189 | 61.90% | 54.42% | 22.50% | 72 | 98 |
| by_answer_type: unknown | 139 | 0 | 0 | — | — | — | 0 | 0 |
| by_question_type: address | 153 | 136 | 11 | 81.82% | 42.86% | 8.09% | 2 | 12 |
| by_question_type: date | 260 | 253 | 32 | 68.75% | 22.45% | 12.65% | 10 | 76 |
| by_question_type: items | 438 | 427 | 49 | 67.35% | 25.58% | 11.48% | 16 | 96 |
| by_question_type: merchant | 409 | 399 | 96 | 66.67% | 50.00% | 24.06% | 32 | 64 |
| by_question_type: total | 855 | 822 | 146 | 69.18% | 30.06% | 17.76% | 45 | 235 |
| by_question_type: unknown | 1339 | 1278 | 254 | 65.35% | 33.07% | 19.87% | 88 | 336 |
| ocr_quality_bins: engine_confidence_high | 1209 | 1159 | 206 | 74.76% | 32.91% | 17.77% | 52 | 314 |
| ocr_quality_bins: engine_confidence_low | 92 | 83 | 2 | 100.00% | 11.11% | 2.41% | 0 | 16 |
| ocr_quality_bins: engine_confidence_medium | 2153 | 2073 | 380 | 62.89% | 32.83% | 18.33% | 141 | 489 |

OCR confidence bins là proxy của engine, không phải CER hoặc human quality. OCR agreement không chứng nhận đáp án đúng nghĩa trường được hỏi.

## Student: mean và sample SD qua ba seed

| Arm | Strict EM mean ± SD | Token F1 mean ± SD | ANLS mean ± SD |
|---|---:|---:|---:|
| L2 | 46.00% ± 0.48 pp | 53.52% ± 0.60 pp | 63.98% ± 0.29 pp |
| P1-full | 41.09% ± 0.57 pp | 48.16% ± 0.57 pp | 61.07% ± 0.51 pp |
| P1-size | 40.94% ± 0.48 pp | 48.49% ± 0.31 pp | 60.82% ± 1.16 pp |
| P2 | 43.34% ± 0.46 pp | 50.32% ± 0.44 pp | 61.58% ± 0.42 pp |

| Arm | Seed | Checkpoint step | Strict EM | Training phút | Peak reserved GiB |
|---|---:|---:|---:|---:|---:|
| L2 | 17 | 191 | 45.65% | 36.28 | 3.301 |
| L2 | 42 | 191 | 45.80% | 35.82 | 3.301 |
| L2 | 2026 | 191 | 46.55% | 36.00 | 3.301 |
| P1-full | 17 | 191 | 40.84% | 38.84 | 3.301 |
| P1-full | 42 | 96 | 40.69% | 42.18 | 3.301 |
| P1-full | 2026 | 191 | 41.74% | 40.21 | 3.301 |
| P1-size | 17 | 191 | 40.39% | 41.56 | 3.301 |
| P1-size | 42 | 96 | 41.14% | 42.02 | 3.301 |
| P1-size | 2026 | 191 | 41.29% | 39.84 | 3.301 |
| P2 | 17 | 191 | 43.24% | 41.82 | 3.301 |
| P2 | 42 | 191 | 42.94% | 41.97 | 3.301 |
| P2 | 2026 | 191 | 43.84% | 40.62 | 3.301 |

Mọi primary run có 191 updates. Silver arms có 1.528 gold + 1.528 silver exposures; L2 lịch sử có 3.053 gold exposures. Primary P2/P1-size khớp updates, hyperparameters, gold order/counts và số silver samples; FLOPs/wall time có thể khác theo ảnh/target. Checkpoint được chọn riêng mỗi seed từ step96/191; không chọn seed tốt nhất. Chi phí bảng trên là toàn trajectory, không chỉ prefix của checkpoint được chọn; không gồm label/OCR/load/eval/save.

## H2: paired group bootstrap

| So sánh | Mean delta EM (pp) | Seed delta SD (pp) | 95% group CI (pp) |
|---|---:|---:|---|
| P2_vs_P1-size | +2.40 | 0.54 | [0.72; 4.17] |
| P2_vs_P1-full | +2.25 | 0.15 | [0.50; 4.12] |
| P2_vs_L2 | -2.65 | 0.23 | [-4.33; -0.98] |

P2 cải thiện EM so với P1-size trên dev; CI conditional theo ba seed nằm trên 0.

Primary P2−P1-size: +2.40 điểm EM trên dev. Đọc ước lượng cùng CI và seed SD ở trên. CI bootstrap theo duplicate group với 2.000 resamples, conditional trên ba seed đã chạy; không bao gồm training variance. Đây là dev selection, chưa là xác nhận final test. H2 âm vẫn là kết quả hợp lệ nếu đủ evidence; không đổi filter để làm H2 thắng.

## Human review và evidence

Human review đã được gate kiểm đủ packet và attestation.

[G4 report](<../artifacts/phase4/g4_report_reviewed_v2.json>) · [Comparison và slices](<../artifacts/phase4/execution_v1/comparison/comparison.json>) · [Holdout audit](<../artifacts/phase4/execution_v1/holdout_report.json>) · [Resume proof](<../artifacts/phase4/execution_v1/campaign/resume_proof.json>) · [STATUS](<STATUS.md>)

G4 report SHA-256: `d087ed94cc7483da75863944d5620982bb53ac421419ba182aef0970839092ff`. Không suy CI, release hoặc API readiness từ kết quả local này. Assistant không stage/commit/push.

[Human review theo bốn strata](<../artifacts/phase4/g4_report_reviewed_v2_human_review.json>)

## Final code checks và trạng thái bàn giao

[Final WSL check manifest](../artifacts/phase4/checks_final_wsl_v1/checks.json): pytest **485 passed**,
Ruff/format/doctor/repository policy pass, **71 schemas match**. Có một cảnh báo deprecation
Starlette/httpx; doctor xác nhận `inference_ready=false` / `model_not_configured`. Windows check
475 passed/10 skipped thuộc integration v6 trước lượt final WSL; không có Windows rerun hoặc
GitHub CI mới sau final check này. Docker/release chưa được xác minh.

Campaign recovery hoàn tất 9 matched runs và 12-result comparison. Parent campaign attempt vẫn
`complete=false` vì SIGINT có chủ đích sau run6; run7 cũ step75/191 được giữ cùng manifest,
run7 mới chạy từ step0 và run8–9 hoàn tất. [Continuation state](../artifacts/phase4/recovery_after_run6_v1/continuation.json)
ghi trạng thái hoàn tất riêng, không sửa lịch sử parent. Phase4 done local sẵn sàng cho owner review;
GitHub commit/push, CI và release là các trạng thái riêng.
