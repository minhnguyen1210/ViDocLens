# Data card — ReceiptVQA rotated ingestion v1

Kiểm kê ngày **02/11/2026**. **Đã nhập image inventory, chưa freeze dataset training/benchmark.** Chỉ ReceiptVQA rotated; không bao gồm MC-OCR/Viet-Receipt-VQA/OOD. [Workflow](../PHASE1_WORKFLOW.md), [quyền nguồn](../DATA_ACCESS_REGISTER.md), [quản trị](../DATA_GOVERNANCE.md).

| Thuộc tính | Kết quả / giới hạn |
|---|---|
| Nguồn | Repo phong-lt/LiGT_VQA, README commit `5b4376b455ed82e16b2285fca5d8b4b25ee3a3af`; archives tải 02/11/2026 |
| License | Research-only, CC BY-NC-SA 4.0; quyền inference/train/external/release tách biệt |
| Annotations SHA-256 | `226f7dcc6421115da254b2809dc9ebfd138be0c2f175a9c1c12f7a46ae6127ea` |
| Rotated ZIP SHA-256 | `731bc35c3525c6a067363aa77ccf49189932773976148adea9994ad8e2861a5e` |
| Image inventory SHA-256 | `672c177c40759c776da3df2606c29c2e09adfe9aa6b8bcdc1cb802e5037be4aa` |
| Quyền đang thực thi | Audit/pilot nghiên cứu local theo quyền chủ dự án; draft không cấp quyền train, external/public disabled |
| Số ảnh / QA | **9.500 / 64.812**, mọi ảnh CRC/full decode pass |
| Format/mode | 9.500 JPEG/RGB; 0 ảnh cần EXIF transpose trong archive này |
| Dimensions | Width 352–2.592, height 480–6.686; biên độc lập, không phải một ảnh có cả hai cực trị |
| Filename mapping | 9.493 exact, 7 aliases `.png/.jpeg` → `.jpg` theo stem duy nhất; không sửa CSV |
| Exact duplicate | 9.465 raw byte hashes và 9.465 canonical pixel hashes; 29 nhóm nhiều ảnh, 15 nhóm xuyên official split |
| Near duplicate | 19.391 cặp pending review, trong đó 6.959 xuyên official split; không coi đây là duplicate đã xác nhận |
| Canonical derivatives | EXIF/RGB/bỏ metadata đã chạy trong RAM để hash; chưa materialize file, không re-encode corpus |
| PII / merchant / thiết bị | Chưa audit/thống kê toàn corpus, chưa redaction; không cho external/public |
| OCR | Feasibility 20 ảnh đã có; chưa quality pilot 100 ảnh, human transcription/CER |
| Trách nhiệm | Nguyễn Hữu Gia Minh; deletion/release workflow cần hoàn thiện trước public release |

Domain nguồn là receipt tiếng Việt; chưa đo tỷ lệ ngôn ngữ, merchant, question/answer types đầy đủ. Image inventory/graph/review queue không có QA/gold. Test chỉ được parse cấu trúc/IDs/filename/counts; không dùng test QA/metric chọn model.

## Official split và draft

Official train/dev/test vẫn **7.600/950/950 ảnh**, **51.886/6.426/6.500 QA**. Bảng dưới là draft sau exact grouping, còn thay đổi sau near review, không là số mẫu đã train.

| Partition | Ảnh | QA | Group IDs phân biệt |
|---|---:|---:|---:|
| train_fit | 6.822 | 46.619 | 6.811 |
| audit_holdout | 759 | 5.141 | 756 |
| dev_select | 665 | 4.481 | 665 |
| dev_calibrate | 285 | 1.945 | 284 |
| test | 950 | 6.500 | 949 |
| quarantine (official train) | 19 | 126 | 15 |

Quarantine group IDs cũng xuất hiện trong dev/test; không cộng cột group thành tổng toàn corpus. Không có dev→test quarantine theo exact hash lần này. Các thành viên không quarantine của exact group không vượt partition.

20 nhóm pilot nằm ngoài audit. Tỷ lệ áp dụng theo group, không theo ảnh/QA; seed 42 dùng SHA-256 ranking có purpose riêng. Nested gold IDs dự kiến: G5=340, G10=681, G25=1.702, G100=6.811. Chưa mở gold/train; khi freeze phải công bố thêm ảnh/QA từng budget và chốt stratification question type. `SplitDraft.training_allowed=false`; loader đã reject actual draft trong kiểm tra thực.

## Artifacts local

- [Ingestion summary](../../data/manifests/receiptvqa_ingestion_v1/summary.json), [run/source/runtime](../../data/manifests/receiptvqa_ingestion_v1/run.json), [inventory](../../data/manifests/receiptvqa_ingestion_v1/images.jsonl).
- [Dedup summary](../../data/manifests/receiptvqa_dedup_v1/summary.json), [exact groups](../../data/manifests/receiptvqa_dedup_v1/exact_groups.json), [review queue](../../data/manifests/receiptvqa_dedup_v1/near_duplicate_candidates.jsonl).
- [Split draft](../../data/manifests/receiptvqa_dedup_v1/split_draft.json), SHA-256 `240637316e45f4f26e5901025308711efb0d4a7f45ef7ebfbca4a99570619bea`.
- [Independent verification](../../artifacts/phase1/ingestion_dedup_verification.json): schema/membership, counts, overlap, pilot exclusion và actual draft không cấp quyền gold training.

Artifacts bị Git ignore, không phải gói phát hành. Mỗi run dùng folder mới; source/transform/package metadata đi cùng kết quả. Chưa xác nhận parity preprocessing official benchmark.

## Gate còn mở

Review candidates, thêm OCR/feature matching cho crop/rotation/chụp lại; freeze graph/split và final access plan có quarantine; OCR 100 ảnh với subset transcription được review; official scorer/multipart parity, bootstrap và R1; thu/gán nhãn OOD có quyền; PII/release audit. **G1 chưa đạt.**
