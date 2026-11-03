# Model card — ViDocLens gold-only student (Phase 3)


**Bản nháp nghiên cứu local, chưa phát hành.** **G3 đạt9/9 tiêu chí local**: smoke52/resume/reload với adapter diff0 và gold-only baseline đủ ba seed. Hiện trạng và số kiểm chứng ở [STATUS](STATUS.md); protocol ở [workflow Phase 3](PHASE3_WORKFLOW.md). Các checkpoint smoke không phải model để triển khai.

| Thuộc tính | Profile đã khóa |
|---|---|
| Base | Qwen/Qwen3-VL-2B-Instruct |
| Immutable revision | `89644892e4d85e24eaac8bacfd4f463576704203` |
| Base weights SHA-256 | `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0` |
| Upstream license metadata | Apache-2.0 trong model card đã tải ở revision trên; không đồng nghĩa cấp quyền phát hành ReceiptVQA hoặc adapter |
| Adapter | PEFT safetensors; rank8/alpha16/dropout0.05, 112 language attention q/k/v/o projections; vision/base frozen |
| Processor | Cùng base revision, lưu riêng processor/tokenizer/chat template trong từng checkpoint |
| Dữ liệu | ReceiptVQA containment v1 G10: 454 ảnh/405 nhóm/3.053 QA; gold raw, không teacher output |
| Split SHA-256 | `3b591e74d2c7c8515724641351017bb63b0247d940c30f5e068479cc2f30a4d9` |
| Plan SHA-256 | `2cc060be5c31ff5a6216909039751c2a0f39756db7e5067796fdd8217d62b8a2` |
| Config | [phase3_gold_v2.json](../configs/student/phase3_gold_v2.json), immutable copy trong plan |
| Prompt | [student_vqa_v1](../prompts/student_vqa_v1.txt), image + một câu hỏi; không OCR |
| Compute | RTX3060 12GB, WSL2/Python3.11.14, NF4 double quant, BF16 compute/autocast, nonquantized base fp32 qua PEFT; SDPA math/deterministic |
| Input budget | Pixel cap262144, context2048, output128; không truncate input, raw prediction giữ nguyên |
| Primary budget | Ba seed17/42/2026; mỗi seed một epoch/191 updates; microbatch1/accumulation16, batch cuối13; AdamW1e-4/wd0.01, cosine/warmup6 updates, clip1.0 |
| Environment | [ML hash lock](../infra/requirements/phase0-ml-linux-py311.lock); [environment evidence](../artifacts/phase3/environment_v2.json) khớp71/71 packages |
| Code provenance | Local branch `codex/phase3-student-training`, base`d13360e`, uncommitted; run source snapshots và checks code hashes. Không giả lập commit/release ID |
| Verifier/router/serving | Chưa tích hợp; `inference_ready=false` |

## Đánh giá và lựa chọn

Cùng 100 dev components/666 QA của Phase 2, Numeric slice379 QA được freeze trước prediction. Chấm strict NFC EM/F1/ANLS và compatible protocol riêng; bootstrap2000 theo component, seed42. Mỗi seed chọn giữa checkpoint96 và191 bằng strict EM → Numeric EM → p50 latency → step sớm. Báo cả ba seed và sample standard deviation; không chọn seed tốt nhất thay số trung bình.

Đã chấm L1 và cả hai checkpoint của ba seed trên666 QA/run; rule chọnstep191 cho cả ba. G3 report kiểm checkpoint/source hashes và replay raw metrics, giữ nguyên parent campaign bị pause và bind continuation riêng. Test/OOD/dev_calibrate/audit không tham gia lựa chọn; đây là dev selection, chưa là kết quả generalization cuối.

| Seed | Checkpoint | Strict EM | Numeric EM | Checkpoint manifest SHA256 |
|---|---|---:|---:|---|
| 17 | [step191](../artifacts/phase3/campaign_v1/L2_seed17/checkpoint-0191/checkpoint.json) | 45.65% | 61.21% | `a7446cd98151391591ff984761e8881011c58fbcca2a6f58b909516e9a075317` |
| 42 | [step191](../artifacts/phase3/campaign_v1/L2_seed42/checkpoint-0191/checkpoint.json) | 45.80% | 61.74% | `e9e0cecf3c5dd4afd8f80ec9c26d4fd17595ce9605b11e2a785c21965e0cfbc6` |
| 2026 | [step191](../artifacts/phase3/campaign_v1/L2_seed2026/checkpoint-0191/checkpoint.json) | 46.55% | 62.01% | `af035d8f59be987f432bef90c90a7a62a58f06028d8f9196d4bdea7bc4d4c45a` |

Ba seed mean strict EM **46,00%**, sample SD **0,483 điểm %**; F1 **53,52%**, ANLS **63,98%**, Numeric EM **61,65%**. L1 EM34,38%; mean seed EM−L1 +11,612 điểm %, paired95% CI[8,736;14,467] (2.000 group resamples, seed42). Không chọn seed tốt nhất để thay trung bình; bootstrap không gồm training variance. [Báo cáo đầy đủ](PHASE3_RESULTS.md), [G3 report](../artifacts/phase3/g3_report_v1.json).

Ba seed train191 updates/3.053 unique QA mỗi seed, training peak reserved3,3008GiB, không OOM. Raw learning curves, optimizer/scheduler/RNG và processor nằm trong artifacts local. Checkpoint hashes ở bảng là SHA của manifest; manifest bind adapter safetensors/processor/state. Không có production checkpoint hoặc serving bundle đã phát hành.


Feasibility hiện đo trên dữ liệu thật có max train sequence462 và target105 token; context ceiling2048 là giới hạn cấu hình, chưa là kiểm thử VRAM worst-case ở mọi chuỗi2048.

## Intended use và giới hạn

Nghiên cứu hỏi đáp ảnh biên lai tiếng Việt, input một ảnh/một câu hỏi. Chưa xác nhận trích xuất KIE, tài liệu nhiều trang, OOD đầy đủ, hệ thống từ chối hoặc xác minh numeric. Ảnh bị resize theo pixel budget; chữ nhỏ, mờ hoặc nhiều trường gần nhau có thể gây lỗi. Không có OCR/verifier sửa output. Cap128 có thể cắt đáp án dài; report phải giữ số lượt chạm cap và toàn bộ denominator.

## Cách nạp và tái lập

Dùng `vidoclens.student.predict` với plan đã khóa và checkpoint đủ hash theo [workflow](PHASE3_WORKFLOW.md). Runtime nạp base local đúng revision/SHA, processor của checkpoint và adapter, không merge vào base4bit; không tải network. Resume train cần optimizer/scheduler/Python/NumPy/CPU/CUDA RNG và đúng plan. Profile backend khác là protocol mới, cần regression; v1 auto-SDPA không đạt greedy resume và được giữ trong lịch sử.

Latency mỗi QA gồm tiền xử lý và generation batch1, không gồm cold model load; request đầu vẫn được giữ. Có cache ảnh decode trong process, không cache answer hoặc chia sẻ KV giữa QA. Profile ghi cold model load và peak allocated/reserved riêng. Các số này không đo toàn bộ điện năng hoặc chi phí thuê GPU.

Dữ liệu pretraining của base chưa được dự án audit độc lập; việc không dùng test/OOD trong pipeline này không chứng minh base chưa từng tiếp xúc benchmark.

## Phát hành

Chưa tạo release, upload model hoặc phục vụ API. Dữ liệu, ảnh, predictions/gold, optimizer state và checkpoint chỉ local/ignored. Release về sau cần quyền dữ liệu/adapter, compatibility/regression và rollback bundle; train thành công không tự cấp quyền phát hành. Chủ dự án tự commit/push source code thủ công.
