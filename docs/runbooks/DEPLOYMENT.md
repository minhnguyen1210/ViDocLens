# Runbook triển khai

**Hiện trạng:** repo đang ở nền móng. Docker CPU scaffold chỉ chứng minh có thể khởi động web/API; `/health/live` thành công không chứng minh OCR/student hoạt động. `/health/ready` phải trả `503` khi chưa cấu hình và load model. Chưa có triển khai GPU production được xác nhận.

Đích Phase 6: một host Linux GPU hoặc môi trường tương thích đã kiểm chứng, một worker giữ model trên RTX 3060 12GB, FastAPI và demo Gradio, reverse proxy TLS khi truy cập qua mạng. Cấu hình và tiêu chí cuối theo [SOURCE_OF_TRUTH.md](../../SOURCE_OF_TRUTH.md).

## Chuẩn bị release

1. Chốt commit và môi trường có lock; build immutable container digest. Không dùng tag `latest` để nhận diện release.
2. Tạo release manifest có base model revision, adapter hash, tokenizer/processor revision, OCR weights/config, verifier/router config, schema/prompt versions và data provenance.
3. Lưu model card, metrics, smoke fixtures hợp lệ, known issues và checksum. Chỉ chọn release qua dev/acceptance gates đã đóng băng.
4. Chạy test/scan cần thiết; kiểm tra quyền phân phối artifact. Không đóng API key hoặc raw training data trong image.
5. Giữ bundle release trước và backup metadata/config theo retention. Thử restore và rollback trước khi nhận traffic thực.

## Chuẩn bị host đích

Kiểm tra GPU/driver/runtime/container compatibility bằng bài smoke thực; có checkpoint load được không đủ chứng minh batch thực vừa VRAM. Chốt image pixel budget, sequence length, queue capacity và request timeout bằng load test.

Chạy service bằng user không đặc quyền. Mount model read-only, cache/data vào volume riêng có quyền tối thiểu; tách secrets khỏi repo/image. Giữ API và demo ở loopback/private network; chỉ reverse proxy được tiếp xúc internet. Bật TLS, xác thực, giới hạn request/rate và upload limit theo hợp đồng. Không bật auto-reload hoặc nhiều web workers cùng load GPU model.

Demo dùng API server qua backend; API key của provider không xuất hiện ở browser. External mode mặc định tắt; cả policy server và lựa chọn request đều phải cho phép mới gửi dữ liệu.

## Trình tự đưa bản mới vào sử dụng

1. Kiểm tra backup và release manifest; đảm bảo bundle có thể rollback. Với single GPU 12GB, đặt maintenance window, drain và dừng runtime cũ trước khi nạp candidate; không mặc định đủ VRAM cho hai model đồng thời.
2. Mount bundle candidate và khởi động trên cổng nội bộ. Readiness vẫn fail trong lúc weights/OCR đang load.
3. Warm-up bằng fixture được phép dùng; đo VRAM, latency, schema và readiness. Model load lỗi không được “healthy” bằng fallback giả.
4. Chạy smoke Track A, Track B, abstention, local-only, lỗi upload và external denied. Nếu external được bật, kiểm tra budget và quyền trước smoke tương ứng.
5. Chạy tải giới hạn và kiểm tra 429/503 khi bận, timeout có hủy/giải phóng tài nguyên, và OOM không làm hệ thống lặp retry vô hạn.
6. Chuyển traffic bằng reverse proxy sau gate; quan sát error rate, queue, VRAM, latency và chi phí. Giữ release cũ đủ lâu theo rollback policy.

Lệnh chạy nền móng hiện có nằm trong README. Lệnh triển khai GPU chính thức chỉ được đưa vào runbook sau khi image/config thực tồn tại và smoke trên host đích; không thay Docker CPU bằng một nhãn “GPU” mà chưa kiểm chứng.

## Quan sát và lưu trữ

Log structured gồm request/run ID, release ID, mode, timing từng stage, reason codes và số đo usage. Không ghi ảnh/OCR đầy đủ, secrets hoặc nội dung chứng từ vào log vận hành mặc định. Phân biệt chất lượng offline với số đo online: lượng OCR-supported response không phải online accuracy.

Theo dõi liveness/readiness, latency p50/p95, queue depth, error/abstention/fallback rates, GPU memory, OCR failure và budget remaining. Ngưỡng alert được chốt từ pilot; không hứa SLO khi chưa đo. Upload tạm phải hết hạn và được dọn, kể cả request lỗi.

## Rollback và hoàn thành

Khi schema/quality/runtime gate thất bại, ngừng nhận request mới, cho request đang chạy kết thúc hoặc timeout có kiểm soát, dừng candidate rồi nạp lại bundle cũ. Warm-up và kiểm tra readiness trước khi mở lại proxy. Release đầu chưa có bản cũ thì quay về maintenance state. Rollback nguyên bundle; không ghép adapter cũ với processor mới. Cache namespaced theo version, database migration phải tương thích rollback hoặc có kế hoạch restore đã thử.

Deployment chỉ hoàn tất khi có URL/môi trường truy cập thực, commit/digest/manifest, log smoke, kiểm tra quyền truy cập và bằng chứng rollback. Docker build thành công trên laptop chưa phải deployment hoàn tất.
