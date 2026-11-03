# Phase 4 — local teacher, grid, human review và comparison

03/11/2026 · ADR-P4-002 · [SOT §11.5](../SOURCE_OF_TRUTH.md#115-công-cụ-local-teacher-grid-human-audit-và-comparison--adr-p4-002) · [handoff](PHASE4_OFFLINE_HANDOFF.md).

Code điều phối/analysis đã kiểm CPU synthetic; **Qwen adapter chưa smoke GPU, không có silver/calibration/human review/training thật trên laptop**. Không dùng số fixture để báo nghiên cứu. Quy trình F0/F1/prepare/approval/select cũ ở [workflow](PHASE4_OFFLINE_WORKFLOW.md) vẫn dùng được.

## Local teacher

```text
python -m vidoclens.teacher.local_labels --help
python -m vidoclens.filtering --help
```

`snapshot/config/plan` không import ML. `run` mới import torch/Transformers/bitsandbytes và chỉ trên host đã có stack phù hợp. Không cài/tải model qua command này. Model candidate vẫn Qwen3-VL-4B-Instruct theo ADR-014; chưa chứng nhận chạy 12 GB hay tốt hơn student. Đây là **image-only label candidate**, không sửa A3 image+OCR benchmark/fallback.

Lệnh bên dưới là ví dụ **trên PC sau khi khôi phục artifacts**, không khẳng định path/model/grant đã tồn tại. Tạo thư mục cha output. Dùng interpreter của ML venv đã kiểm chứng trên WSL/Linux cho `run`, CPU venv cho các bước khác.

```powershell
$py = '.\.venv\Scripts\python.exe'
$archive = 'data/raw/ReceiptVQA_annotations.zip'
$frozen = 'data/splits/containment_v1'
$inventory = 'data/manifests/receiptvqa/images.jsonl'
# Model phải là dedicated directory có sẵn; thay revision bằng hash thật đã kiểm nguồn.
& $py -m vidoclens.teacher.local_labels snapshot --model artifacts/models/local_teacher --model-id Qwen/Qwen3-VL-4B-Instruct --revision <immutable-revision> --output artifacts/phase4/model_snapshot.json
& $py -m vidoclens.teacher.local_labels config --snapshot artifacts/phase4/model_snapshot.json --output artifacts/phase4/teacher_config.json
& $py -m vidoclens.teacher.local_labels plan --pool artifacts/phase4/dev_pool.json --config artifacts/phase4/teacher_config.json --archive $archive --frozen $frozen --inventory $inventory --output artifacts/phase4/dev_plan.json
```

`snapshot` hash toàn bộ file của model directory (không symlink/hidden files, phải có config và safetensors), lưu manifest **ngoài** directory đó. Quy trình này không tải model hoặc tự xác minh license/nguồn revision. `config` tạo candidate defaults: 8 questions/request, cap 12.000 ký tự question metadata, 8.192 input tokens, 2.048 output tokens, pixel cap 262.144, seed42, NF4 double BF16, SDPA, greedy, whole-answer. Chỉnh candidate config **trước** plan/pilot nếu cần; plan/hash đổi thì grant/cache run đổi. Đây chưa là tuning trên dữ liệu thật.

`plan` replay frozen pool từ archive/inventory/access plan, chỉ đưa câu hỏi silver/dev, không đưa G10 membership/answer vào model requests. Cùng ảnh chia nhóm theo qid và caps; câu đơn quá dài bị từ chối. Plan hiện bao phủ toàn pool; không tự chọn subset pilot hoặc sửa split. Nếu cần campaign pilot nhỏ hơn, phải thiết kế subset/provenance riêng trước run, không cắt file pool để vượt frozen replay.

Owner tạo `LocalGenerationGrant` theo [schema](../schemas/local_generation_grant.schema.json), bind **canonical** SHA256 của plan (`vidoclens.filtering.io.digest`, khác SHA bytes file), purpose `quality_pilot` trên dev hoặc `silver_generation`. Mọi permission default false; evidence hash phải trỏ tới hồ sơ quyền/pilot thực. Không có mẫu điền sẵn true. Silver generation cần quality pilot pass; grant này không thay `SilverApproval` cho training.

Image map JSON là `{ "document_id": "relative/path/to/image.png" }`, phủ đúng documents của plan. Resolver kiểm path trong `--image-root`, bytes hash đúng pool. Không truyền base64/ảnh/keys ra ngoài.

```powershell
& $py -m vidoclens.teacher.local_labels run --pool artifacts/phase4/dev_pool.json --plan artifacts/phase4/dev_plan.json --grant artifacts/phase4/dev_generation_grant.json --model artifacts/models/local_teacher --snapshot artifacts/phase4/model_snapshot.json --image-root data --image-map artifacts/phase4/dev_image_map.json --archive $archive --frozen $frozen --inventory $inventory --run-id local_teacher_dev_v1 --max-attempts 1 --output artifacts/phase4/local_teacher_dev_v1
```

Kết quả: `plan.json`, `grant.json`, `environment.json`, `attempts.sqlite` (raw exact decoded text, status, tokens/time/VRAM/checksums mọi attempt), `batch.json`, `manifest.json`. Dùng `batch.json` cho filtering. Manifest `complete` chỉ nghĩa artifacts đầy đủ, **không** nghĩa mọi QA thành công, teacher tốt hoặc training đã được duyệt. Kiểm `label_status_counts` và raw artifacts; metrics GPU đo generation, không gộp model load/preprocessing thành latency end-to-end.

Resume chạy lại đúng command/output sau interruption; inputs/config/code/environment/grant/image đổi phải tạo run mới. Complete run replay không gọi model, cả run có error. `--max-attempts` 1..3 giới hạn tổng attempts/request trong run chưa complete; chỉ retry error/incomplete, parse/schema lỗi không retry vô hạn. Muốn chạy lại failures của run complete phải tạo run mới, giữ cả hai bằng chứng và báo thêm compute. Crash sau inference trước SQLite commit có thể sinh lại một request. Không gọi cơ chế này là exactly-once.

`run.lock` chặn concurrent writers. Nếu kill process để lại lock, owner xác minh process đã dừng và giữ `attempts.sqlite`/metadata trước khi gỡ **đúng file lock của run**; không xóa cache để chữa lỗi binding. Atomic writer cần filesystem hỗ trợ hard-link (NTFS/ext4); lỗi publish để run incomplete và fail rõ.

Train pool cần purpose `silver_generation` và quality gate. Audit holdout còn yêu cầu `--frozen-filter path/to/config.json` đúng access plan; không generate holdout để chọn prompt/rule. `run` real không nhận fixture plan; library fixture backend chỉ phục vụ test, không có CLI giả inference.

## Dev threshold grid và freeze

```powershell
& $py -m vidoclens.filtering grid --pool artifacts/phase4/dev_pool.json --batch artifacts/phase4/local_teacher_dev_v1/batch.json --ocr artifacts/phase4/dev_ocr.jsonl --config configs/filtering/f1.yaml --archive $archive --frozen $frozen --inventory $inventory --output artifacts/phase4/dev_grid_v1
& $py -m vidoclens.filtering grid-select --grid artifacts/phase4/dev_grid_v1 --candidate tau-010 --selected-by '<owner>' --rationale '<precision-recall-retention tradeoff trên dev đã xem>' --output artifacts/phase4/f1_freeze_v1
```

`tau-010` chỉ minh họa lựa chọn, không là recommendation hay kết quả đã chọn. Grid chứa bốn bundle `tau-000/005/010/015`, audit từng candidate và `grid.json`; chỉ threshold thay đổi. `--quality-bins` optional là annotation độc lập document→bin, không suy từ agreement teacher/OCR. `grid-select` replay/check mọi candidate, lưu cả bảng và rationale trong `selection.json`, bind `config.json` frozen vào evidence. Dùng `f1_freeze_v1/config.json` cho train/holdout; giữ cả grid và freeze directory làm evidence, không sửa inplace. Không tự tối ưu theo retention. Candidate defaults khác cần campaign mới được ghi nhận, không giấu số lần thử.

## Human audit

```powershell
& $py -m vidoclens.filtering review-export --bundle artifacts/phase4/holdout_filter_v1 --archive $archive --frozen $frozen --inventory $inventory --per-stratum 25 --seed 42 --output artifacts/phase4/human_packet_v1
# Người review điền một COPY của review_template.json, sau khi tự xem ảnh đúng hash.
& $py -m vidoclens.filtering review-import --packet-dir artifacts/phase4/human_packet_v1 --review artifacts/phase4/human_completed_v1.json --output artifacts/phase4/human_summary_v1.json
```

Output gồm `packet.json` (question/image ID+hash/raw answer/OCR), `sampling_key.json` (outcomes và population/sample counts), `review_template.json`, checksum manifest. Reviewer chỉ xem packet và ảnh được join bằng document/hash; giữ sampling key/gold/filter outcome riêng đến khi annotation xong. JSON là artifact exchange, chưa có UI xem ảnh/gán nhãn. Không copy ảnh thật vào repo để tiện review.

Sampling theo QA trong bốn strata, hash rank seed cố định; strata ít mẫu lấy hết, strata rỗng có inclusion probability null. Template judgments null và image attestation false biểu thị **chưa làm**, importer không nhận như completed review. Điền correctness/semantic field/OCR quality, optional error tags/note, reviewer và attestation. Cần đúng đủ qids, không duplicate/unknown/missing, fixture flag phải khớp. `uncertain` là judgment hợp lệ; không ép thành đúng/sai.

Summary báo counts/disagreement theo stratum; không thay hidden gold, không dùng holdout sửa lại frozen config, không coi raw stratified sample accuracy là toàn pool. Attestation là khai báo của reviewer, không xác thực danh tính. Synthetic review tests không là người đã audit ảnh thật.

## Result exchange từ trainer Phase 3

Sau G3 và train/evaluate thật, adapter PC xuất một [SilverTrainingResult](../schemas/silver_training_result.schema.json) cho mỗi arm/seed. Chưa có adapter cho trainer đang dở trên PC vì source đó chưa có ở laptop. Không tạo fake result để mở gate.

| Field group | Nội dung bắt buộc |
|---|---|
| Identity | arm `L2/P1-full/P1-size/P2`, seed17/42/2026, unique run_id, fixture flag, training/evaluation pool digests |
| Evidence | G3 evidence, training profile, evaluation protocol và checkpoint hashes; selection digest đúng manifest (L2 null) |
| Data/compute | đúng gold/silver qids; **per-qid exposure counts kể cả 0**; completed updates, measured seconds/peak reserved bytes; silver arms equal loss và aggregate gold:silver 1:1 |
| Evaluation | raw `AnswerPrediction` trên cùng dev pool; error/abstain giữ status, missing được evaluator đếm là failure |

Hashes pool/selection là canonical model digest; `training_profile_sha256` là hash **bytes file** profile như lệnh select. Cả 12 results dùng cùng eval profile (prompt/preprocess/decoding/checkpoint policy đã chốt) và G3 evidence. Hash không thay việc consumer kiểm nội dung/trainer; phải log measured exposures, không điền số lý thuyết từ config. Selected nhưng chưa thấy có count0; report phân biệt selected/seen unique/total exposure. L2 gold-only có total exposure riêng; không giả L2 có silver.

```powershell
# $resultFiles là 12 file cụ thể owner đã kiểm, mỗi arm/seed đúng một file.
& $py -m vidoclens.filtering compare --train-bundle artifacts/phase4/train_filter_v1 --approval artifacts/phase4/local_label_approval.json --training-profile artifacts/phase3/frozen_training_profile.json --optimizer-updates 1000 --pool artifacts/phase4/dev_pool.json --archive $archive --frozen $frozen --inventory $inventory --results $resultFiles --resamples 2000 --bootstrap-seed 42 --output artifacts/phase4/comparison_v1
```

`1000` là ví dụ cú pháp, thay bằng budget thật giống select/L2/P1/P2. CLI replay bundle và frozen inputs, tái dựng selections bằng approval/profile/budget rồi kiểm result bindings. Cần đủ 12 runs; unmatched profile/update/gold/silver/exposure/eval protocol/fixture hoặc group leakage bị từ chối. Các silver arms phải có cùng aggregate gold exposure trong mỗi seed. Chưa có chế độ partial comparison để nhầm thành core matrix đầy đủ.

Output `comparison.json`, `seed_summary.csv`, manifest: per-seed strict EM/F1/ANLS, mean/sample std, image/group macro EM, question/reference-answer-type slices, compute/exposure. Primary paired EM P2−P1-size, secondary P2−P1-full/L2; bootstrap cùng receipt/component resamples 2.000 mặc định. CI từng seed và fixed-three-seed-average không bao gồm training variance; seed delta mean/std báo riêng. <2 groups thì CI null, missing không bị bỏ denominator. Dữ liệu dev mang tính exploratory; workflow không mở test/OOD/dev_calibrate và không tự đóng G4.
