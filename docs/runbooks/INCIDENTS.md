# Xử lý sự cố

Runbook mục tiêu cho hệ thống khi đã triển khai. Trong giai đoạn scaffold, lỗi `not_implemented` và readiness `503` vì chưa có model là hành vi được công bố, không phải kết quả suy luận.

## Quy trình chung

Ghi thời điểm, request/run ID, release ID, triệu chứng và phạm vi ảnh hưởng; không sao chép chứng từ hoặc secrets vào issue công khai. Chặn tác động đang tiếp diễn, giữ log cần thiết với quyền hạn chế, phục hồi bằng cấu hình đã biết tốt, sau đó xác minh bằng smoke phù hợp. Ghi nguyên nhân, biện pháp ngăn tái diễn và test regression nếu cần.

| Sự cố | Hành động ngay | Kiểm tra trước phục hồi |
|---|---|---|
| GPU OOM / worker chết | Ngừng nhận thêm việc; drain/khởi động worker có kiểm soát; không retry cùng input vô hạn | Pixel/sequence limits, concurrency=1, VRAM rò rỉ; smoke cả ảnh khó |
| OCR lỗi hoặc thiếu evidence | Trả trạng thái phù hợp/abstain; chỉ external khi có quyền và budget | OCR engine/cache version, tọa độ resize, ảnh decode; không coi OCR rỗng là xác nhận không có đáp án |
| Provider timeout/429/5xx | Retry hữu hạn với backoff; circuit breaker; giữ budget reservation đúng | Retry-after, ledger và partial response; không gửi lại Batch đã có result |
| Vượt trần hoặc usage bất thường | Tắt external routing/silver jobs; giữ local còn an toàn | Reconcile reserved/spent, duplicate request, price version; không reset ledger để chạy tiếp |
| Sai số tiền / sai trường | Tạm dừng release/route có vấn đề; dùng bundle trước hoặc abstain | Raw answer, evidence đúng quyền, semantic field confusion, numeric normalization và snap policy |
| Readiness fail sau cập nhật | Không chuyển traffic vào bản mới | Base/adapter/processor compatibility, file hash, disk space, GPU driver |
| Nghi lộ key/PII | Dừng đường xuất dữ liệu liên quan; thu hồi/rotate secret và hạn chế log/artifact | Tìm phạm vi truy cập, xử lý cache/backups theo quyền và retention; không đưa dữ liệu lộ vào báo cáo công khai |
| Leakage hoặc metric bug | Đánh dấu run `invalidated`, giữ provenance, dừng claim liên quan | Xác định mọi run bị ảnh hưởng, sửa split/scorer, ADR và rerun nhất quán |

## Thay đổi trong sự cố

Chỉ áp dụng thay đổi tối thiểu để khôi phục. Không âm thầm giảm chất lượng ảnh, đổi model/threshold hoặc bật external để làm readiness xanh. Mọi thay đổi ảnh hưởng prediction phải có config/release version và quay lại acceptance gate.

Sau phục hồi, kiểm tra liveness **và** inference smoke, Track B schema, policy dữ liệu ngoài máy, budget accounting và cleanup upload. Chốt postmortem bằng bằng chứng và chủ sở hữu hành động; không quy lỗi cho “model ngẫu nhiên” khi chưa kiểm tra dữ liệu và pipeline.
