# Commons OOD seed v1 — AI reference

Ngày nhập và review: **02/11/2026**. Chủ dự án: Nguyễn Hữu Gia Minh. Đây là seed phục vụ **bắt đầu annotation OOD trong Phase 1**, theo SOT §7.5/ADR-021. Không phải human gold, tập train, hoặc benchmark xác nhận cuối dự án.

## Nguồn và quyền

| Ảnh nguồn | Tác giả / giấy phép công bố | Page ID / revision | Nội dung và giới hạn |
|---|---|---|---|
| [Sample Remittance Receipt of Vietnam Post](https://commons.wikimedia.org/wiki/File:Sample_Remittance_Receipt_of_Vietnam_Post.jpg) | HuangWending18072009 / [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | 171575050 / 1066296904 | Biên nhận chuyển tiền dạng sample theo mô tả nguồn, tiếng Việt, nhiều trường riêng tư đã che; không khôi phục nội dung bị che |
| [Hanoi Department of Transportation receipt](https://commons.wikimedia.org/wiki/File:Hanoi_Department_of_Transportation_receipt.jpg) | Donald Trung / [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | 59349747 / 1252969174 | Mẫu biên lai phí in sẵn, ngày và người thu để trống; không chứng minh giao dịch đã xảy ra |
| [Một tờ hóa đơn ăn uống ở Việt Nam](https://commons.wikimedia.org/wiki/File:M%E1%BB%99t_t%E1%BB%9D_h%C3%B3a_%C4%91%C6%A1n_%C4%83n_u%E1%BB%91ng_%E1%BB%9F_Vi%E1%BB%87t_Nam.jpg) | Martin Lewison, nguồn Flickr / [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) | 113371922 / 1006657757 | Ảnh hóa đơn tại Việt Nam, chữ in tiếng Anh, phần merchant bị cắt; câu hỏi tiếng Việt |

Metadata Commons API được lưu nguyên bản theo từng file trong `data/raw/commons_ood_seed_v1/metadata_*.json`; manifest gắn SHA-256 metadata và page revision. Bytes ảnh được so SHA-1/size với API trước nhập; SHA-256 raw cũng được lưu. Tổng tải ảnh **8.000.054 bytes**, không weights mới. Không coi tên nguồn hoặc tác giả là đáp án nếu thông tin không hiện trên ảnh.

Quyền vận hành version này: local annotation/research cho phép; **train=false, external=false, publication=false**. Các cờ false là phạm vi sử dụng của dự án, không phải khẳng định giấy phép cấm mọi hoạt động đó. Attribution/ShareAlike và quyền riêng tư cần được giữ/kiểm tra khi cân nhắc phát hành. Ảnh/QA/metadata đầy đủ nằm trong Git ignore; không đưa dữ liệu cá nhân lên README. Chủ dự án xử lý yêu cầu sửa/xóa theo DATA_GOVERNANCE; version hiện tại chưa phát hành.

## Ingestion, fingerprint và chống leakage

Full decode → EXIF transpose → RGB → bỏ metadata ở bản processed PNG; giữ JPEG gốc. Ảnh thứ ba có EXIF orientation 6, canonical **3024×4032**; hai ảnh còn lại **1248×960** và **3840×2160**. Raw hash, pixel hash và processed-file hash là ba trường riêng, không thay nhau.

- [Manifest](../../data/manifests/commons_ood_seed_v1/documents.jsonl), SHA-256 `07cd41b3d3524469945d406d92aad9667f49d04c13faa22b1d1bca39f5c451bf`.
- [Overlap audit](../../data/manifests/commons_ood_seed_v1/overlap.json): **28.500 cặp xuyên nguồn + 3 cặp nội bộ; 0 candidate**. So với toàn inventory 9.500 ảnh và feature fingerprints đã freeze, gồm test **images**, không đọc test QA để chọn cấu hình.
- Raw/pixel exact; full pHash ≤6, crop80 ≤4, rotation pHash ≤4, crop60 ≤2, gradient128 ≤2 với 8–120 ones. Các orientation được so chéo; thresholds chốt trước chạy. Không chứng minh đã tìm hết mọi ảnh chụp lại hoặc crop tùy ý.
- [Graph extension](../../data/manifests/commons_ood_seed_v1/graph_extension.json) nối hash graph gốc và ba node có namespace Commons. Không sửa graph/access plans ReceiptVQA. Bất kỳ seed node chạm candidate chưa phân xử đều bị quarantine; reader không nhận annotation của ảnh đó.

## Annotation và kiểm tra

**3 ảnh × 8 câu hỏi = 24 QA**, gồm **18 answerable / 6 unanswerable**. Câu hỏi lấy từ nội dung nhìn thấy, không chọn vì model trả lời tốt. Full raw answers giữ nguyên chữ số, leading zero, dấu câu; answerable có bbox [0,1] trên canonical image, unanswerable có answer/bbox rỗng. Không tính toán tổng thay đáp án in sẵn.

Assistant chép draft trực tiếp từ ba ảnh trước lượt model local. Qwen3-VL-2B revision `89644892e4d85e24eaac8bacfd4f463576704203`, NF4/BF16 chạy offline trên GPU, nhận **image + question**, không OCR/draft/reference. Profile cố định trước inference: max 262.144 pixels, 64 output tokens, greedy, seed 42. **24/24 QA** có lượt kiểm tra chéo và quyết định cuối từ ảnh; không đổi prompt/threshold sau khi nhìn output. Model từng trả sai trường, chữ số và suy nội dung bị che; output đó không tự ghi đè reference. Cả 24 draft giữ nguyên sau adjudication.

[Annotations](../../artifacts/phase1/ai_review_final_v1/ood_annotations.jsonl), [adjudications](../../artifacts/phase1/ai_review_final_v1/adjudications.jsonl), [provenance](../../artifacts/phase1/ai_review_final_v1/provenance.json), [gate](../../artifacts/phase1/g1_ai_gate_v2.json). `annotator_type=ai`, `second_review=ai_only`, `eligible_as_human_gold=false`, `eligible_for_confirmatory_evaluation=false` được enforce bằng Pydantic; không ghi điểm model accuracy trên seed này.

Đây là convenience sample rất nhỏ, một nhà cung cấp ảnh, gồm blank/sample và một hóa đơn tiếng Anh; chưa đại diện merchant/device/time của biên lai Việt Nam. Không có independent human review hoặc independent model family: reviewer local dùng cùng base student. Full OOD ở các phase nghiên cứu sau cần dữ liệu rộng hơn và validation thực theo SOT; không tái dùng seed bị model-review này như một tập final test chưa từng xem.
