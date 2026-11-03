# Phase 3 — kết quả student gold-only

**G3 đạt local ngày 03/11/2026.** Toàn bộ training và evaluation đã hoàn tất, raw metrics được replay và audit bằng evidence thật. [Gate report local](../artifacts/phase3/g3_report_v1.json) · [STATUS](STATUS.md) · [workflow](PHASE3_WORKFLOW.md). Chưa commit/push, chưa có CI mới hoặc release; serving chưa tích hợp.

## Protocol và dữ liệu

SOT v1.12 / ADR-026–027. Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`, NF4 double quant, BF16 compute/autocast, nonquantized base FP32 qua PEFT. LoRA rank8/alpha16/dropout0.05 trên112 language attention q/k/v/o projections,3.211.264 trainable parameters; base/vision frozen. SDPA math/deterministic, TF32 off.

Train đúng G10 đã freeze: **3.053 QA,454 ảnh,405 nhóm**, chỉ raw gold; prompt `student_vqa_v1`, image + một câu hỏi, không OCR hoặc API outputs. Ba seed17/42/2026, mỗi seed một epoch/191 updates, microbatch1/accumulation16, batch cuối13, LR1e-4, AdamW wd0.01, warmup6/cosine, clip1. Dev cùng100 components/666 QA Phase2; numeric379 QA được freeze trước predictions. Không mở test/OOD/audit/dev_calibrate để tune hoặc chọn checkpoint.

Pixel cap262144, context2048, output128; processor không truncate. Chỉ supervise assistant raw answer+EOS, prefix/image/user/padding bị mask. Chọn checkpoint96/191 cho từng seed theo strict EM → Numeric EM → p50 latency → step sớm; không chọn seed tốt nhất thay trung bình.

## Kết quả dev strict

| Arm | Strict EM | Token F1 | ANLS | Numeric EM (N379) | p50/p95 (s) | Cap hits | Được chọn |
|---|---:|---:|---:|---:|---:|---:|---|
| L1 zero-shot | 34.38% | 41.96% | 54.47% | 47.49% | 0.792/1.652 | 3 | — |
| L2 seed17/step96 | 44.29% | 51.88% | 63.14% | 59.63% | 0.935/1.944 | 0 | — |
| L2 seed17/step191 | 45.65% | 53.18% | 64.02% | 61.21% | 0.935/1.923 | 0 | Có |
| L2 seed42/step96 | 43.84% | 51.37% | 62.57% | 59.37% | 0.942/1.868 | 0 | — |
| L2 seed42/step191 | 45.80% | 53.17% | 63.67% | 61.74% | 0.955/1.916 | 1 | Có |
| L2 seed2026/step96 | 44.14% | 51.04% | 61.93% | 59.37% | 1.005/2.093 | 1 | — |
| L2 seed2026/step191 | 46.55% | 54.21% | 64.24% | 62.01% | 1.027/2.125 | 0 | Có |

Mỗi lượt chấm đủ666 QA; error/abstain/missing giữ denominator. Raw output và output IDs được giữ; không parse lời giải để chọn câu có vẻ đúng hoặc sửa digit. Cap hits vẫn được tính điểm theo raw output.

| Metric của ba checkpoint được chọn | Mean | Sample SD (điểm %) |
|---|---:|---:|
| strict_nfc_em | 46.00% | 0.483 |
| strict_nfc_token_f1 | 53.52% | 0.598 |
| strict_nfc_anls | 63.98% | 0.290 |
| numeric_em | 61.65% | 0.403 |

## Paired group bootstrap so với L1

2.000 resamples, seed42, resample nguyên100 receipt/conservative components; QA-weighted estimand. Đây là dev subset dùng chọn checkpoint, chưa phải final test.

| So sánh strict EM | Chênh lệch (điểm %) | 95% CI (điểm %) |
|---|---:|---:|
| 17 | 11.261 | [8.321; 14.224] |
| 42 | 11.411 | [8.482; 14.308] |
| 2026 | 12.162 | [9.052; 15.165] |
| mean_seed_scores_minus_L1 | 11.612 | [8.736; 14.467] |

Các dòng seed là checkpoint được chọn trừ L1; mean_seed_scores_minus_L1 là trung bình điểm theo QA trên ba runs trừ L1, không phải model ensemble. Bootstrap không bao gồm training variance; sample SD ba seed được báo riêng. Không dùng các số này để kết luận tổng quát trên test/OOD.

## Compatible protocol riêng

`ligt_5b4376b_anls_0_0_2_v1` tách khỏi strict; không gọi strict là official score hoặc nhận historical reproduction của paper.

| Arm | Compatible metrics (0–1) |
|---|---|
| L1 zero-shot | accuracy=0.351351; set_token_f1=0.418728; anls=0.558941 |
| L2 seed17/step96 | accuracy=0.454955; set_token_f1=0.518183; anls=0.640335 |
| L2 seed17/step191 | accuracy=0.466967; set_token_f1=0.530913; anls=0.655314 |
| L2 seed42/step96 | accuracy=0.448949; set_token_f1=0.513291; anls=0.644024 |
| L2 seed42/step191 | accuracy=0.468468; set_token_f1=0.531095; anls=0.651348 |
| L2 seed2026/step96 | accuracy=0.451952; set_token_f1=0.509815; anls=0.634211 |
| L2 seed2026/step191 | accuracy=0.477477; set_token_f1=0.541363; anls=0.659677 |

## Training, memory và tính tái lập

| Seed | Updates / QA | First5 / last5 loss | Training update seconds | Peak allocated / reserved GiB | Checkpoint chọn |
|---|---:|---:|---:|---:|---:|
| 17 | 191 / 3053 | 1.17571 / 0.67210 | 2176.76 | 3.0129 / 3.3008 | 191 |
| 42 | 191 / 3053 | 1.03350 / 0.62255 | 2149.10 | 3.0369 / 3.3008 | 191 |
| 2026 | 191 / 3053 | 1.23118 / 0.46501 | 2160.07 | 3.0369 / 3.3008 | 191 |

Đường học đủ191 points/seed nằm trong `learning_curve.jsonl` và `run.json`; audit kiểm hai bản khớp, loss/gradient hữu hạn, đủ unique QA và checkpoint hashes. Grad norm được ghi trước clipping. Thời gian updates gồm collator/forward/backward/optimizer/scheduler/CUDA sync, không gồm cold load hoặc save.

Preflight toàn3.053 train/666 dev đạt, 0 truncate: max train sequence462/target105/image256 tokens, dev sequence398/image252 tokens. Context2048 là ceiling cấu hình, chưa chứng minh worst-case memory cho mọi chuỗi2048. RTX3060 12GB/WSL2/Python3.11.14,71/71 package versions khớp ML lock.

Smoke protocol v2 chạy52 updates/64 train QA; resume50→52 adapter max absolute diff0, loss tails và greedy IDs trùng, reload base/adapter/processor trong process mới trùng. Probe chạm output cap128 là consistency test, không là quality metric. Protocol v1 auto-SDPA có adapter diff8.4983e-09 trong tolerance nhưng greedy resume khác; đã giữ failure và đổi backend trước L1/L2 dev predictions. Lỗi progress writer của smoke đầu tiên cũng giữ nguyên.

Tổng ba lượt train: **6485.93s**, ngoại suy12 matched runs khoảng **7.21 training GPU-hours**. Không gồm label/OCR generation, evaluation, model load/checkpoint I/O, token lengths khác hoặc retry; chưa đo điện năng/giá điện. [Dự toán có số đo steady-state](PHASE0_BUDGET.md).

Latency là preprocessing+generation từng QA, batch1, giữ request đầu; cold load báo riêng trong profile, có cache ảnh decode nhưng không cache answer/KV giữa QA. Đây là số đo trên máy phát triển, không là benchmark host cô lập; có CPU checks trong lượt continuation. Phase2 nhóm nhiều câu hỏi/request nên không so latency trực tiếp với API để kết luận tốc độ cascade.

## Pause và continuation

Chủ dự án yêu cầu pause khi seed2026/step96 có238/666 predictions. Cả ba seed đã train xong. Parent `campaign_v1` vẫn `complete=false`, child SIGINT exit-2 và parent fail-fast RuntimeError; partial không bị xóa/chấm như run đầy đủ. Sau yêu cầu tiếp tục, chạy lại đủ666 QA step96 và chạy step191 vào `continuation_v1`, không train lại hoặc ghép partial.

`continuation_manifest_v1.json` bind parent/pause/execution/runs và source snapshots bằng SHA256. Final audit adopt completed runs nguyên vẹn, kiểm đủ plan/config/seed/profile/checkpoints/source, chấm lại metrics từ raw predictions bằng interpreter đã pin. G3 report đạt trên tập evidence đầy đủ; không sửa cờ complete của lịch sử.

## Evidence và kiểm tra

| Evidence | File local |
|---|---|
| G3 | [gate report](../artifacts/phase3/g3_report_v1.json) |
| Continuation | [manifest](../artifacts/phase3/continuation_manifest_v1.json) |
| Pause | [event](../artifacts/phase3/pause_event_v1.json) |
| Frozen plan | [manifest](../artifacts/phase3/data_v2/manifest.json) |
| Numeric/selection | [protocol](../artifacts/phase3/dev_protocol_v2.json) |
| Preflight | [processor report](../artifacts/phase3/processor_preflight_v2.json) |
| Resume/reload | [proof](../artifacts/phase3/resume_verification_v2.json) |
| Environment | [71-package verification](../artifacts/phase3/environment_v2.json) |
| Checks | [checks v3](../artifacts/phase3/checks_v3.json) |

Windows331 passed/9 skipped; WSL340 passed; student24 + continuation20 cases; Ruff125 files,40 schemas, file policy/YAML239 candidates tại lượt kiểm. Doctor `inference_ready=false`/`model_not_configured`. CI GitHub mới, Docker và serving/release chưa được xác minh. Không thêm dependency/driver, downloads hoặc paid API calls trong Phase3.

Artifacts/data/weights không đi kèm GitHub checkout. Plan SHA`2cc060be5c31ff5a6216909039751c2a0f39756db7e5067796fdd8217d62b8a2`; protocol SHA`db3134d89de01d833080efb7b0dccd6ed99ce3521dcddbecd5187bc20975016a`. Base pretraining contamination chưa được audit độc lập. K5/k25/k100/model phụ là extensions; silver/local teacher/verifier/OOD final/API deployment còn ở các phase sau.
