# Changelog

Ghi thay đổi đáng chú ý; tiến độ và evidence ở [STATUS](docs/STATUS.md). `Unreleased` là thay đổi local/chưa phát hành, không chứng nhận đã push hoặc deploy. Version package `0.1.0` hiện tại chưa là một GitHub release.

## Unreleased

### Added

- Foundation: Pydantic contracts, FastAPI validation/health, CLI doctor, cấu hình và docs nghiên cứu; inference API chưa tích hợp model.
- Phase 0: audit ReceiptVQA, gold boundary, pilot OCR/student local và hash locks có số thực.
- Phase 1: ingestion, conservative containment/frozen access plans, OCR/cache, strict/compatible metrics, bootstrap và R1 oracle.
- AI-assisted OCR/OOD review theo ADR-021, có provenance/adjudication; references không là human gold hoặc final OOD benchmark.
- Quy trình task/branch/commit/push thủ công, bảng phase hiện hành, mẫu Issue/PR và kiểm tra file policy/schema trước commit.

### Changed

- Tách nhật ký thực thi cũ sang `docs/STATUS_HISTORY.md`; `docs/STATUS.md` giữ hiện trạng và bàn giao mới nhất.
- CI CPU bổ sung schema drift, file policy và YAML checks; quyền read-only, không có bước publish/deploy.

### Known limitations

- Phase 2–7 chưa triển khai; API inference chưa ready; chưa training, full OOD validation hoặc deployment.
- GitHub CI/release chưa được xác minh chạy; dữ liệu và artifacts local bị ignore không đi kèm checkout.
