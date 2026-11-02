# Checklist phát hành

Áp dụng trước khi gọi một phiên bản là release hoặc đưa tới người dùng. **Hiện tại chưa có release model/deployment hoàn chỉnh.** Quy định tại [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md); thao tác triển khai tại [runbooks/DEPLOYMENT.md](runbooks/DEPLOYMENT.md).

## Phạm vi và quyền

- [ ] Track A/Track B, loại input được hỗ trợ và giới hạn đã ghi rõ; không quảng cáo chỉ số chưa đo.
- [ ] Code license do chủ dự án chọn; hiện chưa mặc định gán license cho toàn repo.
- [ ] Base model, adapter, dataset, teacher output, ảnh demo và dependencies có quyền dùng/phân phối phù hợp.
- [ ] Không có secrets, raw PII, dataset hoặc artifact không được phép trong Git/image/public storage.
- [ ] External routing có policy server, quyền dữ liệu và lựa chọn request tường minh; mặc định tắt.

## Bằng chứng chất lượng và artifact

- [ ] CI cần thiết pass; những kiểm tra chưa chạy được ghi đúng là chưa chạy.
- [ ] Eval protocol/scorer đã khóa, không leakage; primary comparisons và CI có artifact tái lập.
- [ ] Track B có đánh giá theo field; missing/ambiguous values không được tự điền.
- [ ] Regression fixtures bao gồm sai chữ số, sai trường, thiếu evidence, abstention và input lỗi.
- [ ] Model/data cards đầy đủ số thực, giới hạn và provenance.
- [ ] Release manifest ghim commit, lock/container digest, base/adapter/processor/OCR/verifier/schema/config cùng checksums.

## Triển khai và vận hành

- [ ] GPU load/inference smoke và VRAM thực pass trên host đích; liveness/readiness phản ánh đúng trạng thái.
- [ ] Upload/queue/rate/timeout limits, auth/TLS và bounded concurrency đã kiểm tra.
- [ ] Log không lộ dữ liệu; budget ledger và policy local-only được kiểm tra bằng lỗi giả lập.
- [ ] Backup đã restore thử; rollback toàn bundle về release trước đã diễn tập.
- [ ] Upload tạm/cache có retention và cleanup, kể cả khi request lỗi.
- [ ] Lưu URL/môi trường đích, release ID, log smoke, known issues, người chịu trách nhiệm và ngày phát hành.

Không đánh dấu checklist bằng việc file/config tồn tại; mỗi gate cần kết quả hoặc artifact chứng minh.
