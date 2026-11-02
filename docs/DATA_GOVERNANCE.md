# Quy trình dữ liệu và quyền sử dụng

Áp dụng cùng [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md). Mục tiêu là mỗi ảnh, QA, nhãn bạc và checkpoint đều truy ngược được tới nguồn và quyền sử dụng.

## Nhập dữ liệu

1. Lưu URL nguồn, version, ngày nhận, license/thỏa thuận và phạm vi được phép. Có link tải không đồng nghĩa được training, gửi bên thứ ba hay tái phân phối.
2. Gán source ID; kiểm tra hash, decode ảnh, kích thước, EXIF orientation và nhãn bắt buộc. Raw giữ bất biến trong vùng truy cập hạn chế.
3. Tạo canonical document ID, liên kết mọi alias và ảnh biến thể với document gốc. Lưu cả hash byte gốc và hash ảnh đã chuẩn hóa; phép biến đổi có version.
4. Kiểm tra PII; chỉ derivative đã review mới được cấp quyền external/public. Trạng thái unknown luôn chặn đường xuất dữ liệu đó.
5. Tạo manifest với quyền `benchmark`, `train`, `external_transfer`, `redistribute` độc lập; nguồn chưa rõ quyền được quarantine.

Quyền cần được kiểm tra ở record hoặc source manifest, không chỉ một biến `.env`. Không tự gửi email, chia sẻ dataset hoặc công bố trọng số thay chủ dự án.

## Chống leakage và khóa split

Exact hash chỉ phát hiện bản sao giống byte. Kết hợp decoded-image hash, perceptual hash và review cặp nghi trùng để phát hiện crop/resize/chụp lại. Không dùng pHash như chứng minh duy nhất rằng hai nguồn hoàn toàn độc lập. Ghi thresholds, phiên bản và quyết định review.

Mọi QA của một document và mọi thành viên duplicate cluster đi cùng một split. Giữ official ReceiptVQA split để so sánh; nếu phát hiện trùng xuyên split, ghi rõ exclusion policy và báo cáo protocol sạch riêng, không âm thầm sửa official benchmark. Loại các nguồn silver bổ sung trùng dev/test khỏi pool training.

Theo thiết kế hiện hành, chia official train theo document/duplicate cluster thành `train_fit` khoảng 90% và `audit_holdout` khoảng 10%; khóa danh sách trước chạy. Gold k% là tập ảnh lồng nhau trong `train_fit`, không phải lấy ngẫu nhiên QA cùng ảnh. `audit_holdout` không dùng train hoặc chọn threshold; dev dành tuning; test và OOD dành reporting sau freeze. Tỷ lệ theo cluster có thể lệch nhẹ; lưu số thực tế.

Hidden gold dùng đánh giá nhiễu phải nằm ngoài input của teacher/filter/student. Quy trình sinh silver chỉ đọc image, question và OCR được phép; scorer mở nhãn khi đối chiếu. Kết quả audit không được biến thành vòng chỉnh threshold rồi tiếp tục gọi là held-out audit.

Pretraining contamination khác leakage do project tạo ra: kiểm tra training sources của candidate model; nếu đã học ảnh MC-OCR/Viet-Receipt-VQA trùng benchmark, công bố nguy cơ và đánh giá trên test sạch/OOD phù hợp. Khử trùng dữ liệu SFT không xóa kiến thức đã có trong base weights.

## Nhãn bạc và quyền output

Mỗi record lưu provider/model revision, prompt/schema hash, input document/question IDs, request/cache key, response raw, parse status, OCR evidence, filter decision và reason codes. Nhãn bị loại vẫn được thống kê với quyền truy cập tương ứng; không chỉ giữ ca thành công.

Quyền benchmark/inference của một API không tự cho phép dùng output để train một model local. Chỉ bật export training labels sau khi điều khoản áp dụng hoặc sự cho phép phù hợp được ghi lại. Ý kiến người hướng dẫn giúp đánh giá nghiên cứu nhưng không thay thế quyền từ chủ dữ liệu/dịch vụ. Teacher thay thế cũng cần kiểm tra license riêng.

## Dữ liệu tự thu thập và dữ liệu người dùng

Chỉ thu thập tài liệu có quyền sử dụng; tránh thu thập thông tin không cần cho bài toán. Bản redacted dùng đánh giá phải được chú thích lại nếu redaction làm mất đáp án. Không công bố bản gốc hoặc dấu che có thể đảo ngược.

Đối với request demo, mặc định xử lý tạm, không dùng ảnh/question/output làm training data. Log không chứa ảnh, OCR đầy đủ, API key hay PII. Persistent caching là chế độ riêng có retention được công bố, quyền truy cập và cơ chế xóa; không áp dụng cache nghiên cứu dài hạn cho upload demo theo mặc định.

## Lưu trữ, xóa và công bố

- Không commit ảnh, checkpoint, `.env`, API responses hoặc cache chứa dữ liệu nhạy cảm vào Git.
- Phân quyền data/cache và backups; mã hóa phù hợp môi trường triển khai; không để file server public trỏ vào raw storage.
- Yêu cầu xóa phải truy qua document ID tới derivative, OCR, teacher response, training manifest và backup theo retention. Nếu dữ liệu đã vào checkpoint, đánh giá cần thu hồi/retrain; xóa ảnh không đồng nghĩa đã xóa ảnh hưởng trong weights.
- Trước public release, kiểm tra license code, base model, adapter, dataset, synthetic output và hình minh họa riêng. Artifact không có quyền phân phối chỉ được tham chiếu cách truy cập hợp lệ.
- Data card phải ghi các hạn chế và ngày rà soát; quyết định quyền thay đổi phải cập nhật manifest, SOT/ADR khi tác động thiết kế.
