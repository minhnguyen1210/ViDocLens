# Phase 4 trên nền main đã đạt G3

> **Hiện trạng 05/11/2026:** Phase4 hoàn tất local, G4 pass 10/10. Đây là protocol/runbook để tái lập hoặc kiểm toán; không có runner Phase4 đang tiếp tục. Xem [STATUS](STATUS.md) và [kết quả](PHASE4_RESULTS.md).

Protocol hiện hành: SOT v1.13, ADR-P4-003. Code nhận từ `phase4-offline` (`2fa55cd`),
trên nền main `0060c32`; không nhận Phase 5. Các handoff laptop là lịch sử.
Hiện trạng và kết quả thật xem [STATUS](STATUS.md). Tài liệu này mô tả công cụ chạy;
việc có lệnh, schema hoặc tests không chứng minh G4 đã đạt.

## Dữ liệu và bảo toàn Phase 3

`artifacts/phase4/integration_baseline_v1/preservation.json` ghi checksum1.523files,
bao gồm toàn bộ artifacts Phase3, frozen split containment và PROJECT_OVERVIEW.
`eval.phase4.preservation()` kiểm lại từng byte. Không chỉnh source package student
cũ, không ghi đè parent campaign bị pause, không train lại L2 để làm đẹp so sánh.

`distillation.inputs` dựng pools question-only và raw images đã kiểm SHA:

| Pool | Ảnh | QA | Quyền |
|---|---:|---:|---|
| train_fit ngoài G10 | 4.073 | 27.774 | Sinh silver và training sau pilot |
| dev_select kế thừa Phase3 | 100 | 666 | Pilot, filter grid, checkpoint selection |
| audit_holdout | 504 | 3.454 | Sinh/audit sau filter freeze; không tune/train |

G10 giữ nguyên454ảnh/3.053QA. Cohort dev bind SHA
`db3134d89de01d833080efb7b0dccd6ed99ce3521dcddbecd5187bc20975016a`.
Pool không đưa gold answers vào teacher/filter. Test, OOD, dev_calibrate và quarantine
không có entry point trong workflow này.

## Teacher và OCR thật

Teacher Qwen3-VL-4B-Instruct revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`.
Download public tường minh qua `scripts/download_phase4_teacher.py`;13files,
8.887.291.213bytes, kiểm upstream LFS SHA-256 hoặc Git blob SHA-1 trước publish.
Model card ở revision này khai Apache-2.0; không giả có LICENSE riêng trong snapshot.
Không gọi API trả phí, không dùng cache Phase2 làm training labels.

Plan/grant/snapshot ở `artifacts/phase4/teacher_protocol_v1`; pilot sửa runtime
ở `teacher_protocol_v2`. Config image-only8QA/request, pixels262144,
NF4/BF16, greedy, output2048, seed42. `request_local_v1` dùng alias q0…q7;
raw response giữ nguyên, labels ánh xạ về canonical qids. Unknown/duplicate qids,
JSON/schema lỗi, refusal/truncate không được sửa thành success.

`teacher.reparse` tạo strict_item_reparse_v1 từ completed raw cache: replay legacy batch,
validate envelope/qids, rồi validate từng item. Valid siblings không bị loại vì một item
lỗi. Không sửa answer/null/answerable/digits; metadata/parser SHA và derived runID riêng.
Candidate structured dùng cùng parser này trên pilot/grid/audit/train; raw generation batch và status counts lịch sử giữ nguyên.

Candidate thứ hai `raw_single_v1` dùng cùng snapshot, pixels và seed, một QA/request,
prompt tiếng Việt, output cap 128. Lưu nguyên raw UTF-8 làm target; không parse JSON,
strip answer hoặc sửa chữ số. Sentinel `<unanswerable>` sau strip được ghi riêng;
blank/truncate/error không thành nhãn hợp lệ. Không bịa evidence quote.

Hai candidate phải chạy đủ cùng 666 QA. `eval.label_teacher_selection` chọn trong
candidate qua gate theo EM, ANLS, rồi tổng generation seconds; thứ tự này đã ghi
trước gold metrics. Báo cáo selection bind cả hai báo cáo, giữ cả candidate thất bại.
`workflow --selection-report` kiểm candidate được chọn và replay pilot trước khi
sinh silver; dùng `--raw-mode` khi selection chọn raw. Raw cache được replay bằng
`teacher.raw_replay`; không chạy strict-item JSON reparser trên raw text.

Pilot_v1 bị ngắt khi phát hiện Transformers4.57.1 ghi đè do_sample=False từ
GenerationConfig bằng default model. Giữ log/cache lỗi; không dùng làm quality evidence.
Pilot_v2 truyền use_model_defaults=False và do_sample=False trực tiếp; regression
kiểm đúng thư viện trên WSL, không chỉ mock. Pilot phải hoàn tất toàn666QA,
answered≥90%, không inference error, EM≥L1 và GPU measurement thật trước silver.

OCR giữ nguyên detector/recognizer/lock/recipe Phase1; `ocr.quality --pool-path`
chấp nhận exact pool từ frozen archive, bao phủ tất cả ảnh ngoài G10 hoặc audit.
Cache identity cũ được dùng khi khớp, không ghi vào artifacts Phase1/2.
`ocr.export_pool` kiểm full coverage/checksums và xuất JSONL cùng bins confidence
gold-independent. Bins này là proxy của engine, không phải CER/human quality.
Worker cache có thể dùng `--shard-index 1 --shard-count 2` để xử lý nửa sau của
exact pool trong output riêng. Shard không được nhận là full coverage; lượt chính
vẫn kiểm toàn bộ ảnh và tái dùng cache cùng identity.

## Student và so sánh

`distillation.data` kiểm bundle/replay, exact approval, G3, raw targets, images/groups,
source hashes và G10 loader cũ trước materialize. Fixtures không vào real trainer.
Mọi plan có checksum các dependency, config, prompt, dev population và source Python.

Sampler xen kẽ gold/silver, cyclic shuffle riêng mỗi nguồn/seed; gold order giống nhau
giữa P1-full/P1-size/P2. Mỗi run191updates×16QA=3.056exposures,
1.528gold+1.528silver, loss weights bằng nhau. Báo counts từng qid kể cả0.
L2 lịch sử có3.053exposures/batch cuối13; cùng191updates, chênh3QA làm tròn được công bố.
Primary P2−P1-size khớp updates/exposures và gold order/counts; FLOPs hoặc wall time có thể khác theo độ dài ảnh/target và được báo bằng số đo thực. L2 là secondary có hạn chế này.

Runtime/collator/checkpoint dùng lại primitives Phase3v2; package student cũ bất biến.
Preflight toàn F0, mixed smoke52, checkpoint50→resume52 và fresh greedy reload phải đạt.
Sau đó9runs:3arms×seeds17/42/2026, checkpoint96/191. Chọn EM, Numeric EM,
p50 latency, rồi step sớm; không chọn seed tốt nhất. Full-run exposures và
selected-checkpoint exposures được lưu riêng.

`distillation.results` kiểm actual trajectories/checkpoint hashes, replay metrics,
adopt3L2 từ G3 và xuất12results. `filtering compare` kiểm selections/fairness,
mean/sample-SD, slices và paired group bootstrap2.000. CI conditional trên3seeds
đã chạy; không là test confirmation hoặc bao gồm training variance.

## Chạy trên WSL đã có runtime

ML interpreter: `/home/vidoclens/.venvs/vidoclens-ml-repro/bin/python`.
OCR interpreter: `/home/vidoclens/.venvs/vidoclens-ocr-repro/bin/python`.
Không thay CUDA/driver hoặc cài lại environment để chạy workflow này.

Sau khi pilot hoàn tất, lệnh sau chạy tuần tự các gates. Chỉ dùng output directory mới:

```text
python -m vidoclens.distillation.workflow --root . \
  --pilot-run SELECTED_PILOT_DIRECTORY \
  --selection-report artifacts/phase4/teacher_selection_v1/selection.json \
  --train-ocr artifacts/phase4/train_ocr_v1 \
  --ocr-python /home/vidoclens/.venvs/vidoclens-ocr-repro/bin/python \
  --output artifacts/phase4/execution_v1
```

Thay `SELECTED_PILOT_DIRECTORY` bằng `selected_source_run` của selection report.
Thêm `--raw-mode` chỉ khi `selected_mode=raw_single_v1`. Nếu không candidate nào
đạt gate, workflow dừng; không đổi ngưỡng hoặc nhận partial pilot là pass.

Workflow dừng khi gate/thao tác lỗi và giữ logs/cache/checkpoints; không nhận partial
output là complete. Không tái chạy cùng output hoặc sửa source sau freeze để vượt
hash check. Để tiếp tục, xác định stage lỗi, dùng artifact directory mới và liên kết
evidence cũ; trainer hỗ trợ `--resume` ở update boundary. Campaign/result exporter
hiện chỉ đóng core comparison trên trajectories đầy đủ bắt đầu step0; nếu primary
run bị ngắt, cần continuation audit riêng trước adoption, không tự ghép logs.

## Human review và G4

Sau audit holdout, workflow tạo `human_review/review.html`, packet và template riêng.
Reviewer nhìn ảnh/câu hỏi/teacher answer/OCR, không thấy gold hoặc filter outcome;
lấy25QA mỗi stratum khi có đủ mẫu. HTML chạy local, không gửi dữ liệu ra ngoài.
Các lựa chọn mặc định để trống; người thật điền tên, judgments và xác nhận đã xem ảnh,
rồi lưu `phase4-human-review.json`. Assistant không ký hoặc điền thay human evidence.

```text
python -m vidoclens.distillation.checks --output artifacts/phase4/checks_final_v1
python -m vidoclens.eval.phase4 --execution artifacts/phase4/execution_v1 \
  --checks artifacts/phase4/checks_final_v1 \
  --human-review PATH_TO_ACTUAL_REVIEW.json \
  --output artifacts/phase4/g4_report_v1.json
```

Final audit replays raw metrics, selections, holdout/review sampling, checkpoints và
preservation; không sửa Phase3. Không có human review thì report chỉ `incomplete`.
H2 âm vẫn có thể passG4 nếu đủ evidence; không đổi threshold vì holdout/test hoặc vì
P2 chưa thắng. G4 không tự bật API readiness, public hosting, commit, push hay release.

Khi gate đã có đủ machine evidence, xuất báo cáo đọc được từ chính các file đã bind:

```text
python -m vidoclens.eval.phase4_report --execution artifacts/phase4/execution_v1 \
  --gate-path artifacts/phase4/g4_report_v1.json \
  --output artifacts/phase4/results_v1.md
```

Reporter kiểm checksum, population và H2 delta; gồm chi phí sinh nhãn full train/holdout,
training theo seed, CI/seed variance và human status. Thiếu human review vẫn ghi
`incomplete`; kết luận H2 âm hoặc CI chứa0 được giữ nguyên. Output đã tồn tại bị từ chối.

## Kết quả thực thi local — 05/11/2026

Phase4 hoàn tất local; [STATUS](STATUS.md) là hiện trạng, [báo cáo](PHASE4_RESULTS.md) chứa metrics và limitations. G4 pass 10/10, bao gồm human review thật, final code checks, replay 9 matched runs/12 results và preservation audit.

Theo yêu cầu nghỉ máy, run7 cũ bị SIGINT tại step75/191 trước checkpoint96. Partial được giữ nguyên cùng SHA manifest trong artifacts/phase4/recovery_after_run6_v1/interrupted; run7 mới được chạy lại từ step0 trong slot campaign chuẩn, sau đó run8–9 và comparison hoàn tất. Parent campaign.json tiếp tục ghi complete=false cho attempt lịch sử; recovery state riêng bind lần chạy tiếp. Không ghép trajectory partial vào run thành công.
