# Protocol để đóng phần thực nghiệm Phase 0

Ngày lập/cập nhật: **02/11/2026**. Đã thực thi sau khi chủ dự án cho phép cài/tải và reboot. 20 mẫu train được chọn trước theo exact-byte groups/seed 42, không chạm dev/test; đã xem contact sheet thấy ảnh dài, mờ/chữ nhỏ, nghiêng/nhăn và dấu tiếng Việt, không thay mẫu theo output. OCR CPU/student NF4 GPU đã chạy; xem [STATUS](STATUS.md) cho bằng chứng gate, [runbook](PHASE0_ENVIRONMENT.md) cho lệnh và locks. Đây vẫn là pilot kỹ thuật, không phải mẫu được phân tầng đại diện benchmark.

## 1. Dữ liệu pilot

1. Chốt raw hay rotated theo protocol nguồn trước tải; lưu URL/revision, license, bytes/hash, CRC và mapping filename. Không tự coi hai archive tương đương; bộ ảnh lớn hơn không mặc nhiên tốt hơn.
2. Tạo danh sách pilot từ official **train** bằng seed 42 sau exact-duplicate grouping, 20 receipts, một câu hỏi hợp lệ/receipt; ghi IDs/hash local. Tách và quarantine các nhóm đã dùng để lựa chọn kỹ thuật khỏi `audit_holdout` sau này, để không gọi audit là held-out khi đã xem. Không dùng test; bước chọn ảnh không đọc đáp án.
3. Bảo đảm pilot có receipt dài, chữ nhỏ, mờ, xoay và dấu tiếng Việt nếu dữ liệu train có các trường hợp đó. Nếu bổ sung mẫu khó có chủ đích, ghi cách chọn; không gọi đây là mẫu ngẫu nhiên đại diện.
4. Runtime chỉ nhận image/question; evaluator hoặc người kiểm tra đọc gold riêng. Gold không được copy vào prompt, OCR correction hay postprocessing.

Phase 0 dùng mẫu nhỏ để kiểm tra kỹ thuật. Pilot chọn OCR 100 ảnh, dedup đầy đủ và evaluator parity thuộc G1; không gọi inference 20 ảnh là benchmark chất lượng.

## 2. Môi trường và model

Thực hiện các gate A–D trong [ENVIRONMENT_SETUP_PLAN](ENVIRONMENT_SETUP_PLAN.md): Linux/WSL2 nhận GPU, Python 3.11 riêng, Torch CUDA matmul/import và OCR CPU. Chưa cần Docker. Không thay driver nếu chưa có bằng chứng bắt buộc.

- Student: candidate Qwen3-VL-2B-Instruct, revision immutable và processor cùng phiên bản; batch 1, pixel cap 262.144, giới hạn output 128 tokens cho smoke; lưu mọi override so với config training. NF4 chỉ coi hoạt động nếu module/device thực xác nhận.
- OCR: candidate PaddleOCR recognizer tiếng Việt, CPU; kiểm tra mapping `vi` đúng version, không chỉ import thành công. Lưu detector/recognizer names, hashes, revisions và language.
- Không nạp teacher 4B cùng student. Teacher local là pilot riêng khi cần nhánh labels, chưa là điều kiện phải tải để kiểm tra student đầu tiên.

## 3. Chạy và ghi số đo

Một warm-up riêng, sau đó chạy 20 mẫu đã chọn, concurrency 1. Đồng bộ CUDA trước/sau đo bằng đồng hồ monotonic; reset peak counters sau load để phân biệt memory load/inference. Ghi cold load, warm latency từng mẫu, p50/p95, peak allocated/reserved, RAM/VRAM hệ thống, input dimensions/image tokens, output tokens, exceptions/truncations và cấu hình device/dtype thực. Không ghi QA/ảnh vào console hoặc log public.

Artifacts thực ở `artifacts/phase0/student_nf4_01/`, `ocr_cpu_01/` và các lượt dựng lại `student_nf4_repro_02/`, `ocr_cpu_repro_02/`; mỗi runner có environment/profile, pilot manifest, per-sample files và summary riêng. Run tái lập giữ source snapshot; hash của runner, input và model được ghi. Evidence tổng hợp không PII ở STATUS; qualitative review riêng ở `artifacts/phase0/ocr_visual_review.json`, không sửa raw result.

## 4. Điều kiện đạt và không đạt

| Gate | Đạt khi | Hiện tại |
|---|---|---|
| Ảnh + gold | Nguồn có quyền, ảnh decode được, mapping pilot với QA đúng, test không dùng chọn cấu hình | Đã có 20 ảnh train decode và manifest không gold; mapping aliases được ghi |
| GPU student | Có generation thực trên GPU qua pilot; không OOM, không CPU fallback bị che; report đầy đủ | 20/20 generation thực; 7 đầu ra chạm cap 128; chưa accuracy |
| OCR Việt | Có text/bbox/confidence thực, kiểm tra trực quan dấu và số; lỗi được lưu, không gán CER khi thiếu OCR gold | 20/20 có text/box/confidence; đã review trực quan, có lỗi dấu/tách dòng |
| Tái tạo | Ghi Python/OS/driver/wheel sources/package hashes/revisions; resolve lock và dựng lại sạch, smoke pass | Có hai hash locks và venv mới khớp freeze; kết quả chạy lại ở STATUS |
| Nhánh labels | Điều kiện API rõ hoặc teacher local có quyền/plan cụ thể; không đưa output chưa được phép vào train | Có phương án local; chưa pilot |

OCR/student trả text không đồng nghĩa trả đúng. Không đặt ngưỡng accuracy tùy ý chỉ để pass smoke. Nếu fail ghi lỗi tái hiện và dừng tại gate; không hạ gate hoặc sửa test labels.

Train smoke 50–100 updates, loss-mask, save/load adapter là bước feasibility bổ sung/G3; inference pass chưa chứng minh QLoRA train được. Không bắt đầu full training trong Phase 0.

## 5. Công việc làm được ngay khi giữ nguyên hệ thống

Audit annotations có thể chạy lại theo [scripts README](../scripts/README.md). [Boundary loader và metric fixtures](ANNOTATION_LOADER_AND_METRICS.md) đã triển khai trên Windows như phần độc lập của Phase 1. Tests CPU riêng không chứng minh G0; kết luận gate dựa thêm vào artifacts OCR/GPU và dựng lại môi trường trong STATUS.
