# OOD và transcription — quy trình review local

Ngày 02/11/2026. Quy trình đã chạy cho [Commons OOD seed v1](data/COMMONS_OOD_SEED_V1.md), **không phải tuyên bố đã có OOD human gold**. Theo chỉ dẫn tường minh mới, SOT §7.5/ADR-021 cho phép AI thực hiện phần review/annotation ở G1. Không đổi tên một subset ReceiptVQA thành OOD; không dùng nguồn khi quyền chưa được xác minh.

## Nhận và gán nhãn OOD

1. Ghi source/merchant/device/time khác biệt thực tế, người cung cấp, quyền nghiên cứu và bằng chứng quyền trong access register. Quyền external/release mặc định false. Người vận hành phải có ảnh thực và quyền, không điền bằng suy đoán.
2. Import vào cùng pipeline hash/decode; thêm nguồn vào dedup graph trước khi phát hành version split mới. Không sửa split `receiptvqa_containment_v1` đang được dùng để báo số.
3. Người gán nhìn ảnh trước, không xem OCR/teacher. Với mỗi QA ghi câu hỏi, type, answerability, full alternative answers, bbox evidence chuẩn hóa. `unanswerable` có answer/bbox rỗng; không đoán chữ mờ, chữ bị cắt hoặc suy tổng từ kiến thức ngoài ảnh.
4. Dùng `OODAnnotation` trong [review.py](../src/vidoclens/contracts/review.py); schema [OOD](../schemas/ood_annotation.schema.json). `rights_evidence_id` trỏ hồ sơ đã xác minh, không phải một string tự cấp quyền. Các record AI ghi `annotator_type=ai`, không đủ điều kiện human gold.
5. Đối với human gold ở phase nghiên cứu/release: ít nhất 20% QA có người thứ hai kiểm tra độc lập; một người thì kiểm tra trễ với nhãn cũ bị che và ghi hạn chế. **Ngoại lệ G1 được chủ dự án yêu cầu:** ít nhất 20% QA có AI local reference-free kiểm tra thêm, sau đó assistant phân xử từ ảnh. Không gọi đó là human inter-annotator agreement. Record pending không đóng gate; output model không tự trở thành reference.
6. Kiểm tra overlap với tất cả train/silver/benchmark; giữ OOD ngoài tuning. Freeze IDs/answers/evidence/rights hashes trước final suite Phase 5–7. Không gửi public hoặc API như một phần của review local.

## Review OCR đã chuẩn bị

Mở [review local](../artifacts/phase1/ocr_quality_v1/review.html) sau khi runner hoàn tất. Ảnh hiển thị trước, OCR nằm dưới phần mở rộng để tránh dẫn nhãn. Không cần web server hoặc hosting. [Selection](../artifacts/phase1/ocr_quality_v1/selection.json) chỉ chứa ảnh G10 train_fit, không có gold QA.

Reference dùng [TranscriptionReview](../schemas/transcription_review.schema.json): image/OCR hashes, reviewer type, blind-to-OCR flag, coverage và từng line. Phải đối chiếu lại từ ảnh, không chỉ đổi `reviewer_type` trên bản AI. Với dòng thiếu detection, dùng `missing-<id>` và transcription thật; scorer tính prediction rỗng. Dòng không chắc đánh dấu `uncertain`, loại khỏi CER và báo số loại. CER NFC, giữ nguyên dấu/case/khoảng trắng/digits; báo numerator/denominator và coverage. Không gọi CER trên một số dòng rõ là CER đại diện corpus.

```powershell
.\.venv\Scripts\python.exe -m vidoclens.eval.transcription --reviews artifacts/phase1/ai_transcription_v1 --ocr-dir artifacts/phase1/ocr_quality_v1 --output artifacts/phase1/cer_new.json
```

Lệnh từ chối ghi đè evidence. References AI hiện tại được gõ từ ba ảnh trước khi xem OCR JSON, sau đó nối với vị trí/dòng OCR. [CER report](../artifacts/phase1/ai_transcription_v1/cer_report.json) giữ riêng provenance AI; chưa có người kiểm tra. Đây là phần assistant có thể tự thực hiện theo yêu cầu, không phải bằng chứng đã có nhân sự hoặc ảnh OOD mới.

## Đã thực hiện tại G1 và giới hạn còn lại

- OCR: 3 ảnh/38 dòng readable, 1 dòng uncertain bị loại; model local kiểm tra 38 dòng, assistant phân xử từ ảnh; CER AI 55/460, không thay corpus/human CER.
- OOD: 3 ảnh có giấy phép nguồn/24 QA, 18 answerable và 6 unanswerable; 24/24 local second pass và adjudication, source image/bbox/raw answer hashes được khóa.
- Contracts [AI review](../src/vidoclens/contracts/ai_review.py) tách input không reference, output và quyết định cuối; QA mang `ai_reference`, không train/confirmatory evaluation/human gold. [Gate](../artifacts/phase1/g1_ai_gate_v2.json) đạt theo phạm vi mới.
- Human-verified records vẫn **0**. Full OOD/human validation cho kết luận nghiên cứu và release còn ở phase sau. Seed có same-base AI exposure, convenience sampling và tiếng Anh; không biến thành final holdout hoặc dùng chọn prompt/filter/router.
