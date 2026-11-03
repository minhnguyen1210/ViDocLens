# Phase 3 — Student và gold-only baseline


Protocol `phase3_gold_v2`, SOT v1.12 / ADR-026–027. **G3 đã đạt local; xem [báo cáo](PHASE3_RESULTS.md).** Các lệnh dưới là runbook tái lập; run IDs đã tồn tại phải đổi sang tên mới. Hiện trạng ở [STATUS](STATUS.md).

## Luồng thực thi

1. Kiểm G1/G2, locked WSL ML runtime và GPU; dùng weights 2B có sẵn, không gọi API trả phí.
2. Freeze toàn bộ G10 train (454 ảnh/405 components/3.053 QA), dev subset Phase 2 (100 ảnh/666 QA), prompt/config/hash. Materialize ảnh có kiểm raw SHA; train gold và dev question-only nằm file riêng, Git ignored.
3. Unit tests loss mask/causal positions, RNG/checkpoint/data boundary; actual processor preflight không truncate, thống kê token/pixel/answer length. Numeric dev membership do evaluator freeze trước prediction.
4. Probe backward thật; smoke 52 updates với 64 train QA (có long targets). Lưu gradient/loss/VRAM và checkpoints; reload processor/base/adapter, resume từ update50 đến52 so với continuous, có optimizer/scheduler/RNG. Smoke không đi vào L2 weights.
5. L1 zero-shot và L2-k10 ba seed, một epoch/191 updates mỗi seed, cùng input profile. Evaluate checkpoint96 và191 trên dev. Chọn theo EM → Numeric EM → p50 latency → step sớm; giữ metric từng checkpoint và tất cả seed.
6. Báo strict/compatible metrics, paired component bootstrap, mean/std ba seed, latency/VRAM/compute estimate. Model card, environment lock evidence và checkpoint manifests; chỉ đóng G3 khi có số thật.

## Cấu hình và ranh giới

[Config](../configs/student/phase3_gold_v2.json), [prompt](../prompts/student_vqa_v1.txt), ML lock Phase 0 được dùng lại và phải kiểm trên training thật. Một GPU, microbatch1/accumulation16, BF16 autocast, NF4 double quant, SDPA math và deterministic algorithms, không offload. CUBLAS workspace `:4096:8`, TF32 off; v1 auto-backend giữ trong lịch sử do greedy resume không khớp. LoRA language attention đã enumerate; vision/base frozen. `prepare_model_for_kbit_training` của PEFT upcast nonquantized base sang fp32; điều này được ghi trong profile, không nhận toàn model BF16.

Numeric slice: gold có ít nhất một digit và không có chữ cái; các ký tự punctuation/whitespace vẫn giữ nguyên khi chấm. Đây là heuristic được định trước, không phải human taxonomy. Null/error/truncated không được bỏ denominator. Raw prediction luôn giữ; không parse lời giải để chọn câu có vẻ đúng.

Learning curve ghi loss trung bình theo QA trong mỗi optimizer update; `grad_norm` là norm trước clipping1.0. Thời gian update gồm collator, forward/backward, clip, optimizer/scheduler và CUDA synchronization; không gồm model load hoặc checkpoint I/O. Batch cuối dùng13 QA và chia loss theo13, không chia16.

Checkpoints lưu adapter safetensors, processor/tokenizer/chat template, optimizer/scheduler/RNG, base revision/weight SHA, plan/config/lock hashes và step. Chỉ save ở accumulation boundary; checkpoint partial không hợp lệ. Resume từ trusted local checkpoint sau checksum, `torch.load(weights_only=True)`. Không merge vào base4bit.

## Lệnh

Windows có thể tạo plan không cần Torch:

```powershell
.venv/Scripts/python.exe -m vidoclens.student.data --output artifacts/phase3/data_v2 --config configs/student/phase3_gold_v2.json
```

ML chạy bằng `/home/vidoclens/.venvs/vidoclens-ml-repro/bin/python` trong WSL tại repo. Các tên dưới là run IDs của lần triển khai này; nếu tái lập hãy dùng run IDs mới và cập nhật toàn bộ đường dẫn tương ứng. Thư mục output phải mới; lệnh ghi lại lần chạy, không ghi đè evidence cũ:

```bash
python -m vidoclens.student.preflight --plan-dir artifacts/phase3/data_v2 --output artifacts/phase3/processor_preflight_v2.json
python -m vidoclens.eval.student freeze --plan-dir artifacts/phase3/data_v2 --output artifacts/phase3/dev_protocol_v2.json
python -m vidoclens.student.train --plan-dir artifacts/phase3/data_v2 --output artifacts/phase3/smoke_v3 --seed 42 --kind smoke
python -m vidoclens.student.train --plan-dir artifacts/phase3/data_v2 --output artifacts/phase3/smoke_resume_v2 --seed 42 --kind smoke --resume artifacts/phase3/smoke_v3/checkpoint-0050
python -m vidoclens.student.verify_resume --plan-dir artifacts/phase3/data_v2 --continuous artifacts/phase3/smoke_v3 --resumed artifacts/phase3/smoke_resume_v2 --output artifacts/phase3/resume_verification_v2.json
```

Sau khi preflight/resume proof đạt, campaign chạy L1 và lần lượt train/evaluate cả ba seed bằng các GPU processes riêng; chỉ có một model process ở mỗi thời điểm:

```bash
python -m vidoclens.student.campaign --plan-dir artifacts/phase3/data_v2 --output artifacts/phase3/campaign_v1 --preflight artifacts/phase3/processor_preflight_v2.json --resume-proof artifacts/phase3/resume_verification_v2.json --protocol artifacts/phase3/dev_protocol_v2.json
python -m vidoclens.eval.phase3 --plan-dir artifacts/phase3/data_v2 --campaign-dir artifacts/phase3/campaign_v1 --checks-path artifacts/phase3/checks_v2.json --output artifacts/phase3/g3_report_v1.json
```

`student.preflight`, `student.verify_resume`, `student.predict` và `eval.student` có `--help` cho từng bước. `eval.student freeze` phải chạy trước predictions, khóa numeric membership và rule; evaluator không gọi model/API. Campaign fail fast nếu một subprocess lỗi, giữ logs/outputs, không tự xóa/chạy lại lên kết quả cũ.

STATUS ghi lệnh thực tế và phần chưa xong. Assistant không stage/commit/push; chủ dự án tự thực hiện Git. Không phát biểu CI/GPU training đạt chỉ từ tests CPU.

## Tiếp tục evaluation sau pause (ADR-027)

Campaign gốc `campaign_v1` đã bị ngắt theo yêu cầu chủ dự án ở seed2026/step96. Toàn bộ training và các run trước đó giữ nguyên. Predictor/campaign không có resume/append; [handoff](PHASE3_HANDOFF.md) ghi các lệnh inference/evaluate còn thiếu, chạy vào `continuation_v1`. Private runner `continuation_v1/execute.py` ghi command/exit/log hashes vào `execution.json`; chỉ có một GPU process mỗi lúc.

Sau khi hai lượt mới đều hoàn tất, tạo manifest rồi audit; dùng output mới và checks thực tế của code hiện tại. Chạy audit bằng Python3.11.14 trong WSL ML-repro đã pin, cùng interpreter với evaluator gốc; replay so report đầy đủ, không đổi Python/Unicode/floating summation giữa hai lượt:

```bash
python -m vidoclens.eval.continuation --plan-dir artifacts/phase3/data_v2 --campaign-dir artifacts/phase3/campaign_v1 --continuation-dir artifacts/phase3/continuation_v1 --pause-event artifacts/phase3/pause_event_v1.json --output artifacts/phase3/continuation_manifest_v1.json
python -m vidoclens.eval.phase3 --plan-dir artifacts/phase3/data_v2 --campaign-dir artifacts/phase3/campaign_v1 --continuation-path artifacts/phase3/continuation_manifest_v1.json --checks-path artifacts/phase3/checks_v3.json --output artifacts/phase3/g3_report_v1.json
```

Manifest không đánh dấu campaign cũ thành công. Run cũ complete được adopt nguyên vẹn; partial được bind riêng và không chấm vào baseline. Audit xác minh đủ source/profile/checkpoint/seed/population, replay metric từ raw predictions và giữ đường dẫn từng run. Không copy hoặc sửa cờ `complete` để vượt gate. Resolver hiện hỗ trợ evaluation-only continuation sau khi training ba seed đã hoàn tất.
