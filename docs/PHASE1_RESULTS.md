# Phase 1 — kết quả thực thi ngày 02/11/2026

**Phase 1 hoàn tất theo phương án AI chủ dự án yêu cầu, SOT v1.7/ADR-021.** [Gate G1](../artifacts/phase1/g1_ai_gate_v2.json) kiểm checksum/provenance, quyền và overlap OOD, review OCR/OOD, frozen plans và evaluator. Nhãn vẫn là AI reference, không thành human gold. Các số pipeline cũ bên dưới giữ nguyên; phần hoàn tất AI ở cuối ghi bằng chứng bổ sung. [STATUS](STATUS.md), [workflow](PHASE1_WORKFLOW.md).

## Dữ liệu và split đã freeze

SOT v1.6/ADR-020 nối mọi candidate chưa phân xử vào cùng leakage component; không coi chúng là duplicate đã chứng minh. Train chạm dev/test và dev chạm test bị quarantine. Cách này giảm retention để giữ ranh giới dữ liệu; không gỡ pending edge dựa vào test QA.

[Feature run](../data/manifests/receiptvqa_features_v1/summary.json) xử lý toàn 9.500 ảnh bằng pHash xoay/crop và gradient dHash. Có 3.360 feature pairs; union với queue gốc thành **19.496 pairs**, tạo **5.802 containment components**. Exact graph vẫn 9.465 groups. Component lớn nhất 1.872 ảnh; template có thể tạo nhiều false positives. Không tuyên bố exhaustive dedup cho mọi chụp lại/crop.

[Frozen summary](../data/splits/receiptvqa_containment_v1/summary.json), SHA `3b591e74d2c7c8515724641351017bb63b0247d940c30f5e068479cc2f30a4d9`. [Verification độc lập](../artifacts/phase1/frozen_split_verification_v1.json) kiểm đủ 9.500 ảnh/64.812 QA, zero uncontained edges/cross-partition components sau quarantine. Test reader vẫn khóa, không mở test gold. [Data card](data/RECEIPTVQA_CONTAINMENT_V1.md) ghi toàn bộ provenance/counts.

| Partition | Ảnh | QA |
|---|---:|---:|
| train_fit | 4.527 | 30.827 |
| audit_holdout | 504 | 3.454 |
| dev_select | 456 | 3.021 |
| dev_calibrate | 190 | 1.303 |
| test | 950 | 6.500 |
| quarantine | 2.873 | 19.707 |

Quarantine gồm 2.569 train + 304 dev. G5/G10/G25/G100 có 202/405/1.012/4.050 components. G10: **454 ảnh/3.053 QA**; silver: **27.774 câu hỏi không gold**. Nested budgets và pilot exclusion được kiểm tra. Source thiếu taxonomy xác nhận; phân phối keyword question-only chỉ mô tả train/dev, không gọi là gold strata. Không so split giảm dữ liệu này như full official train.

## OCR 100 ảnh và review

[OCR summary](../artifacts/phase1/ocr_quality_v1/summary.json): **100/100 ảnh, 4.587 spans, zero empty**, tất cả từ 100 G10 train_fit components. CPU 4 threads, detector max-side 960, MKLDNN/orientation/unwarping off, weights/revisions/locks Phase 0. Không thêm weights/package hoặc đổi driver/hệ thống. Inference p50 **6,706 s**, p95 **9,832 s**; peak sampled RSS **1.506.947.072 bytes**. Bao gồm inference đầu tiên; không gọi là deployment latency benchmark đã warmup.

Cache key gồm raw/canonical pixels, preprocessing/settings, language, engine/model revisions+manifest hash và package lock. Payload checksum và atomic publication; tests concurrent writers không cho ghi đè kết quả xung đột. 0 cache hits lần chạy đầu; từng entry đọc lại/checksum khớp. [Local review HTML](../artifacts/phase1/ocr_quality_v1/review.html) không cần public server.

[AI visual review](../artifacts/phase1/quality_contact_v1/visual_review.json): xem 5 contact sheets/100 thumbnails và 3 ảnh đầy đủ. Ảnh 2017 xoay 90 độ; có receipt nhỏ/faint/nhăn, merge hai giá ở 4254 và missing invoice ID. Không phải kiểm từng ký tự/bbox bằng người. [Diagnostic slices](../artifacts/phase1/quality_contact_v1/diagnostic_slices.json) dùng flags AI chồng lấp, không strata cân bằng; ảnh xoay có 0/6 exact span matches.

[AI transcription CER](../artifacts/phase1/ai_transcription_v1/cer_report.json): gõ references từ ảnh trước khi đọc OCR JSON; **38 dòng/3 ảnh, 55 edits/460 characters → CER 11,9565%**. Loại 1 dòng không chắc; 1 missing detection tính deletion. Giữ NFC/dấu/case/digits. Đây là selected readable lines, không đại diện corpus; **human_verified=false**. OCR chỉ là baseline chẩn đoán, chưa nhận chất lượng đủ cho filter high-coverage.

## Evaluator và R1

[Parity report](../artifacts/phase1/upstream_parity_v1/parity_report.json): **260 fixtures pass** qua scorer upstream SHA-pinned. Caller `.strip()` nhưng giữ newline bên trong. Protocol `ligt_5b4376b_anls_0_0_2_v1` tách strict NFC. Repo tác giả không pin anls, nên không nhận đã tái lập dependency/run bài báo. Wheel/source nhỏ nằm trong ignored artifacts, không cài vào venv.

[R1 report](../artifacts/phase1/r1_oracle_v1/report.json) trên **686 QA/100 ảnh G10 train**:

| Metric | Strict NFC | Compatible |
|---|---:|---:|
| EM / Accuracy | 58,0175% | 59,9125% |
| Token F1 | 69,9707% | 69,8839% |
| ANLS | 64,4129% | 64,9421% |

Strict EM CI95 từ 2.000 bootstrap component: **53,1850–62,5382%**. Numeric span recall **75,7353%** (408 QA), text **33,1395%** (172), hybrid **30,1887%** (106). Có **1 multipart QA**, exact miss; không suy chất lượng multipart từ một mẫu.

Oracle dùng gold chọn trong universe tối đa 4 dòng liên tiếp/24 tokens, joins space/newline/literal separator. Ưu tiên strict EM, rồi F1, ngắn/lexical. ANLS chấm span được chọn, không tối ưu ANLS riêng. **Không phải student accuracy, final benchmark hoặc cận trên tuyệt đối của VLM.** Không fuzzy sửa digit; raw full answers/part diagnostics riêng. Bootstrap theo component, paired comparison yêu cầu cùng qids, không bao gồm training variance.

## Validation và gate đã đóng theo ADR-021

Lượt containment có 35 tests mới; lượt hoàn tất AI thêm 15 tests về reference-free input, quyền/identity/quarantine, answerability/digits và adjudication. Kết quả hiện hành: **Linux 205 passed; Windows 198 passed/7 NumPy skips** (chạy đủ ở Linux). Ruff lint/format pass, **27 schemas** tái xuất. Một warning Starlette/httpx. Doctor/API readiness vẫn false vì chưa tích hợp runtime vào server; chưa GitHub CI, Docker, training, paid API hoặc hosting.

- [x] Full ingestion/record validation, exact + rotation/crop/gradient candidates.
- [x] Freeze containment, quarantine, nested plans, corpus gold/silver/test boundary.
- [x] OCR/cache 100 ảnh; profile/latency, AI visual/CER diagnostic thật.
- [x] Strict/compatible/multipart parity, bootstrap, R1 có số và span limits.
- [x] Data card, annotation contracts và [OOD protocol](OOD_ANNOTATION_PROTOCOL.md).
- [x] **OCR reference theo ADR-021:** 3 ảnh/38 dòng, local AI kiểm thêm và assistant phân xử từ ảnh; human flags giữ false.
- [x] **Bắt đầu OOD có quyền:** 3 ảnh ngoài ReceiptVQA/24 QA, rights/decode/overlap/AI review/adjudication đầy đủ.

**G1 hoàn tất theo phạm vi AI mới**, không nhận human gold hoặc full OOD benchmark. Chỉ dẫn mới của chủ dự án đã được đưa vào SOT/ADR trước chạy; artifact lịch sử không sửa. Chưa triển khai Phase 2.

## Hoàn tất phần AI và nguồn OOD

[Commons OOD seed data card](data/COMMONS_OOD_SEED_V1.md) ghi 3 ảnh với page revision/tác giả/CC0, CC BY-SA 4.0 và CC BY 2.0. Full decode và canonical file hashes được kiểm; raw bytes tổng **8.000.054**. Cross-source audit toàn 9.500 inventory có **28.500 + 3 phép so sánh, 0 candidate** theo ngưỡng đã đăng ký. Graph extension riêng tham chiếu graph ReceiptVQA; access plans và split gốc không đổi.

[Draft](../artifacts/phase1/ai_closure_inputs_v1/ood_draft.jsonl) từ ảnh có **24 QA tiếng Việt, 18 answerable/6 unanswerable**, bbox normalized, raw answers giữ nguyên digits. Hai nguồn là blank/sample tiếng Việt; một receipt ở Việt Nam in tiếng Anh. Không suy dữ liệu bị che, merchant bị cắt hoặc ngày chưa điền.

[Local review run](../artifacts/phase1/local_ai_review_v1/summary.json): Qwen3-VL-2B weights hiện có, revision cố định, NF4/BF16 GPU offline. **62 tasks = 24 OOD + 38 OCR**, không reference/draft/OCR text trong input, **0 output chạm cap 64 tokens**. Max image pixels 262.144, greedy/seed 42 chốt trước inference. Model local có lỗi số/dấu/sai trường/hallucination; assistant đã xem lại 6 ảnh gốc để phân xử. Tất cả reference draft giữ nguyên; không điều chỉnh prompt hoặc cấu hình theo OOD output.

[Final references/adjudications](../artifacts/phase1/ai_review_final_v1/provenance.json) ghi **62 quyết định** với hash output và reference cuối. OCR CER vẫn **55 edits / 460 characters, 38 dòng**, loại 1 dòng mơ hồ, một detection miss được tính deletion. OOD có **24/24** lượt AI thứ hai, cao hơn tối thiểu 20% của protocol; không tính/report OOD model accuracy. Đây là second AI pass dùng cùng student base, không human hoặc independent-model-family validation.

[G1 checker](../src/vidoclens/data/phase1_gate.py) đã chạy đạt: kiểm Pydantic/unique IDs, quyền source/image hashes, không quarantine/pending review, coverage, binding output→adjudication→reference, CER từ OCR thật, frozen plans và source parity/R1. [Report](../artifacts/phase1/g1_ai_gate_v2.json) chứa checksum evidence chain. Dataset/images/OCR/weights không commit; driver/venvs/locks không đổi, API spend 0.
