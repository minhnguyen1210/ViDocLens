# Nhật ký quyết định

Ngày khởi tạo: 02/11/2026. [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) là quy định hiện hành; ADR ghi lý do và lịch sử. Khi có xung đột, sửa cả hai trong cùng thay đổi trước khi tiếp tục phần phụ thuộc.

| ID | Trạng thái | Quyết định | Lý do / hệ quả |
|---|---|---|---|
| ADR-001 | Chấp nhận | Một tài liệu chuẩn: `SOURCE_OF_TRUTH.md`; overview được bảo toàn làm lịch sử | Không duy trì hai bản thiết kế có thẩm quyền ngang nhau |
| ADR-002 | Chấp nhận | Modular monolith Python; FastAPI phục vụ API, Gradio phục vụ demo | Phù hợp một người triển khai và một GPU; giữ module boundary để thay backend |
| ADR-003 | Chấp nhận | Tách pipeline offline khỏi request online | Huấn luyện, OCR corpus và sinh nhãn không chạy trong lifecycle request |
| ADR-004 | Chấp nhận | JSONL cho record trao đổi, Parquet cho phân tích lớn, SQLite cho ledger/cache metadata | Truy vết đủ dùng; chưa cần hệ thống phân tán hay vector database |
| ADR-005 | Chấp nhận | OCR support là bằng chứng phụ trợ, không phải chứng nhận đáp án đúng | Chuỗi có trên ảnh vẫn có thể thuộc sai trường; OCR cũng có lỗi |
| ADR-006 | Chấp nhận | Mặc định `local`, external off; yêu cầu cho phép gửi dữ liệu tường minh | Cascade không được tự gửi ảnh ra ngoài khi local yếu hoặc gặp lỗi |
| ADR-007 | Chấp nhận | Không huấn luyện từ output dịch vụ khi quyền sử dụng chưa rõ | Tách quyền inference và quyền dùng output cho student; ý kiến người hướng dẫn không thay thế điều khoản áp dụng |
| ADR-008 | Chấp nhận | Test/OOD chỉ dùng sau khi đóng băng cấu hình | Tránh lựa chọn prompt, threshold hoặc checkpoint từ kết quả test |
| ADR-009 | Chấp nhận | Release gồm base model + adapter + processor + verifier + schema + config tương thích | Rollback cả bundle, tránh ghép adapter với sai base revision |
| ADR-010 | Chờ đo | Chọn student/OCR chính | Tên candidate trong config không chứng minh tương thích, chất lượng hay vừa VRAM |
| ADR-011 | Chờ chốt | Snapshot teacher, giá token, trần ngân sách | Chốt từ pilot và quyền truy cập thực; không ghi giá/khả năng model bằng suy đoán |
| ADR-012 | Chấp nhận — 02/11/2026 | Adapter ReceiptVQA giữ raw CSV, dùng qid có namespace dataset/version + image_id/question_id; chưa tự chuyển newline thành `¡sep¿` | Audit ZIP hash `226f7dcc6421115da254b2809dc9ebfd138be0c2f175a9c1c12f7a46ae6127ea`: question_id lặp giữa ảnh, cột index reset theo split, train có 879 answer chứa newline và 0 literal separator; SOT §11.1 đã bổ sung, scorer parity vẫn mở |
| ADR-013 | Chấp nhận — 02/11/2026 | Định vị đóng góp là thực nghiệm có kiểm soát; không nhận novelty riêng cho validated distillation/cascade | Matrix 12 công trình trong LITERATURE, đặc biệt DocVAL; SOT §4 cập nhật. Hidden gold vẫn không vào teacher/filter; không đổi RQ hoặc bắt buộc train CoT |
| ADR-014 | Chấp nhận phương án, candidate chưa kiểm chứng — 02/11/2026 | Nhánh label teacher local Qwen3-VL-4B-Instruct khi quyền output API chưa rõ; load luân phiên với student | Model card/API khai báo Apache-2.0; access register ghi observed revision và gate. SOT §10.4 cập nhật. Chưa tải weights, chưa cấp quyền ảnh, chưa bật API; nếu pilot fail giữ gold-only và RQ2 chưa hoàn tất |
| ADR-015 | Chấp nhận — 02/11/2026 | Loader annotations dùng question contract không trường gold, manifest theo receipt/group gắn archive hash; gold training và gold evaluator tách API | SOT §7.4; source labels không bị serialize sang teacher/silver. Manifest phủ toàn selected split; test chưa mở trước frozen runner. Chưa tạo split thực hoặc coi receipt-only grouping là image dedup |
| ADR-016 | Chấp nhận — 02/11/2026 | Triển khai `strict_nfc_v1` với multiset F1, ANLS ngưỡng strict 0,5, max full references; missing/abstain/error giữ denominator | SOT §14.1; scorer nguồn tại commit cố định có set F1/mean references nên khác protocol. Official parity vẫn mở; giữ metric dự án và metric nguồn tách tên, không đổi primary EM |
| ADR-017 | Chấp nhận cho pilot kỹ thuật — 02/11/2026 | Dùng rotated_images.zip chính thức, mapping aliases đuôi file tường minh; chọn train pilot theo exact-byte groups tránh dev/test | Chủ dự án cho phép tải/cài. Hash/source và 7 aliases đã lưu; 15 nhóm trùng xuyên split cần quarantine 19 ảnh train theo SOT §7.3. Chưa nhận official preprocessing parity hoặc coi byte dedup thay near-dedup; SOT §7.2 cập nhật |
| ADR-018 | Chấp nhận profile feasibility — 02/11/2026 | Khóa stack inference Linux Python 3.11.14: Torch 2.8.0+cu126/vision 0.23.0+cu126, Transformers 4.57.1, PEFT 0.17.1, Accelerate 1.10.1, bitsandbytes 0.48.1; OCR CPU riêng Paddle/PaddleOCR/PaddleX 3.2.0 | Student NF4/BF16 và OCR v5 Việt chạy 20 ảnh train; hai venv mới từ hash locks khớp packages và 20/20 outputs. SOT §6/§22 và runbook cập nhật. G0 đạt; 7 student outputs chạm cap, OCR có lỗi dấu/tách dòng. Chưa chốt chất lượng OCR/student (ADR-010), chưa QLoRA train hoặc deploy; API readiness vẫn false |
| ADR-019 | Chấp nhận bước đầu Phase 1 — 02/11/2026 | Ingestion versioned raw/EXIF-RGB pixel hashes; nối exact byte/pixel graph, pHash full/crop chỉ đưa vào review; split đầu ra là `SplitDraft` không cấp quyền train | Không được freeze khi near-dedup chưa review. Quarantine xuyên official split, pilot groups không vào audit; nested gold IDs chỉ là dự kiến. Không materialize/re-encode toàn corpus hoặc giả có derivative file. SOT §7.3/§7.4 cập nhật; pHash không chứng minh hết leakage hoặc thay matching OCR/feature đầy đủ |

## ADR-020 — Containment bảo thủ và evaluator Phase 1

Chấp nhận triển khai ngày 02/11/2026 theo yêu cầu hoàn thiện Phase 1. Nối candidate chưa chắc vào leakage component, không nhận là duplicate đã chứng minh; exact graph và pending queue bất biến. Quarantine component xuyên official splits trước train. Đổi lại có thể mất nhiều dữ liệu do cùng template; báo riêng counts và giữ version split. Bổ sung feature rotation/crop với thresholds định trước trong SOT §7.4. Không dùng test QA để chọn thresholds. `conservative_candidate_graph` là grouping status mới; final plan không giả review con người. OCR dùng G10 train_fit sau freeze, không audit/calibration/test. User yêu cầu assistant tự review; các annotations này ghi AI-reviewed, không đóng yêu cầu human gold/OOD bằng nhãn AI. Scorer tương thích có tên commit + anls 0.0.2, giữ strict riêng và không tuyên bố tái lập dependency không pin của bài gốc.

## ADR-021 — Hoàn tất Phase 1 bằng AI, không nhận là human gold

Chấp nhận ngày 02/11/2026 theo chỉ dẫn tường minh mới: “sử dụng AI để hoàn thành toàn bộ phase 1”. Thay blocker human tại Phase 1 bằng AI review/reference có provenance và model local reference-free kiểm thêm; human flags giữ false. SOT §7.5 đặt tối thiểu 3 ảnh/30 dòng OCR review, 3 ảnh OOD có quyền/18 QA và 20% second AI review trước đóng gate. OOD seed phải ngoài ReceiptVQA, dedup với toàn corpus, giữ riêng khỏi train/tuning, có raw answers/bbox/answerability. Không biến sample/synthetic receipt thành giao dịch thật, không đánh giá/tune model trên OOD. Nguồn Wikimedia Commons có điều kiện giấy phép lưu theo từng file; tổng tải nhỏ, không API trả phí/weights mới. Human gold/full OOD validation ở phase sau không được tự nhận đã hoàn thành. Quyết định này thay riêng yêu cầu chờ human để đóng Phase 1 trong ADR-020, không thay mọi ràng buộc nghiên cứu/release của SOT.

**Bằng chứng thực thi ADR-021:** [G1 report](../artifacts/phase1/g1_ai_gate_v2.json) đạt; [Commons seed](data/COMMONS_OOD_SEED_V1.md) có 3 ảnh/24 QA và zero overlap candidates theo protocol; 38 dòng OCR và 24 QA có local second pass + 62 adjudications. Linux 205 tests/Windows 198 + 7 skips, 27 schemas. SOT v1.7 công nhận hoàn tất G1 theo phạm vi AI, giữ human/final OOD flags false và mọi artifact lịch sử bất biến.

## ADR-022 — Quản lý trạng thái và GitHub thủ công

Chấp nhận ngày 02/11/2026 theo yêu cầu nâng cấp repo và chỉ dẫn chủ dự án tự push. Giữ STATUS ngắn, có bảng 8 phase, queue task, blocker/owner/điều kiện gỡ, validation và bàn giao; lưu lịch sử cũ riêng, không đổi scientific evidence. CONTRIBUTING quy định task lifecycle, branch `codex/`, Conventional Commits, staged review và push thủ công; CHANGELOG theo phiên bản, Issue/PR templates phục vụ review. Local done/commit/push/CI/release là các trạng thái khác nhau. Bổ sung schema `--check` không ghi file và file policy names/sizes + YAML validation; chúng không là secret scan hoặc bằng chứng model/deploy. CI read-only không publish. SOT v1.8 §19.3 cập nhật cùng quyết định. Không đổi phase gates, môi trường ML, driver hoặc quyền dataset/teacher.

Bằng chứng ADR-022: Linux **223 passed**, Windows **216 passed/7 skipped**, Ruff lint/format đạt, 27 schemas match; 32 Markdown được kiểm UTF-8/liên kết local. File policy/YAML check đạt; index chưa có staged file nên chưa chứng nhận commit sẵn sàng. GitHub CI chưa xác minh chạy. Không có stage/commit/push hoặc thay remote trong lượt nâng cấp.

## Mẫu ADR tiếp theo

```text
ID / ngày / người quyết định:
Trạng thái: đề xuất | chấp nhận | thay thế | bác bỏ
Vấn đề cần giải quyết:
Các lựa chọn đã xét:
Quyết định:
Bằng chứng (run ID / tài liệu / URL + ngày truy cập):
Tác động dữ liệu, chi phí, chất lượng, bảo mật:
Phần SOT / config / schema bị thay đổi:
Điều kiện cần xem xét lại:
Thay thế ADR nào:
```

Những thay đổi bắt buộc có ADR: đổi bài toán chính, nguồn gold, split, preprocessing metric, teacher/student, policy dữ liệu ra ngoài, tiêu chí nhận release hoặc cắt một đầu ra cam kết.
