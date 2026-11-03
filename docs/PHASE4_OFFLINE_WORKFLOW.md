# Phase 4 offline — contracts, F0/F1 và audit

Ngày: 03/11/2026. Phạm vi ADR-P4-001–002; xem [bàn giao PC](PHASE4_OFFLINE_HANDOFF.md) và [local teacher/grid/human review/comparison](PHASE4_LOCAL_TOOLS.md).
Đây là implementation CPU, chưa sinh silver thật, chưa train P1/P2 và chưa đạt G4.
Không tải model, không gọi provider, không dùng cache benchmark OpenAI để train.

## Giao diện và dữ liệu

Entry point riêng để hạn chế xung đột CLI với Phase 3:

```powershell
.\.venv\Scripts\python.exe -m vidoclens.filtering --help
```

Trên WSL thay interpreter bằng Python của môi trường đã kiểm chứng; không cài lại ML lock chỉ để chạy filter. CPU tooling dùng core + `data,teacher` extras; tests thêm `serve,dev`. Filter/evaluator/planning không import torch/Paddle; chỉ command local teacher `run` mới nạp optional ML stack.

| Contract | Nội dung / boundary |
|---|---|
| `SilverPool` | Question-only, raw image hash, duplicate group, archive/inventory/access-plan hashes; `train_fit \\ G10`, `dev_select` hoặc `audit_holdout`. G10 membership chỉ có IDs/questions, không answers |
| `SilverBatch` | Kết quả **local open-weight** của một pool chính xác; model revision bất biến, prompt/generation/environment hashes, raw-response hash từng record, `fixture_only` |
| `SilverLabel` | Answered hoặc unanswerable/refused/incomplete/parse_error/error; giữ raw answer; không có gold/reference |
| `FilterConfig` | Protocol/span bounds/ngưỡng có version; mặc định chưa calibrated; freeze gắn evidence dev, access-plan hash và fixture flag |
| `FilterRun` | Một decision mỗi qid, F0/F1, raw/normalized riêng, từng part và OCR occurrence, reason, hashes |
| `SilverApproval` | Attestation của owner cho đúng pool/batch local: quyền dữ liệu/model/training labels và quality pilot; không kế thừa grant Phase 2 |
| `SilverExperiment` | Chín selections: 3 arms × seeds 17/42/2026; cùng G10/profile/update budget, ratio 1:1, loss weights bằng nhau; luôn `training_executed=false`, `requires_g3_validation=true` |

Nguồn schema là [contracts/silver.py](../src/vidoclens/contracts/silver.py); JSON schema sinh bởi [exporter](../scripts/export_schemas.py). [Runner local teacher](PHASE4_LOCAL_TOOLS.md) tạo `SilverBatch` và giữ raw responses trong artifacts ignored khi được gọi rõ ràng trên PC qua gates. CLI filtering không chạy teacher, không chuyển `TeacherResult` của API sang local result và không chứng nhận một file tự khai báo provenance là dữ liệu thật.

`whole_answer_v1` giữ cả câu trả lời thành một part. `literal_separator_v1` chỉ tách literal `¡sep¿`; không suy multipart từ newline. Raw serialization luôn là training target, không thay bằng OCR hoặc normalized text. Khai báo part protocol trước generation/evaluation; không chọn lại theo gold để tăng điểm.

## Quy tắc F0/F1 hiện thực

- F0 giữ answered labels hợp lệ; lỗi, abstention, missing, invalid literal parts được đếm riêng. Unknown/duplicate qids, sai image hash hoặc sai pool làm fail input, không âm thầm bỏ mẫu.
- F1 tạo contiguous token windows theo reading order, tối đa 4 OCR spans/24 tokens, document cap 4096 tokens, answer cap 1024 ký tự theo default. Không giả đây là cách tìm span tối ưu. Token offsets và span IDs truy ngược về bbox trong OCR bundle.
- Matching chuẩn hóa NFC và whitespace cho evidence; giữ nguyên dấu/case/raw target. Numeric/hybrid chỉ exact whole-token match, chặn bỏ sign/currency/unit/adjacent numeric token đã đăng ký. Không có tiền tệ locale equivalence hoặc fuzzy digit edits. Không xử lý được mọi cách OCR tách punctuation/đơn vị lạ; đây là hạn chế recall cần đo trên dev.
- Text fuzzy dùng normalized Levenshtein, default minimum 6 ký tự, margin 0,05; text ngắn cần exact. So margin cả candidate thứ hai ngoài acceptance threshold. Repeated occurrences và reused/overlapping evidence giữa parts bị loại bảo thủ.
- Giá trị `τ ∈ {0, .05, .10, .15}` là search space. Minimum length, margin và bounds hiện là candidate defaults, chưa được đo trên dữ liệu thật. Không dùng audit/test/OOD để lựa chọn.
- `semantic_check=unknown`, reason `semantic_checker_not_implemented`. Có question-type heuristic chỉ để chia strata/audit. F1 không xác nhận đúng trường ngữ nghĩa; semantic verifier thuộc công việc sau.
- OCR missing/empty/error/over-limit khiến F1 reject, F0 vẫn giữ answered label hợp lệ. Mọi qid yêu cầu đều có decision, kể cả teacher không trả label.

## Lệnh trên PC sau khi khôi phục artifacts

Các đường dẫn sau là **ví dụ**, không khẳng định chúng tồn tại trên laptop. Thay bằng vị trí thực đã đối chiếu hash. Tạo thư mục cha output trước; output file/bundle phải chưa tồn tại.

```powershell
$py = '.\.venv\Scripts\python.exe'
$annotationZip = 'data/raw/ReceiptVQA_annotations.zip'
$frozenSplit = 'data/splits/containment_v1'
$imageInventory = 'data/manifests/receiptvqa/images.jsonl'

& $py -m vidoclens.filtering prepare --archive $annotationZip --frozen $frozenSplit --inventory $imageInventory --partition dev_select --output artifacts/phase4/dev_pool.json
& $py -m vidoclens.filtering prepare --archive $annotationZip --frozen $frozenSplit --inventory $imageInventory --partition train_fit --output artifacts/phase4/train_pool.json
```

`prepare` dùng frozen G10 reader hiện có, kiểm hashes và mapping, giữ nguyên split/quarantine. `audit_holdout` có thể chuẩn bị question-only, nhưng filter/audit của partition này yêu cầu rule đã freeze. Test/OOD/dev_calibrate không có chế độ truy cập ở CLI này.

Sau pilot local teacher và generation được cho phép, dùng `batch.json` từ runner hoặc adapter đúng `SilverBatch` trên PC. Các tên `dev_batch.json`, `train_batch.json` bên dưới chỉ minh họa. OCR input là JSONL, mỗi dòng một `OCRResult`, tối đa một record/document; chỉ gồm documents thuộc pool. Không dùng output teacher làm OCR evidence. Hash ảnh phải trùng pool.

```powershell
& $py -m vidoclens.filtering filter --pool artifacts/phase4/dev_pool.json --batch artifacts/phase4/dev_batch.json --ocr artifacts/phase4/dev_ocr.jsonl --config configs/filtering/f1.yaml --output artifacts/phase4/dev_filter_v1
& $py -m vidoclens.filtering audit --bundle artifacts/phase4/dev_filter_v1 --archive $annotationZip --frozen $frozenSplit --inventory $imageInventory --output artifacts/phase4/dev_audit_v1.json
```

Cách chạy từng config vẫn hỗ trợ; dùng [grid/grid-select](PHASE4_LOCAL_TOOLS.md#dev-threshold-grid-và-freeze) để tự động chạy đủ bốn ngưỡng trên **cùng dev pool/batch** và giữ selection history. Với run đơn, sau review tradeoff precision/recall/retention, đóng băng config đã chọn:

```powershell
& $py -m vidoclens.filtering freeze --config configs/filtering/f1.yaml --dev-report artifacts/phase4/dev_audit_v1.json --output artifacts/phase4/f1_frozen_v1.json
& $py -m vidoclens.filtering filter --pool artifacts/phase4/train_pool.json --batch artifacts/phase4/train_batch.json --ocr artifacts/phase4/train_ocr.jsonl --config artifacts/phase4/f1_frozen_v1.json --output artifacts/phase4/train_filter_v1
```

`freeze` xác nhận report thuộc dev_select/config tương ứng, lưu SHA256 bytes report và access-plan identity; không tự chọn quality threshold hoặc biến kết quả fixture thành hiệu chỉnh thật. Freeze bằng fixtures không áp dụng cho batch thật. Report/approval là provenance của người chạy, không là chữ ký hay sandbox chống owner sửa file.

Bundle giữ pool/batch/OCR/run/summary và manifest checksum ghi sau cùng. Loader từ chối incomplete/corrupt bundle, replay quyết định với implementation hiện tại. Đổi code/config phải tạo run mới; không sửa lịch sử. `summary` không có metric quality khi chưa mở gold qua evaluator.

Sau khi có approval local **thật** theo schema `SilverApproval` và profile/budget đã được Phase 3 kiểm chứng:

```powershell
& $py -m vidoclens.filtering select --bundle artifacts/phase4/train_filter_v1 --archive $annotationZip --frozen $frozenSplit --inventory $imageInventory --approval artifacts/phase4/local_label_approval.json --training-profile artifacts/phase3/frozen_training_profile.json --optimizer-updates 1000 --output artifacts/phase4/selections_v1
```

`1000` chỉ minh họa cú pháp: thay bằng budget chung đã chốt từ Phase 3, không dùng số này làm default khoa học. Profile được hash như opaque artifact; CLI chưa xác minh nội dung trainer/G3. Chưa có template approval điền sẵn true. Owner chỉ tạo attestation sau khi các điều kiện thực sự đạt.

`P1-size` subsample F0 bằng SHA256 rank theo seed/qid/stratum `(question_type, answer_type)`, cùng số QA mỗi stratum như F1. F1 là subset F0 nên đủ capacity cho mỗi stratum. Gold selection vẫn theo receipt/group; đây là subsample QA **trong train_fit**, không tạo split mới. Sampler/exposure training do Phase 3 thực hiện; chưa đo số lần nhìn gold hoặc chất lượng student.

Audit holdout dùng cùng commands prepare/filter/audit với config frozen. `audit` đọc gold qua evaluator riêng, yêu cầu đúng qid/document coverage; xuất correctness strict NFC EM, retention, precision/recall và bốn nhóm review. Denominator 0 là `null`. `--quality-bins path.json` nhận mapping document ID → bin do review độc lập cung cấp; phải phủ đúng pool. Nếu thiếu thì report ghi `null`, không tự đoán OCR quality từ teacher agreement. Báo cáo không tự thực hiện human audit.

## Điều kiện tích hợp và những gì chưa có

- Qwen adapter đã có code nhưng chưa smoke trên GPU/pilot; còn generation silver/OCR thật, lựa chọn threshold thật và người thực hiện human error audit. Tooling grid/review đã có, xem runbook bổ sung.
- Trainer đọc selections/targets, kiểm G3 và profile, sampler 1:1, resume, training/evaluation P1-full/P1-size/P2.
- Semantic verifier, F2/F3/correction, final test/OOD, API/serving/deploy.
- CPU tests chỉ chứng minh logic/contract bằng synthetic fixtures. Không có metric nghiên cứu hoặc quality claim mới trong lượt này.
