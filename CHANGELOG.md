# Changelog

Ghi thay đổi đáng chú ý; tiến độ và evidence ở [STATUS](docs/STATUS.md). `Unreleased` là thay đổi local/chưa phát hành, không chứng nhận đã push hoặc deploy. Version package `0.1.0` hiện tại chưa là một GitHub release.

## Unreleased

### Added

- Phase 4 offline trên laptop: 10 silver/filter contracts/schema; frozen G10 question-only pools; local result exchange; F0/F1 bounded OCR evidence, numeric guards, raw target preservation; immutable bundles/replay và privileged audit.
- Nine experiment selections (P1-full/P1-size/P2 × 3 seeds), matched-size strata, exact-batch local label approval gates, shared profile/update budget metadata; synthetic workflow tests và hướng dẫn tích hợp với Phase 3 trên PC.

- Phase 2 local: Pydantic teacher contracts/prompt v2, Responses REST adapter, request-scoped permissions, SQLite transactional cache/ledger, bounded retry, Batch sharding/reconciliation và dev evaluator/CLI.
- OCR 100 dev thật, immutable 511-request plan và payload/hash validation; 61 teacher fixtures, 8 credential fixtures, 4 finalization fixtures; CLI `--env-file` và runner PowerShell nhập key local.
- Pilot 50 ảnh và A1/A2/A3/A5 trên cùng 100 dev/666 QA; usage/cost, strict/compatible metrics, component bootstrap CI, cache replay không gọi mới; finalizer và role freeze theo policy khóa trước dev output.

- Foundation: Pydantic contracts, FastAPI validation/health, CLI doctor, cấu hình và docs nghiên cứu; inference API chưa tích hợp model.
- Phase 0: audit ReceiptVQA, gold boundary, pilot OCR/student local và hash locks có số thực.
- Phase 1: ingestion, conservative containment/frozen access plans, OCR/cache, strict/compatible metrics, bootstrap và R1 oracle.
- AI-assisted OCR/OOD review theo ADR-021, có provenance/adjudication; references không là human gold hoặc final OOD benchmark.
- Quy trình task/branch/commit/push thủ công, bảng phase hiện hành, mẫu Issue/PR và kiểm tra file policy/schema trước commit.

### Changed

- SOT v1.11 / ADR-P4-001 cho phép chuẩn bị CPU Phase 4 độc lập; G3/G4 vẫn cần bằng chứng thật. STATUS phân biệt công việc PC chưa thấy và phần laptop đã kiểm chứng.

- Tách nhật ký thực thi cũ sang `docs/STATUS_HISTORY.md`; `docs/STATUS.md` giữ hiện trạng và bàn giao mới nhất.
- CI CPU bổ sung schema drift, file policy và YAML checks; quyền read-only, không có bước publish/deploy.
- SOT v1.10 / ADR-025 đóng G2: benchmark/fallback chọn A3 GPT-5.4 image+OCR; label strategy local có điều kiện trước Phase 4, serving external vẫn disabled.

### Known limitations

- Phase 2 hoàn tất, 6,080008 USD theo usage trong cap 20 USD; chưa đối soát invoice. Một A5 schema error giữ đủ 6 QA trong denominator. API training export/Batch upload chưa được cấp, local label teacher 4B chưa pilot trong checkout này. Phase 3 đang dở trên PC theo owner; Phase 4 mới có implementation CPU, chưa local teacher runner/silver thật/calibration/human audit/trainer integration/G4. Serving inference chưa ready; full OOD/deployment chưa hoàn tất.
- CI cũ tại03ac245 đã được xác minh; CI cho Phase2 và release chưa chạy. Dữ liệu, grants, cache/ledger và artifacts local bị ignore không đi kèm checkout.
