# Loader annotations và metric CPU

Ngày: **02/11/2026**. Phần §§1–5 mô tả implementation/history ban đầu; cập nhật Phase 1 ở §7. G0 đã đạt, split containment và scorer parity đã chạy; trạng thái tổng thể xem STATUS.

## 1. Chạy ngay trên archive hiện có

Từ repository root:

```powershell
.\.venv\Scripts\python.exe -m vidoclens.data.receiptvqa --archive data/raw/receiptvqa/ReceiptVQA_annotations.zip --split train
.\.venv\Scripts\python.exe -m vidoclens.data.receiptvqa --archive data/raw/receiptvqa/ReceiptVQA_annotations.zip --split dev
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_receiptvqa_loader.py tests/unit/test_metrics.py
```

CLI chỉ in số QA/receipt, hash nguồn và trạng thái output; không xuất JSONL chứa câu hỏi/đáp án. Reader parse CSV trực tiếp từ ZIP, giữ raw bất biến, không extract. Input sai trả exit 2 với thông báo không chứa payload. `--split test` không được hỗ trợ trong CLI hiện tại.

Kiểm tra gồm header/cell bắt buộc, ID số canonical, source index, composite qid, mapping ID↔filename, CRC member được chọn, ZIP member whitelist, UTF-8 và giới hạn 64 MiB. Reader train/dev không mở member CSV test. Audit cả archive/cross-split IDs vẫn là lệnh `vidoclens.data.audit_receiptvqa`; kiểm tra selected split không thay kiểm tra toàn corpus.

## 2. API và ranh giới gold

| API Python | Đầu ra | Quyền đọc nhãn |
|---|---|---|
| `data.receiptvqa.load_questions(path, split="train")` | Tuple `ReceiptQuestion` | Không có trường gold/answer; view ingestion, chưa phải tập train/silver đã chia |
| `data.receiptvqa.load_silver_questions(path, plan)` | Câu hỏi thuộc `train_fit` ngoài gold groups | Không có trường gold/answer |
| `data.receiptvqa.load_training_examples(path, plan)` | `SupervisedReceiptExample(question, reference)` | Chỉ `train_fit` có `gold_for_training=true` |
| `eval.receiptvqa_gold.load_evaluation_gold(path, plan, partition=...)` | `GoldReference` | Chỉ `audit_holdout`, `dev_select`, `dev_calibrate`; không phải đầu vào teacher |

Không có tham số `include_gold=True` dùng chung cho reader. `test`/`ood` và yêu cầu dùng `train_fit` qua gold evaluator bị chặn; chưa có API mở test theo boolean override. Final test runner với frozen manifest là công việc sau này.

`ReceiptQuestion` giữ raw question và bản NFC riêng, filename tham chiếu, IDs nguồn và archive hash. Qid có dạng `receiptvqa:<archive_sha256>:image:<image_id>:question:<question_id>`; source index không tham gia identity. Đổi archive bytes → namespace mới. Không giả hash ảnh, width/height hoặc duplicate groups; chưa tạo `Document` khi chưa có ảnh.

Gold được giữ **nguyên một chuỗi đầy đủ** trong `GoldReference.answers`, kể cả leading/trailing spaces, quoted CRLF/newline hay literal `¡sep¿`. Tuple `answers` biểu diễn các đáp án đầy đủ thay thế, không phải các phần của cùng đáp án. Reader không tự tách newline, thay delimiter hoặc chuẩn hóa giá trị tiền.

Các contracts mới nằm trong [dataset.py](../src/vidoclens/contracts/dataset.py) và [evaluation.py](../src/vidoclens/contracts/evaluation.py), được export bởi [export_schemas.py](../scripts/export_schemas.py). Chúng immutable ở cấp field và cấm trường dư. Loader/scorer revalidate object ở boundary để tránh vô tình dùng `model_copy(update=...)` bỏ qua validation.

## 3. Manifest cấp quyền cho từng receipt/group

`ReceiptAccessPlan` bắt buộc có SHA-256 đúng archive, `grouping_status` và tuple assignments. Mỗi assignment có `source_image_id`, official split, `duplicate_group_id`, partition và cờ gold training mặc định false.

- Manifest phải phủ **đúng toàn bộ image IDs của split được đọc**, không chấp nhận allowlist thiếu receipt hoặc IDs không tồn tại.
- Mỗi receipt xuất hiện một lần; tất cả QA của receipt kế thừa cùng policy.
- Cùng duplicate group không được chia khác partition hoặc khác gold selection.
- Chỉ official train được chia `train_fit`/`audit_holdout`; dev chỉ `dev_select`/`dev_calibrate`; test không thể gán thành train.
- `gold_for_training=true` chỉ hợp lệ ở `train_fit`; teacher/silver bỏ toàn bộ groups này.

Chưa tạo manifest train/dev thực trong tác vụ này vì chưa có image dedup và quarantine pilot. `receipt_only` dùng để phát triển/test boundary; không phải bằng chứng hết near-duplicate hay cấp phép chạy benchmark. `image_dedup_verified` là provenance do pipeline cung cấp, không phải cờ có thể tự chứng minh dedup. Phần tạo manifest, tỷ lệ 90/10 và 70/30, nested gold budgets vẫn theo SOT và sẽ triển khai cùng G1.

Ví dụ dùng **sau khi có manifest thật được kiểm tra**; file minh họa dưới đây chưa được tạo:

```python
from pathlib import Path
from vidoclens.contracts.dataset import ReceiptAccessPlan
from vidoclens.data.receiptvqa import load_silver_questions, load_training_examples

archive = Path("data/raw/receiptvqa/ReceiptVQA_annotations.zip")
plan = ReceiptAccessPlan.model_validate_json(
    Path("data/splits/receiptvqa_access_plan.json").read_text(encoding="utf-8")
)
silver_inputs = load_silver_questions(archive, plan)
supervised_examples = load_training_examples(archive, plan)
```

Gold protection là ranh giới API/serialization và quy trình phát triển, **không phải sandbox/ACL chống người có quyền filesystem**. ZIP nguồn vẫn có cột answer và parser tin cậy phải đọc CSV để bỏ cột này. Không truyền `_SourceRow`, `GoldReference`, `SupervisedReceiptExample` hoặc toàn bộ manifest/log gold vào teacher. `repr` gold được ẩn, nhưng `model_dump()` trên record gold là thao tác có quyền và vẫn chứa nhãn; không log record đó.

## 4. Protocol `strict_nfc_v1`

Các hàm trong [metrics.py](../src/vidoclens/eval/metrics.py) dùng Python stdlib, không tải scorer/package ngoài:

| Hàm / metric | Định nghĩa |
|---|---|
| `exact_match` / `strict_nfc_em` | So chuỗi sau NFC; giữ casing, whitespace, dấu tiếng Việt, dấu tiền tệ và digits |
| `token_f1` / `strict_nfc_token_f1` | NFC → `str.split()` → multiset token overlap bằng Counter; `2*overlap/(len(pred)+len(ref))` |
| `anls` / `strict_nfc_anls` | NFC → Levenshtein theo Unicode code points; chia max length; nhận `1-d` chỉ khi `d < 0.5` |
| `score_answer` | Lấy max riêng từng metric trên các **full alternatives**; `None` prediction = 0; reject reference set rỗng/reference blank |
| `evaluate_answers` | Join bằng qid, QA-weighted mean; reject duplicate/unknown qid; prediction thiếu vẫn giữ trong denominator |

Hàm pairwise định nghĩa empty/empty = 1, một bên empty = 0; F1 tính emptiness sau whitespace split. Corpus ReceiptVQA hiện tại là answerable: `GoldReference` không cho blank gold; abstain/error/missing đều 0 trên toàn bộ metrics. Zero answered → `selective_em=null`, coverage = 0. Tất cả scores ở thang **0–1**, không phải phần trăm. Chưa hỗ trợ scorer riêng cho unanswerable OOD.

Ví dụ fixture tính tay: `125.001` so `125.000` có EM/F1 = 0 nhưng ANLS = 6/7. ANLS partial credit không chứng nhận số đúng và không được dùng để sửa digit. `ab` so `ac` có normalized distance = 0,5 nên ANLS = 0. `a a` so `a` có multiset F1 = 2/3. Full answer nhiều phần phải được so như một chuỗi theo raw serialization; không cho điểm EM chỉ vì đúng một part.

`AnswerPrediction` chỉ có qid/status/raw answer; chưa cần giả provenance model để kiểm tra metric. `EvaluationSummary` ghi `official_compatible=false`, số answered/abstained/error/missing, coverage và selective EM. Validator chặn report có mẫu số/status counts mâu thuẫn. Đây chưa phải experiment report đủ nguồn/run/model hash; runner sau này phải bổ sung provenance.

## 5. Kết quả đọc scorer tác giả và giới hạn parity

Đã đọc bốn file nguồn tại commit `5b4376b455ed82e16b2285fca5d8b4b25ee3a3af`, ngày 02/11/2026:

- [accuracy.py](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/evaluation/accuracy/accuracy.py): so raw strings, trung bình trên references; vòng lặp đi theo prediction keys.
- [f1.py](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/evaluation/f1/f1.py): whitespace split, giao **set** token nhưng mẫu số dùng độ dài token list, trung bình references. Ví dụ hai chuỗi `a a` giống nhau vẫn cho 0,5 theo công thức code này; protocol dự án dùng multiset nên cho 1.
- [anls_metric.py](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/evaluation/anls_metric/anls_metric.py): gọi package `anls.anls_score` với threshold 0,5; chưa khóa/kiểm tra nội dung dependency áp dụng trong run tác giả.
- [evaluation/__init__.py](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/evaluation/__init__.py): ghép các scorer, không tự chứng minh preprocessing phía caller.

[Paper §5.2](https://arxiv.org/html/2502.19202v1) là nguồn công thức tham khảo. Không copy hoặc execute code upstream trong tác vụ này, không cài NumPy/anls. Còn thiếu preprocessing caller, dependency version, multi-part serialization và đối chiếu end-to-end. Vì vậy **chưa có `official_compatible` implementation**; không so điểm `strict_nfc_v1` trực tiếp với bảng R0. Các khác biệt trên được giữ rõ thay vì sửa ngầm để tạo cảm giác parity.

## 6. Phần chưa triển khai

Lịch sử lúc loader đầu tiên được viết: chưa có image pipeline/OCR/scorer parity. Những phần đó đã được triển khai trong Phase 1 (§7); train/teacher và final frozen test runner vẫn thuộc các phase sau. Không coi fixture pass là kết quả model.

## 7. Cập nhật Phase 1 — 02/11/2026

`ReceiptAssignment` có `quarantine` cho train/dev, luôn không có training gold. Group validator cho phép quarantined members cùng component với heldout; các member còn sử dụng phải cùng partition/gold policy. `ReceiptAccessPlan.grouping_status=conservative_candidate_graph` cần inventory/graph hashes. Dùng `data.freeze.load_frozen_plan(Path("data/splits/receiptvqa_containment_v1"), 10)` thay file ví dụ ở §3. Draft vẫn bị loader reject. Bằng chứng thực: [split verification](../artifacts/phase1/frozen_split_verification_v1.json).

Metric [compatible.py](../src/vidoclens/eval/compatible.py) đặt tên `ligt_5b4376b_anls_0_0_2_v1`. Đã đọc caller `base_executor._evaluate_metrics`: `.strip()` prediction/reference, giữ newline bên trong, wrap một full answer; không đổi newline thành `¡sep¿`. Upstream ANLS 0.0.2 lowercases/collapses whitespace và dùng denominator độ dài sau upper; khác strict NFC. Dependency `anls` của repo tác giả không pin nên **không biết chắc version của run bài báo**. Không đổi primary strict EM hoặc tuyên bố tái lập R0.

[Parity report](../artifacts/phase1/upstream_parity_v1/parity_report.json) chạy **260 fixtures** qua Accuracy/F1/ANLS upstream SHA-pinned và implementation dự án: khớp per-sample ở tolerance 1e-12. Wheel được tải vào ignored artifacts, không cài vào hệ thống; script kiểm SHA trước execute. Các file caller được đọc/hash, không chạy full training executor.

Grouped bootstrap, paired qid guard, bounded OCR oracle và CER ở `src/vidoclens/eval`. R1 chỉ được mở 100 ảnh G10 train_fit ở pilot. Nhãn và raw predictions nằm trong ignored artifacts, không log gold hoặc truyền teacher. CER AI và CER human tách provenance, không gộp để nhận human quality.
