# Kết quả Phase 2

**G2 đạt ngày 03/11/2026 (Asia/Saigon).** Pilot và bốn baseline đã chạy API thật; metrics, chi phí, cache replay và role freeze có evidence. SOT v1.10 / ADR-023–025. [STATUS](STATUS.md) · [workflow/lệnh tái kiểm](PHASE2_WORKFLOW.md).

## Phạm vi và tính toàn vẹn

- Pilot: **50 ảnh G10 train / 344 QA / 59 groups**, không đọc gold để tạo request hoặc chọn prompt. 59/59 groups hợp lệ.
- Baselines: **cùng 100 dev_select components / 666 QA / 113 groups mỗi arm**. Selection seed 42 khóa trước output; gold dev chỉ mở ở evaluator sau khi đủ predictions.
- Tổng: **150 ảnh duy nhất, 511 live attempts**, không retry, không cache hit trong live run. Không mở test/OOD/dev_calibrate/audit để chọn teacher; không xuất output API sang training.
- API key trong `.env` đã dùng thành công cho cả hai snapshots; file ignored, runtime không log key, không thay đổi hệ thống/driver/dependencies.
- Plan/prompt/selection policy bất biến. A4 few-shot là extension tùy chọn và chưa chạy. Pilot train không có bảng accuracy vì không dùng gold của pilot.

## Chất lượng dev

Các số dưới tính theo phần trăm trên **toàn bộ 666 QA** mỗi arm; null/error/missing không bị loại. Strict protocol giữ case, dấu, digits và whitespace theo `strict_nfc_v1`; F1 là multiset token-F1. EM image-macro cho mỗi ảnh/component trọng số bằng nhau.

| Arm | Input / model | EM | Token F1 | ANLS | EM 95% CI | Image-macro EM |
|---|---|---:|---:|---:|---|---:|
| A1 | GPT-5.4 · OCR text | 57.66 | 68.87 | 80.69 | [53.46; 62.03] | 58.30 |
| A2 | GPT-5.4 · ảnh | 73.72 | 85.54 | 89.10 | [69.74; 77.54] | 73.90 |
| A3 | GPT-5.4 · ảnh + OCR | 76.28 | 87.53 | 90.01 | [72.58; 79.97] | 76.77 |
| A5 | GPT-5.4 mini · ảnh + OCR | 70.27 | 81.26 | 86.65 | [66.30; 73.90] | 70.58 |

Bảng tương thích LiGT dùng protocol `ligt_5b4376b_anls_0_0_2_v1`, báo riêng để không đánh tráo với strict; **không phải tái lập toàn benchmark official test**.

| Arm | Compatible accuracy | Set-token F1 | ANLS |
|---|---:|---:|---:|
| A1 | 59.16 | 68.68 | 81.77 |
| A2 | 75.83 | 85.19 | 90.37 |
| A3 | 78.53 | 87.15 | 91.28 |
| A5 | 72.67 | 80.94 | 87.84 |

| Arm | Answered | Abstained | Error QA | Missing QA | Coverage |
|---|---:|---:|---:|---:|---:|
| A1 | 650 | 16 | 0 | 0 | 97.60% |
| A2 | 665 | 1 | 0 | 0 | 99.85% |
| A3 | 665 | 1 | 0 | 0 | 99.85% |
| A5 | 660 | 0 | 6 | 0 | 99.10% |

**A5 có một nhóm lỗi schema (6 QA):** output không thỏa consistency constraint của `TeacherAnswer`; raw response và usage vẫn được lưu. Cả nhóm được ghi error, tính 0 quality, giữ đủ denominator. Không repair, retry hoặc bỏ nhóm để tăng metric. 510/511 groups có status ok; status ok không đồng nghĩa câu trả lời đúng.

Bootstrap 2.000 lần, seed 42, resample theo 100 receipt/leakage components; estimand QA-weighted. Paired differences EM:

- A3 − A2: **+2.55pp**, 95% CI [+0.43; +4.75]pp.
- A5 − A3: **-6.01pp**, 95% CI [-8.90; -3.15]pp.

A3 tốt hơn A2 trên subset này, có bằng chứng paired dev cho lợi ích của OCR input. CI chưa gồm training/provider stochastic variance hoặc selection optimism; không chứng minh OCR giúp mọi QA, không là final-test claim.

## Usage, chi phí và latency

| Run | Requests | Input tokens | Cached input | Output tokens | USD | p50 / p95 giây mỗi group |
|---|---:|---:|---:|---:|---:|---|
| pilot | 59 | 178,309 | 0 | 31,348 | 0.916010 | 7.119 / 9.091 |
| A1 | 113 | 127,173 | 0 | 59,786 | 1.214753 | 6.589 / 8.668 |
| A2 | 113 | 307,149 | 0 | 60,671 | 1.677962 | 7.573 / 9.913 |
| A3 | 113 | 339,418 | 0 | 60,122 | 1.750404 | 7.207 / 9.786 |
| A5 | 113 | 339,418 | 0 | 59,172 | 0.520879 | 3.414 / 4.514 |

**Tổng 6,080008 USD / cap 20 USD**, còn 13,919992 USD trong ledger của campaign; reserved=0, uncertain=0, 511 attempts đều settled. Đây là usage thực × price cards đã khóa (làm tròn micro-USD từng attempt), **chưa đối soát invoice tài khoản**. Số dư không mở thêm phạm vi ảnh/request hoặc quyền training.

Mỗi process chạy sync một request; tối đa hai experiment processes cùng ledger. Pilot chạy tuần tự trước dev; các lượt A1/A5, A1/A2 và A2/A3 có thời gian chồng nhau. Latency đo validation/cache/network/parse mỗi group, có first request, không gồm OCR offline; không là serving/deployment latency. Timestamps UTC đầy đủ trong report/run manifests.

**Replay 511/511 cache hits** (59 + 4×113), tất cả result-file hashes trùng live; ledger attempts/spent/reserved/uncertain giữ nguyên. Replay dùng đường dẫn credential không tồn tại: nếu cache miss sẽ dừng trước provider. Lỗi schema A5 vẫn là lỗi khi replay. Không phát sinh API calls hoặc spend mới.

## Quyết định teacher và G2

- Benchmark và fallback chọn **A3 / gpt-5.4-2026-03-05 / image_ocr / teacher_vqa_v2**; detail high, reasoning none, output cap 4096, store false. Policy khóa trước dev output: EM, rồi ANLS/cost/ID khi hòa.
- A5 rẻ hơn A3 nhưng giảm **6,01pp EM**, vượt ngưỡng fallback 2pp. Fallback configuration đã chọn nhưng **serving vẫn disabled**, cần Phase 5 và quyền trên dữ liệu/request thực tế.
- Label strategy chọn nhánh **local open-weight** ADR-014. Qwen3-VL-4B vẫn candidate chưa tải/pilot; phải qua license/VRAM/quality trước Phase 4. API training export và Batch upload vẫn false.

| G2 criterion | Kết quả |
|---|---|
| `all_live_experiments_complete` | PASS |
| `pilot_50_images` | PASS |
| `same_100_dev_images` | PASS |
| `replay_zero_calls_and_spend` | PASS |
| `budget_within_cap_and_settled` | PASS |
| `offline_checks_passed` | PASS |
| `no_test_or_ood_selection` | PASS |
| `no_api_training_export` | PASS |
| `selection_policy_unchanged` | PASS |

Budget vượt cap/concurrency/retry/uncertain và Batch partial/expired/missing đã kiểm bằng fixture; không cố tiêu tiền vượt cap để kiểm tra. Batch implementation có offline tests/dry-run, **chưa live upload** vì grant không gồm Batch. Không giảm điều kiện G2 để đạt quality target; kết quả âm/lỗi vẫn được báo.

## Dữ liệu chuẩn bị và kiểm tra

- OCR dev: 100/100 ok, 4.327 spans, 0 empty/cache hits; CPU p50=6,9768s, p95=9,3199s; sampled peak RSS 1.495.355.392 bytes. Cùng stack/revisions Phase 1, không tải thêm weights.
- 511 payloads khớp frozen questions/partitions/image hashes; không có gold fields. Max body 1.859.429 bytes, tổng 214.969.967 bytes trước retry. Hai bản plan tái tạo trùng SHA.
- Batch dry-run lịch sử: 498 shards với full input-token bound 2.000.000, max 190MB, model riêng; 215.034.864 JSONL bytes; không upload.
- Windows Python 3.14.9: **289 passed, 7 skipped**. WSL ML-repro Python 3.11.14: **296 passed**. 61 teacher fixtures + 8 credential fixtures + 4 finalization fixtures nằm trong suite.
- Ruff check/format đạt, 105 Python files; 36 schemas match; file policy/YAML đạt 212 candidates tại lượt kiểm. Các kiểm tra này không thay thế content/secret/license review.
- Doctor: inference_ready=false/model_not_configured đúng trạng thái serving. Warning Starlette/httpx đã biết còn tồn tại. Không chạy Docker, GPU/student training hoặc GitHub CI cho thay đổi Phase 2.

## Evidence local và hash

Artifacts/dataset/cache/grant được Git ignore và không đi kèm clone. API outputs chỉ dùng benchmark. Các report không chứa key; bản thiếu-key đầu tiên vẫn giữ nguyên trong lịch sử.

| Artifact | SHA256 |
|---|---|
| [G2 report](../artifacts/phase2/final_v1/report.json) | `7c0462bce5ffc7b888b4293376b06573c1e1926f72f080438217ef2116347e21` |
| [Role freeze](../artifacts/phase2/final_v1/role_freeze.json) | `20b38839969434ffcfc6124f76a06d70bb6f3ec1464d338f6fffc3e11d1c58ae` |
| [Selection policy](../configs/teacher/selection_v1.json) | `e626850dd368a649e172205dc1e61c2310832cdfbb2c54860ae7fae0fa755c5f` |
| [Policy freeze trước dev](../artifacts/phase2/selection_policy_freeze_v1.json) | `035694f86939143b6e383ac059db78901e836632e010c89e26e09c4d6b168f44` |
| [Checks](../artifacts/phase2/checks_live_v2/summary.json) | `d1715296781ac1ead31b19e3470fbeeea37564d418fc8c983a6ef362290d88f4` |
| [API plan](../artifacts/phase2/api_plan_v1/manifest.json) | `a4e08717582b1754e50e8c7170bd8b105261164da66adf4993eb5ebfa9e489ab` |
| [Question-only requests](../artifacts/phase2/api_plan_v1/requests.jsonl) | `32dae83d8a5304a8b96decdb8e7283a909d3bb5deca79bf249d38845616ea236` |
| [Owner approval](../artifacts/phase2/approval.json) | `82c1a99f149288b888ce1e6953f2cfcda7696c07e99e364c00a61c78215eb761` |
| [OCR summary](../artifacts/phase2/dev_ocr_v1/summary.json) | `9e58313d60de6d902f1f7c553c3ab0143173fcff13c9127b158933e3fd59916a` |
| [OCR profile](../artifacts/phase2/dev_ocr_v1/profile.json) | `c634cf790d2e00a4f9038c7ffb31932079335d31285fd2593059b07990871e81` |
| [Payload validation](../artifacts/phase2/preflight_validation_v1.json) | `b261adfa6767d2f3167fe1d4d45349976252605c3781f2056cfb7cd9ebb8635f` |

Report G2 lưu hashes của cả năm live run manifests và năm replay manifests; các run lưu hashes từng result, price cards, timestamps, samples và ledger snapshots. Raw per-attempt/final cache giữ trong SQLite local. Không cộng delta ledger của các run overlap để tính tổng cost.

`PROJECT_OVERVIEW.md` giữ SHA256 `d7d16d8d5400540c4e529cd07de92e1abf41c688584dbbf599ab5c67a6d3cf63`; split/G0/G1 artifacts không thay đổi. Phase 2 hoàn tất local; Phase 3 là training smoke/reload/resume và gold-only baselines. Chưa stage/commit/push; chủ dự án tự quản lý Git theo CONTRIBUTING.
