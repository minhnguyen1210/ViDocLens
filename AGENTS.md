# ViDocLens — hướng dẫn làm việc trong repository

Đọc `SOURCE_OF_TRUTH.md` trước khi thay đổi kiến trúc hoặc triển khai một phase. `PROJECT_OVERVIEW.md` là ý tưởng lịch sử, giữ nguyên trừ khi chủ dự án yêu cầu sửa. `docs/STATUS.md` ghi hiện trạng; `docs/DECISIONS.md` ghi quyết định.

## Quy tắc thực thi

- Tôn trọng phạm vi người dùng giao. Dựng scaffold không đồng nghĩa triển khai toàn bộ OCR/training/API. Ghi rõ thành phần chưa có; không trả inference giả, metric giả hoặc readiness thành công khi chưa có model.
- Logic dùng chung nằm trong `src/vidoclens`; demo chỉ gọi API. Notebook không là implementation duy nhất của một bước pipeline.
- Contract là Pydantic trong `src/vidoclens/contracts`; JSON schema được sinh bằng `scripts/export_schemas.py`. Sửa contract phải tái xuất và kiểm tra các trạng thái biên liên quan.
- Không dùng label trong teacher input; chia dữ liệu theo receipt/duplicate group. Test/OOD không chọn prompt, hyperparameter, filter hay router.
- Numeric evidence không được fuzzy sửa digit. Lưu raw answer riêng normalized value. OCR agreement không phải chứng nhận đúng ngữ nghĩa.
- Không đọc/in khóa bí mật; không commit ảnh thật, OCR/cache, dataset, weights hoặc `.env`. File mẫu không chứa secret.
- GitHub: chủ dự án tự kết nối remote và push thủ công. Assistant tuyệt đối không tự chạy `git push` hoặc dùng công cụ/API publish, sync hay upload code lên GitHub thay cho push. Yêu cầu triển khai phase, sửa code hoặc hoàn tất công việc không cấp quyền push; mọi thay đổi chuẩn bị trong repo phải để chủ dự án tự đưa lên GitHub.
- Không tự gọi API trả phí, tải dataset/weights lớn hoặc bật public hosting chỉ để kiểm tra foundation. Khi tác vụ đã được chủ dự án cho phép, thực thi trong budget/quyền dữ liệu đã thiết lập; không xin lại phép cho thao tác đã được ủy quyền.
- Không tự gửi email hoặc liên hệ tác giả. Có thể soạn nội dung khi được giao; gửi cần chỉ dẫn cụ thể.
- Dependency core và ML/OCR tách biệt. Không đổi CUDA/driver hệ thống cho một test CPU. Pin stack ML sau smoke trên host thật, không bịa lock đã tương thích.
- Với thay đổi kiến trúc, cập nhật SOT và ADR cùng nhau. Với kết quả thực thi, cập nhật STATUS và chỉ ghi những gì đã kiểm chứng.
- Tuân thủ `CONTRIBUTING.md`: STATUS là bảng phase/task hiện hành, STATUS_HISTORY lưu lịch sử, CHANGELOG ghi thay đổi đáng chú ý. Mỗi bàn giao cập nhật kết quả kiểm tra, blocker/điều kiện gỡ và bước tiếp theo. Phân biệt local done, commit, push, CI và release; không tự stage/commit khi chỉ được giao triển khai. Chủ dự án tự commit/push thủ công.

## Kiểm tra

Môi trường hiện có: `.venv` cục bộ, không commit. Trên Windows dùng `.venv\Scripts\python.exe`; Linux dùng `.venv/bin/python`.

```text
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m vidoclens doctor
python scripts/export_schemas.py --check
python scripts/check_repo.py
```

Chạy kiểm tra phù hợp phần thay đổi. Thay đổi tài liệu thuần túy chỉ cần kiểm tra nội dung, liên kết, UTF-8 và tính nhất quán; không cần thêm unit test mô phỏng câu chữ. Kiểm tra Docker/GPU chỉ khi có runtime phù hợp, và báo rõ nếu chưa thực hiện. Không phát biểu CI GitHub đã pass khi mới chỉ viết workflow.
