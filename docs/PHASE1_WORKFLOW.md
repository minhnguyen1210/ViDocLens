# Phase 1 — ingestion, chống leakage và evaluator

Ngày bắt đầu/hoàn tất: **02/11/2026**, sau khi tái kiểm tra G0. [SOT v1.7](../SOURCE_OF_TRUTH.md) và ADR-019/020/021 quy định phạm vi; [STATUS](STATUS.md) ghi kết quả chạy. Có split containment đã freeze, tách khỏi draft lịch sử. **Phase 1 đã hoàn tất theo phương án AI mới**, nhãn không là human gold/final OOD benchmark.

## Thứ tự thực thi và gate

| Bước | Đầu ra / điều kiện |
|---|---|
| 1. Ingestion ReceiptVQA | Audit annotation structure, filename mapping, CRC/full decode, raw SHA-256, canonical pixel SHA-256, EXIF/dimensions và fingerprint; không xuất QA/gold |
| 2. Dedup và quarantine | Exact byte/pixel graph; review pHash/feature/OCR candidates; kiểm tra duplicate xuyên official split; không gộp hai hóa đơn chỉ vì cùng template |
| 3. Freeze split | Sau review, phát hành manifest có hash, audit holdout không chứa nhóm đã dùng pilot, dev_select/calibrate tách nhau, G5⊂G10⊂G25⊂G100 theo group; kiểm tra gold loader với quarantine |
| 4. OCR pilot/cache | Tối thiểu 100 ảnh train/dev_select; đánh giá span recall, số, reading order và CER trên subset có transcription/review thật; cache key gồm đủ image/preprocess/model/lock hashes |
| 5. Evaluator/R1 | Đối chiếu scorer upstream và serialization nhiều phần; strict metrics tách official-compatible; bootstrap theo receipt group; R1 lexical oracle có giới hạn span rõ |
| 6. OOD/data card | Nhập seed có quyền, cross-source audit, gán nhãn từ ảnh và local AI kiểm thêm theo ADR-021; adjudication, provenance, bbox/answerability và data card |

ADR-020 bổ sung nhánh freeze bảo thủ: mọi candidate chưa phân xử đều là constraint chung component. Không cần tự nhận chúng là duplicate thật hoặc đã review hết; đổi lại phải quarantine toàn component chạm heldout. Nhánh này giữ 4.527 ảnh train_fit, 504 audit, 456 dev_select, 190 dev_calibrate, 950 test và 2.873 quarantine. Gold G10 là 405 components/3.053 QA; silver 27.774 câu hỏi không gold. Hạn chế mất dữ liệu do template được báo rõ; review tương lai có thể tạo version ít bảo thủ hơn trước thí nghiệm mới.

Không có MC-OCR/Viet-Receipt-VQA hay ảnh tự thu trong corpus hiện tại; không tuyên bố đã dedup xuyên các nguồn chưa nhập. **Đã nhập Commons seed 3 ảnh** và kiểm với toàn ReceiptVQA bằng extension graph. Mỗi nguồn mới phải có overlap audit trước sử dụng. Chưa có human OCR gold; reference AI có provenance riêng, model output không tự thành gold.

## Chạy ingestion trên host hiện tại

Từ PowerShell, dùng Linux venv đã có NumPy/Pillow được hash-lock, không cài thêm vào Windows core:

```powershell
wsl -d Ubuntu-24.04 -u vidoclens -- bash -lc 'cd /mnt/c/Users/Admin/Desktop/ViDocLens; OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/vidoclens/.venvs/vidoclens-ml-repro/bin/python -m vidoclens.data.ingest_receiptvqa --annotations data/raw/receiptvqa/ReceiptVQA_annotations.zip --images data/raw/receiptvqa/rotated_images.zip --output data/manifests/receiptvqa_ingestion_new --workers 4'
```

Module [ingest_receiptvqa](../src/vidoclens/data/ingest_receiptvqa.py) từ chối output tồn tại; validation không extract ZIP tùy ý. Kiểm tra tên member gốc và tên đã được Python xử lý, basename/alias không nhập nhằng, symlink/encryption, byte/pixel limits. Mỗi batch tối đa `workers × 2` payload để không buffer cả archive trong RAM. CSV test chỉ được parse cho integrity/IDs/filenames/counts, không đưa question/answer vào manifest hoặc chọn model.

[Canonical transform](../src/vidoclens/data/images.py) thực hiện full decode → EXIF transpose → RGB → bỏ metadata trong bản RAM. Pixel SHA-256 bao gồm marker version, width/height và RGB bytes; khác hash JPEG/PNG file. Không re-encode/lưu lại 9.500 ảnh để giả có canonical files. Muốn materialize derivative cho OCR về sau phải lưu thêm hash file và lineage; `canonical_file_materialized=false` hiện tại là chủ ý.

Runtime dùng Pillow/NumPy từ ML lock; package extra `data` khai báo dependency khi thiết lập host mới. Chưa tạo lock riêng cho ingestion vì hiện đã chạy trong môi trường ML đã khóa, không đổi lock cũ. pHash DCT 64-bit của dự án lấy median trên low frequencies 8×8 của ảnh grayscale 32×32; không nhận hash tương đương bit-for-bit với mọi thư viện/version. [ImageHash implementation](https://github.com/JohannesBuchner/imagehash/blob/master/imagehash/__init__.py) và [Pillow EXIF transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose) là tham khảo thuật toán/API; code và runtime thực của mỗi run được snapshot/hash.

Một lượt chỉ hợp lệ khi có `summary.json` pass và hash `images.jsonl` khớp. Folder bị gián đoạn không được đọc như inventory hoàn chỉnh; rerun dùng tên mới, không ghi đè evidence trước.

## Tạo graph và bản chia dữ liệu nháp

```powershell
wsl -d Ubuntu-24.04 -u vidoclens -- bash -lc 'cd /mnt/c/Users/Admin/Desktop/ViDocLens; /home/vidoclens/.venvs/vidoclens-ml-repro/bin/python -m vidoclens.data.split_draft --inventory-dir data/manifests/receiptvqa_ingestion_v1 --pilot data/manifests/receiptvqa_phase0_pilot.json --output data/manifests/receiptvqa_dedup_new'
```

- [Exact grouping](../src/vidoclens/data/dedup.py) dùng connected components trên byte/pixel matches; mọi thành viên nối bắc cầu và exposure pilot theo cả group. Group ID gắn namespace/document membership, không phụ thuộc thứ tự file.
- pHash full distance ≤6 hoặc crop giữa 80% distance ≤4 sinh `NearDuplicateCandidate` với `review_status=pending`, `auto_merge_allowed=false`. Hai thresholds được ghi trước chạy; chưa đủ cho mọi xoay/crop/chụp lại. Candidate kể cả xuyên test chỉ phục vụ kiểm tra danh tính ảnh, không tuning VQA hoặc đọc test gold.
- Train group chạm dev/test → quarantine train; dev chạm test → quarantine dev; official test giữ nguyên. Quarantine là metadata exclusion, không xóa ảnh hoặc sửa CSV.
- `SplitDraft` chỉ là đề xuất: 10% clean train groups vào audit (làm tròn xuống), 30% eligible dev groups vào calibration; seed 42 được đưa vào SHA-256 ranking có purpose riêng. Pilot-exposed groups không được chọn audit. G5/G10/G25/G100 là nested group IDs, không chứa answers. Chưa stratify question type; source không có trường taxonomy, cần chốt trước freeze.
- `SplitDraft` có schema riêng, `training_allowed=false`, không parse được thành `ReceiptAccessPlan`. Không cung cấp cờ override để tự nhận `image_dedup_verified`. Chưa triển khai bước promote draft thành final access plan khi review còn mở.

## Review tiếp theo

Ưu tiên candidate xuyên official split, rồi candidate có thể nối audit/train hoặc dev_select/dev_calibrate. So cả ảnh gốc và chi tiết receipt number/date/items/totals; cùng merchant/template không đủ kết luận duplicate. Ghi mỗi quyết định `duplicate/different/uncertain`, reviewer, lý do, hash hai ảnh và protocol; `uncertain` không được tự coi là `different`. Thêm OCR/feature candidates cho các trường hợp pHash không bao quát, kể cả crop/rotation. Không chỉnh thresholds theo accuracy/test QA.

Theo nhánh semantic review, khi review xong build lại graph/partitions và kiểm tra overlap/pilot exposure/nested budgets rồi freeze. Theo nhánh containment ADR-020, không gỡ pending edge: kiểm tra tất cả edges nằm trong component trước freeze. Nếu audit group đã được xem labels để chọn kỹ thuật, phải ghi exposure và loại khỏi audit trước freeze. Không dùng kết quả test để gỡ các constraint.

## Pipeline hiện thực tiếp theo

Chạy trong Linux venv ML đã khóa cho feature/metric; OCR dùng venv OCR riêng. Các lệnh Python dưới đây dùng repo root làm working directory, output cần tên chưa tồn tại. Không tự tải weights hoặc gọi provider.

```text
python -m vidoclens.data.feature_candidates --inventory-dir data/manifests/receiptvqa_ingestion_v1 --archive data/raw/receiptvqa/rotated_images.zip --output data/manifests/features_new
python -m vidoclens.data.freeze --inventory-dir data/manifests/receiptvqa_ingestion_v1 --dedup-dir data/manifests/receiptvqa_dedup_v1 --feature-dir data/manifests/receiptvqa_features_v1 --pilot data/manifests/receiptvqa_phase0_pilot.json --output data/splits/containment_new
python -m vidoclens.ocr.quality --root . --split-dir data/splits/receiptvqa_containment_v1 --inventory-dir data/manifests/receiptvqa_ingestion_v1 --archive data/raw/receiptvqa/rotated_images.zip --output artifacts/phase1/ocr_new
python -m vidoclens.eval.phase1 --annotations data/raw/receiptvqa/ReceiptVQA_annotations.zip --split-dir data/splits/receiptvqa_containment_v1 --ocr-dir artifacts/phase1/ocr_quality_v1 --output artifacts/phase1/oracle_new
python scripts/check_metric_parity.py --sources artifacts/phase1/upstream_parity_v1 --output artifacts/phase1/parity_new.json
```

Feature runner full-decode → canonical RGB → thumbnail tối đa 512 px → pHash rotations/center crop 60% và gradient dHash128. Thresholds được ghi trước chạy; 3.360 candidates feature, union với pHash gốc thành 19.496 unique pairs (có cả exact pairs từ feature pass). Không phải exhaustive retrieval cho arbitrary crop/chụp lại. [Feature summary](../data/manifests/receiptvqa_features_v1/summary.json).

`load_frozen_plan` kiểm tra hash tất cả artifact bắt buộc và membership. `access_g5/g10/g25/g100.json` là plans có quyền; `partition_membership.json` giữ format draft để xem assignment, không phải grant. Graph là containment, khác exact identity graph. [Independent overlap/gold check](../artifacts/phase1/frozen_split_verification_v1.json) đọc train/dev và chặn test, kiểm tra 9.500 IDs, 64.812 QA, 19.496 constraints và gold/silver.

R1 dùng gold để chọn span có max strict EM rồi multiset F1, tie-break ngắn/lexical; tối đa 4 dòng liên tiếp, 24 tokens/span, joins space/newline/literal separator. ANLS của span được chọn không phải oracle tối đa ANLS. Multi-part vẫn một full answer; part diagnostics không cấp EM khi chỉ đúng một phần. Bootstrap 2.000 lần theo component, cùng qids cho paired comparison. Report là **100 ảnh train diagnostic**, không phải final benchmark. Test/OOD vẫn chặn.

OCR giữ 960 px max side, CPU 4 threads, MKLDNN off và weights Phase 0. Cache key chứa image/pixel, preprocessing/settings, language, engine/model revision+manifest hash, lock hash; payload checksum và publish atomic. 100 ảnh này đã thuộc train G10, không làm lộ audit/dev_calibrate. [Review protocol](OOD_ANNOTATION_PROTOCOL.md) phân biệt reference AI và human gold.

## OOD seed và đóng G1 bằng AI

Nguồn/hash/giấy phép và giới hạn ở [data card](data/COMMONS_OOD_SEED_V1.md). Các lệnh dưới dùng ảnh/weights đã có và thư mục output mới; không tải hoặc cài thêm. Nếu thư mục đã tồn tại, chọn run ID mới, không xóa evidence.

```powershell
wsl -d Ubuntu-24.04 -u vidoclens -- bash -lc 'cd /mnt/c/Users/Admin/Desktop/ViDocLens && /home/vidoclens/.venvs/vidoclens-ml-repro/bin/python -m vidoclens.data.ood_seed --root . --output data/manifests/commons_ood_seed_new'
wsl -d Ubuntu-24.04 -u vidoclens -- bash -lc 'cd /mnt/c/Users/Admin/Desktop/ViDocLens && HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/vidoclens/.venvs/vidoclens-ml-repro/bin/python -m vidoclens.data.local_ai_review --root . --tasks-file artifacts/phase1/ai_closure_inputs_v1/tasks.jsonl --model-path artifacts/models/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203 --output artifacts/phase1/local_ai_review_new'
.\.venv\Scripts\python.exe -m vidoclens.data.phase1_gate --root . --final-dir artifacts/phase1/ai_review_final_v1 --output artifacts/phase1/g1_ai_gate_new.json
```

`ood_seed` là importer giới hạn đúng ba nguồn của version v1, không generic downloader. `local_ai_review` kiểm weights/processor manifest, image hashes và strict task schema; inputs không label/OCR. Lượt inference mới cần adjudication mới gắn đúng output hash, không dùng lại adjudication của run trước. Gate command cuối kiểm bộ evidence **đã hoàn tất v1**, không tự đóng một run reviewer mới.

Draft OOD được chép từ ảnh trước local inference; draft OCR trước khi đọc OCR JSON đã lưu từ run cũ. Final records gồm 24 QA và 3 transcription reviews; 62 quyết định được assistant lập sau đối chiếu ảnh, không accept model hàng loạt. [Provenance](../artifacts/phase1/ai_review_final_v1/provenance.json) giữ bản gốc, output hashes và reference hashes.

Gate kiểm frozen ReceiptVQA plans/graph, source parity/R1, source image/rights hashes, không pending/quarantine, coverage và CER. Report chỉ công nhận `g1_ai_review_v1`; human gold và final OOD readiness giữ false. Test/OOD không được dùng chọn prompt, hyperparameter, filter hoặc router.
