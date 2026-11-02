# ReceiptVQA — containment split v1

Ngày 02/11/2026. Dùng raw corpus và quyền research trong [data card ingestion](RECEIPTVQA_ROTATED_V1.md); không sửa ảnh/CSV hoặc cấp quyền external/public. Split freeze theo ADR-020, không phải full official-training protocol hay bằng chứng hết pretraining contamination.

## Provenance và containment

- Inventory SHA-256: `672c177c40759c776da3df2606c29c2e09adfe9aa6b8bcdc1cb802e5037be4aa`.
- Near queue: 19.391 pairs; feature rotation/crop/gradient: 3.360 pairs; union **19.496 pairs**, thêm 105 pairs.
- Exact graph giữ **9.465 groups**. Constraint graph có **5.802 components**, lớn nhất 1.872 ảnh. Không gọi mọi thành viên là cùng hóa đơn.
- Quarantine train chạm dev/test, dev chạm test: **2.569 train + 304 dev**. Official test giữ 950 ảnh/6.500 QA.
- Chưa phân xử semantic từng candidate. Containment ngăn mọi known/pending candidate edge vượt partition được sử dụng. False positives do template làm mất dữ liệu; arbitrary crop/recapture có thể chưa được phát hiện. Thêm nguồn/gỡ constraint phải tạo version mới.
- [Frozen summary](../../data/splits/receiptvqa_containment_v1/summary.json), SHA-256 `3b591e74d2c7c8515724641351017bb63b0247d940c30f5e068479cc2f30a4d9`.
- [Independent verification](../../artifacts/phase1/frozen_split_verification_v1.json): đủ 9.500 ảnh/64.812 QA, zero uncontained edge, zero cross-partition component sau quarantine; silver không gold và test reader bị khóa.

## Phân phối thực

| Partition | Ảnh | QA |
|---|---:|---:|
| train_fit | 4.527 | 30.827 |
| audit_holdout | 504 | 3.454 |
| dev_select | 456 | 3.021 |
| dev_calibrate | 190 | 1.303 |
| test | 950 | 6.500 |
| quarantine | 2.873 | 19.707 |

Tỷ lệ 90/10 và 70/30 theo component, seed 42. Pilot Phase 0 không vào audit. Tỷ lệ ảnh/QA khác component. Source không có taxonomy question type xác nhận; lưu phân phối heuristic question-only train/dev trong verification, không gọi là gold strata hoặc đọc test gold để cân bằng.

| Gold budget | Components | Ảnh | QA |
|---|---:|---:|---:|
| G5 | 202 | 221 | 1.452 |
| G10 | 405 | 454 | 3.053 |
| G25 | 1.012 | 1.122 | 7.596 |
| G100 | 4.050 | 4.527 | 30.827 |

Các tập nested theo component. G10 là nhánh chính; ngoài G10 có **27.774 câu hỏi** candidate silver. Pilot OCR lấy 100 components G10; gold chỉ mở trong evaluator, không đưa vào OCR/teacher. Freeze loader kiểm checksum plans/membership/graph; quarantine không có training gold.

## OCR/evaluator và hạn chế

PaddleOCR 3.2.0 CPU với detector/recognizer pinned trong môi trường riêng. [Quality runner](../../src/vidoclens/ocr/quality.py), [oracle runner](../../src/vidoclens/eval/phase1.py) và [STATUS](../STATUS.md) ghi kết quả thật; cache riêng tư local, không commit.

Strict NFC và compatible `ligt_5b4376b_anls_0_0_2_v1` tách biệt. 260 fixtures parity pass với scorer upstream pinned; dependency phiên bản của bài báo không rõ. Bootstrap theo component không bao gồm variance training. R1 là oracle lexical có gold trong span giới hạn, không là inference hay cận trên tuyệt đối của VLM.

Review OCR hiện AI-reviewed, chưa human-verified. OOD có quyền và gán nhãn thực còn 0. Xem [protocol review](../OOD_ANNOTATION_PROTOCOL.md); không công bố full Phase 1 hoặc human gold từ artifact tự động.
