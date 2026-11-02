# Model card — mẫu cần điền

**NOT MEASURED / CHƯA HUẤN LUYỆN.** Chưa có checkpoint ViDocLens được phát hành. Mỗi release phải tạo bản card tương ứng; không điền accuracy, chi phí hoặc “chạy tốt 12GB” trước khi có run artifact.

| Thuộc tính | Giá trị phải điền |
|---|---|
| Model / release ID | Chưa có |
| Base repository / immutable revision / license | Candidate, chưa xác nhận cuối |
| Adapter format / rank / target modules / hash | Chưa có |
| Processor / tokenizer revision | Chưa có |
| Train dataset / split manifest hashes | Chưa có |
| Silver provider / quyền dùng output / filter version | Chưa có |
| Code commit / dirty state / config hash / dependency lock | Chưa có |
| Hardware / quantization / compute dtype / image budget | Chưa đo |
| Seed / steps / effective batch / optimizer / time | Chưa chạy |
| Verifier / router / schema versions | Chưa chốt |

## Intended use và giới hạn

Hỏi đáp và trích xuất trường từ ảnh biên lai tiếng Việt trong phạm vi đã đánh giá. Phải công bố các loại tài liệu chưa hỗ trợ, trường hợp từ chối, điều kiện gọi external và ảnh hưởng của ảnh mờ/chữ nhỏ. Kết quả có OCR support không đồng nghĩa đã đúng trường hay đúng nội dung ảnh.

## Bảng kết quả release

| Split / track | N ảnh / N QA | EM / ANLS / Numeric EM hoặc field metrics | Coverage / selective accuracy | Chi phí / latency / VRAM | Run ID |
|---|---|---|---|---|---|
| Chưa có | Chưa đo | Chưa đo | Chưa đo | Chưa đo | — |

Kèm khoảng tin cậy, normalization, phần mềm scorer, warm/cold cache, số lần đo và error taxonomy. Báo cáo từng seed và tổng hợp; bootstrap theo document hoặc duplicate group, không coi QA cùng ảnh là độc lập.

## Phát hành

Ghi artifact checksums, compatibility matrix, cách load, smoke input hợp lệ được phép công bố, response kỳ vọng, rollback bundle trước đó và known issues. Adapter-only release vẫn phải kiểm tra quyền dữ liệu, output teacher và base model; không mặc định quyền phát hành từ việc train thành công.
