# Data card — mẫu cần điền

Bản đã điền: [ReceiptVQA rotated ingestion v1](data/RECEIPTVQA_ROTATED_V1.md), [containment split v1](data/RECEIPTVQA_CONTAINMENT_V1.md) và [Commons OOD seed v1](data/COMMONS_OOD_SEED_V1.md). Mẫu dưới giữ để dùng cho dataset/version mới.

**NOT MEASURED / CHƯA KIỂM KÊ.** Đây là mẫu, không phải mô tả một dataset đã nhập thành công. Mỗi dataset version có bản sao data card riêng đi cùng manifest; quy tắc tại [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md).

| Thuộc tính | Giá trị phải điền |
|---|---|
| Dataset ID / version / hash manifest | Chưa có |
| Nguồn, người cung cấp, ngày nhận | Chưa có |
| License / thỏa thuận / bằng chứng quyền | Chưa xác minh |
| Quyền inference, training, external transfer, redistribution | Ghi riêng từng quyền: yes/no/unknown |
| Số ảnh / QA / merchant / duplicate group | Chưa kiểm kê |
| Ngôn ngữ, domain, thiết bị chụp | Chưa kiểm kê |
| Split và hash manifest từng split | Chưa đóng băng |
| PII và cách redaction | Chưa audit |
| OCR engine / checkpoint / preprocessing version | Chưa chọn |
| Annotation / review / adjudication | Chưa thực hiện |
| Người chịu trách nhiệm / cách yêu cầu xóa | Chủ dự án; quy trình cần hoàn thiện trước public release |

## Báo cáo chất lượng phải có

Số record bị loại và lý do; thiếu ảnh; lỗi decode; trùng exact/near-duplicate; phân bố độ phân giải và tỉ lệ ảnh khó; QA trống; multi-answer; answer type; question type; OCR failure; số mẫu có OCR support và số mẫu đúng theo gold là hai con số riêng.

Các bảng phân bố phải ghi mẫu số. Phân tích test chỉ sau freeze; không dùng phân bố lỗi từ test để quay lại chọn cấu hình.

## Annotation và test ngoài phân phối

Ghi hướng dẫn lấy nguyên văn câu trả lời, trường hợp không đọc được/không có đáp án, cách gán evidence và cách giải quyết bất đồng. Tách người/đợt annotate khỏi teacher output nếu dùng để đo nhiễu. Ghi số mẫu được review độc lập, mức đồng thuận và hạn chế khi chỉ có một annotator.

OOD phải mô tả khác biệt so với train (cửa hàng, thiết bị, thời gian, template) và giữ nguyên sau khóa. Không lấy mẫu OOD thuận tiện chỉ vì mô hình trả lời tốt.

## Giới hạn và mục đích sử dụng

Ghi rõ phạm vi được phép, giới hạn đại diện, nguy cơ thông tin cá nhân và việc không có quyền công bố ảnh gốc nếu chưa được cấp. Tài liệu công khai chỉ chứa manifest/metadata được phép; hash không tự chứng minh nội dung không nhạy cảm.
