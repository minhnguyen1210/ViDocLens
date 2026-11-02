# EXP-<system>-<dataset>-<seed>-<sequence>

Trạng thái: **planned** (`planned | running | completed | failed | invalidated`). Kết quả để trống cho đến khi đo. Tài liệu này là mẫu; copy cho mỗi run, không sửa mẫu thành kết quả của một run cụ thể.

## Câu hỏi và thiết kế

- RQ / giả thuyết / primary contrast:
- Biến thay đổi duy nhất; biến được giữ cố định:
- Baseline và lý do lựa chọn:
- Tiêu chí kết luận, margin thực dụng và cách xử lý nhiều so sánh:
- Phân hoạch dùng để tuning / audit / reporting:
- Phép so sánh matched-size, matched-compute hoặc full-pool; số QA và update thực tế:

## Provenance bắt buộc

| Nhóm | Trường phải lưu |
|---|---|
| Code | Commit, dirty state, diff artifact nếu dirty, entry point |
| Config | Config đã resolve, hash; không lưu key/secret |
| Dữ liệu | Dataset version, manifest + split hashes, duplicate group version, gold/silver IDs |
| Teacher | Provider, snapshot, prompt + schema hash, image preprocessing, question IDs/order, sampling, response IDs |
| OCR | Engine, weight revision, decode/preprocess settings, cache key version |
| Student | Base + adapter + processor revisions/hashes, quantization, LoRA targets, image/sequence budgets |
| Training | Seed, data order, effective batch, update count, LR schedule, gold/silver mixture, early-stop criterion |
| Environment | OS, GPU/VRAM, driver, CUDA runtime, Python, dependency lock, container digest |
| Evaluation | Scorer version, normalization, reference policy, threshold, bootstrap unit/seed/count |
| Chi phí | Price table + effective date, currency, actual usage, cache hits, retries, failed requests, reserved/spent budget |
| Thời gian | Start/end UTC, wall time, warm-up, synchronization policy, p50/p95 measurement sample count |

## Checklist trước chạy

- [ ] Quyền dữ liệu, external transfer và training-output đã được xác nhận phù hợp run này.
- [ ] Train/dev/test và duplicate groups không giao nhau; không đọc hidden gold khi tạo silver.
- [ ] Test chưa được dùng để chọn model/prompt/filter/router.
- [ ] Run ID duy nhất; resume không ghi đè artifact đã hoàn tất.
- [ ] Budget đủ; cấu hình chưa resolve/model revision null bị từ chối trước request trả phí.
- [ ] Số image/question thực tế, filter yield và target compute đã ghi trước.
- [ ] Fixture metric/schema và smoke run pass.

## Kết quả thực tế

Ghi N trước/sau lọc, precision/recall bộ lọc, bảng metric kèm CI, từng seed, chi phí thực, tỷ lệ fallback/từ chối/lỗi và link artifact. Không bỏ các request lỗi khỏi mẫu số tổng thể một cách im lặng.

## Diễn giải và xử lý lỗi

Điều gì được dữ liệu hỗ trợ; điều gì chưa được hỗ trợ; biến nhiễu; lỗi nổi bật; thay đổi so với preregistration; quyết định giữ/loại run. Nếu invalidated, giữ log và lý do, không tái sử dụng run ID cho kết quả mới.
