# Sổ truy cập dữ liệu và quyền sử dụng

Ngày cập nhật vận hành: **05/11/2026**; nguồn quyền công khai rà soát ngày 02/11/2026. Đây là bằng chứng vận hành theo [DATA_GOVERNANCE](DATA_GOVERNANCE.md), không thay thế các điều kiện nguồn. Chủ dự án hiện đã **cho phép cài WSL2/Ubuntu, môi trường ML/OCR riêng và tải ảnh/weights cho pilot local**. Quyền local ban đầu không cấp external/public. **Bổ sung Phase 2:** ngày 02/11/2026 chủ dự án xác nhận đã kiểm quyền dữ liệu/terms/retention và duyệt benchmark OpenAI API cho đúng 150 ảnh/511 request keys, cap 20 USD; xem [protocol](PHASE2_WORKFLOW.md). Đây là owner attestation; không mở quyền training export, Batch upload hoặc public. Grant cụ thể ở `artifacts/phase2/approval.json`, ignored. Campaign đã hoàn tất 511 calls, 6,080008 USD theo usage; G2 đạt, không mở rộng grant.

Cập nhật hiện hành: ReceiptVQA 9.500 ảnh và frozen containment giữ nguyên. Phase4 local đã dùng grants bind đúng train_fit/audit_holdout cho teacher output; OCR/silver provenance, owner training approval, human review100/100 và G4 đã replay thành công. Không mở quyền external/public; API training export Phase2 vẫn false. OOD Commons seed không dùng train/tuning/final confirmatory evaluation. [STATUS](STATUS.md) · [Phase4 results](PHASE4_RESULTS.md) · [OOD card](data/COMMONS_OOD_SEED_V1.md).

## 1. Dữ liệu

| Nguồn / phiên bản | Truy cập thực tế | Local research / train | External / phát hành |
|---|---|---|---|
| ReceiptVQA, [README cố định](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/README.md) | Annotations ZIP/rotated images đã audit; split containment v1 freeze | Nguồn research-only, CC BY-NC-SA 4.0; Phase 3 đã train G10 gold theo frozen access plans; quyền và tiến độ Phase 4 theo grants/STATUS | External benchmark chỉ cho150 ảnh/511 request keys theo grant Phase2 do chủ dự án xác nhận; phần corpus khác vẫn external unknown/disabled. Không phát hành dữ liệu/adapter |
| [Commons OOD seed v1](data/COMMONS_OOD_SEED_V1.md) | 3 ảnh/24 QA AI, page revisions và metadata/raw/pixel hashes, cross-source audit | Local annotation/research; dataset policy cấm train/tuning/final confirmatory evaluation | CC0/CC BY-SA 4.0/CC BY 2.0 theo từng ảnh; external=false, publication=false cho version này; attribution/ShareAlike và privacy cần giữ khi cân nhắc phát hành |
| [MC-OCR](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) | Trang chính thức truy cập được; chưa có archive hay thỏa thuận ký | Cần hoàn thành thỏa thuận nghiên cứu trước nhập dữ liệu | Unknown; không thừa hưởng quyền từ dataset bên thứ ba |
| [Viet-Receipt-VQA](https://huggingface.co/datasets/5CD-AI/Viet-Receipt-VQA) | Lượt audit trước trả 401; chưa tải | Unknown; cần kiểm tra cả nhãn sinh và ảnh upstream | Unknown; chưa nhập pool |
| Ảnh tự thu thập | Chưa có | Chỉ dùng khi có quyền, redaction và gold do người gán | Tách consent cho nghiên cứu, cloud và public; chưa có consent |

Giấy phép [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) có điều kiện attribution, phi thương mại và ShareAlike khi áp dụng; [legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en) không tự cấp mọi quyền privacy. Nghiên cứu local không đồng nghĩa được phép thương mại hoặc công khai ảnh. Bảng này không biến `unknown` thành cờ approved cho pipeline chưa tồn tại.

**Provenance local:** manifests annotations/image mapping/hash/containment/source rights trong `data/manifests/`; không commit payload. Đã kiểm tra filename→bytes, full corpus fingerprints và cross-source overlap với Commons seed; chưa audit PII toàn corpus hoặc chứng minh exhaustive near-dedup. `docs/STATUS.md` chỉ chứa thống kê phục vụ review.

## 2. Models và ba vai trò teacher

Mốc rà soát nguồn ban đầu 02/11/2026; cập nhật Phase 3/4 xem STATUS và phần cuối tài liệu. Đã đọc metadata công khai Hugging Face ngày 02/11/2026, không dùng token. Sau khi được phép, đã tải student 2B và OCR; ở mốc này teacher 4B mới chỉ có metadata, được tải và chạy pilot sau đó:

| Candidate | Revision quan sát qua API | Bằng chứng quyền / giới hạn |
|---|---|---|
| [Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) | `89644892e4d85e24eaac8bacfd4f463576704203` | Model card khai báo `apache-2.0`; đã tải/hash, inference NF4 và train QLoRA G3; L2 ba seed đạt strict EM mean 46,00% trên dev_select; không phải final test |
| [Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | `ebb281ec70b05090aa6165b016eac8ec08e71b17` | Model card khai báo `apache-2.0`; snapshot và hash đã kiểm; raw single-QA pilot Phase4 đạt gate trên 666 QA (coverage96,25%, strict EM36,49%, ANLS61,34%); không chứng minh teacher vượt student |
| [PP-OCRv5_server_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_det) | `ca867c897ecbca8873081573a802ad70d499cb94` | Đã tải 5 files/88.355.053 bytes và kiểm tra LFS; CPU pilot, không cấp quyền ảnh |
| [latin_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec) | `ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57` | Đã tải 5 files/8.215.271 bytes và kiểm tra LFS; mapping `vi` xác nhận trong PaddleOCR 3.2.0; quality pilot G1 100 ảnh có lỗi dấu/merge/missed lines; giữ làm baseline diagnostic |

Link `blob/main/LICENSE` của 4B trả 404 qua web reader; vì vậy bằng chứng hiện tại là khai báo model card/API, không ghi đã đọc LICENSE đóng gói trong weights. Đã lưu README theo hai revision trên trong `cache/phase0_source_audit/` và manifest hashes tại `artifacts/phase0/candidate_model_metadata.json` (local, Git ignored); cả hai README có `license: apache-2.0`. [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) có điều kiện về notices/redistribution; license model không thay license ảnh hoặc tự quyết định quyền đối với mọi output.

| Vai trò | Trạng thái hiện hành | Gate để thực thi |
|---|---|---|
| `benchmark_teacher` API | G2 đạt; chọn A3 GPT-5.4 snapshot 2026-03-05, image+OCR theo ADR-025 | Chỉ grant benchmark 150 ảnh/511 keys đã dùng; campaign mới cần scope/price phù hợp |
| `label_teacher` API | Disabled; quyền distillation chưa xác minh | Bằng chứng được dùng output cho student, độc lập với quyền gọi inference |
| `label_teacher` local | Qwen3-VL-4B-Instruct đã chạy pilot và sinh silver train/audit theo grant Phase4; human review/G4 đã replay pass | Hoàn tất cho exact Phase4 pools/batches đã bind; không mở grant cho nguồn, split, mục đích, API export hoặc serving mới |
| `fallback_teacher` online API | Đã chọn profile A3 trên dev, serving vẫn disabled | Phase 5; server policy + quyền trên dữ liệu + request consent + budget; kiểm tra output teacher như student |

**Kết quả nhánh local Phase4 (05/11/2026):** Qwen3-VL-4B-Instruct đã vượt pilot gate trên dev_select và được dùng cho các pool train/audit có grant; 27.774 QA train_fit và 3.454 QA audit_holdout được bind/replay. Đây là bằng chứng cho đúng revision, pool, prompt và mục đích đã duyệt; không mở rộng sang dữ liệu/API mới, không tuyên bố teacher tốt hơn student và không cấp serving/public rights. Xem [Phase4 results](PHASE4_RESULTS.md).

## 3. Phương án gold dự phòng đã có trong SOT §7.5

Mốc xem xét: **15/11/2026**, không tự tạo lịch chạy. Nếu ReceiptVQA chưa có ảnh hợp lệ, chủ dự án cung cấp/thu thập receipts có quyền; mục tiêu 100–200 receipts, tổng 500–1.000 QA thủ công. Chia theo receipt/duplicate group trước silver; đề xuất 70/15/15 train/dev/test và chốt manifest trước experiment. Kiểm tra độc lập ít nhất 20% QA; nếu chỉ một người, làm lượt kiểm tra trễ và ghi hạn chế.

Đây là **kế hoạch dự phòng, chưa có gold thay thế**. Nếu kích hoạt phải lập ADR về nguồn/split mới, giảm claim RQ1 thành benchmark nội bộ và không gọi là kết quả ReceiptVQA. Không dùng QA do OCR/teacher sinh làm gold thay thế. Người phụ trách dữ liệu/consent: chủ dự án; công cụ chỉ kiểm tra và xây pipeline sau khi có dữ liệu được phép.

## 4. Code license và phát hành

**Đề xuất Phase 0: MIT cho code tự viết**, chưa áp dụng và chưa tạo `LICENSE` ở root. Chủ dự án chốt trước public release; giữ license/notices của dependency và code bên thứ ba riêng. Code license không cấp lại quyền ReceiptVQA/weights/teacher outputs. Giai đoạn hiện tại chỉ phát triển local; không push, public hosting hoặc công bố dữ liệu.

Trước mọi lần đổi mục đích sử dụng: cập nhật bằng chứng nguồn, người quyết định, ngày, phạm vi và artifact bị ảnh hưởng. Đọc secret hay gửi email tác giả không thuộc quy trình này.

## Bổ sung Phase4 — 03/11/2026

Theo yêu cầu tích hợp/thực thi toàn Phase4, đã tải public Qwen3-VL-4B-Instruct revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`:13files/8.887.291.213bytes; SHA LFS/Git blob khớp upstream. [Manifest local](../artifacts/phase4/teacher_download_v1/manifest.json), [model card pin revision](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/ebb281ec70b05090aa6165b016eac8ec08e71b17/README.md). Publisher khai Apache-2.0; snapshot không có LICENSE riêng. Không diễn giải license model thành quyền ảnh mới.

Phạm vi local ReceiptVQA giữ frozen split/rights Phase3; authorization evidence ghi instruction hiện hành, data register, model card/download hashes và SOT. Pilot structured 113 requests và raw 666 requests đều dùng cùng 666 QA. Raw đã đạt gate; exact train/audit generation grants nằm ở artifacts/phase4/execution_v1/labeling và bind pilot report. Exact full train batch và owner approval đã được replay trong G4. API training export Phase2 vẫn false; không dùng số dư budgetAPI cho phase này. [Execution](PHASE4_EXECUTION.md).
