## Thay đổi và lý do

<!-- Nêu vấn đề cụ thể và hành vi sau thay đổi. Ví dụ trước/sau nếu hữu ích. -->

## Phạm vi

- Task/issue: <!-- ID local hoặc issue thật; không dùng Closes khi mới hoàn tất một phần -->
- Phase/gate:
- SOT/ADR: <!-- link thay đổi hoặc N/A -->

## Validation

| Lệnh / môi trường | Kết quả | Evidence |
|---|---|---|
| | | |

<!-- Phân biệt local tests, GitHub CI, GPU và benchmark. Artifact local không có trên GitHub: ghi run ID/hash và giới hạn truy cập. -->

## Hạn chế và rủi ro còn lại

<!-- Nêu điều chưa kiểm chứng; ghi không có nếu phù hợp. -->

## Review

- [ ] Phạm vi/task nghiệm thu đạt, STATUS cập nhật; CHANGELOG nếu có thay đổi đáng chú ý.
- [ ] Contract/schema/config/docs khớp; SOT + ADR nếu đổi kiến trúc hoặc scope.
- [ ] Diff không có secret, ảnh thật, dataset, OCR/cache hoặc weights.
- [ ] Không test/OOD tuning, không đổi digits bằng fuzzy; provenance AI/human đúng loại (hoặc N/A).
- [ ] Kiểm tra phù hợp đã chạy; phần chưa chạy được ghi rõ.

<!-- Chủ dự án tự push/merge. Checklist không tự chứng nhận phase/release đã hoàn tất. -->
