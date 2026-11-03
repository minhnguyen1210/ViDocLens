# Changelog

Ghi thay đổi đáng chú ý; tiến độ và evidence ở [STATUS](docs/STATUS.md). `Unreleased` là thay đổi local/chưa phát hành, không chứng nhận đã push hoặc deploy. Version package `0.1.0` hiện tại chưa là một GitHub release.

## Unreleased

### Added

- Phase 5 offline: P3-check/P3-snap với numeric/field/geometry/ambiguity guards; immutable dev bundles, correction/harm/coverage metrics; injected cascade backend, exact-request gates, SQLite reservation/cache, circuit/deadline; dev_calibrate routing grid/explicit freeze; blind human OOD reconciliation và final-suite preregistration. Thêm 22 schemas, CPU synthetic tests và handoff PC; không inference/API/human annotation thật.
- Bổ sung Phase 4: local teacher snapshot/config/plan, strict output parser, raw SQLite attempts/resume và lazy Qwen NF4 adapter; dev threshold grid/selection freeze; blind human review export/import; trainer result exchange, fairness/exposure checks và 12-run/3-seed paired component bootstrap comparison. Thêm 13 schemas và CPU fixtures; GPU adapter chưa smoke.
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

- SOT v1.13 / ADR-P5-001 xác định scope CPU, code-bound freeze, runtime/timeout/price-bound limitations và OOD provenance. Branch `phase5-offline` từ Phase 4 `2fa55cd`; G3/G4/G5 và serving readiness chưa được đóng/mở bằng tooling offline.
- SOT v1.12 / ADR-P4-002 và runbook cho các công cụ bổ sung; artifact writer publish nguyên tử/exclusive, manifest complete sau cùng. G3/G4 và quyền API/label giữ nguyên.
- SOT v1.11 / ADR-P4-001 cho phép chuẩn bị CPU Phase 4 độc lập; G3/G4 vẫn cần bằng chứng thật. STATUS phân biệt công việc PC chưa thấy và phần laptop đã kiểm chứng.

- Tách nhật ký thực thi cũ sang `docs/STATUS_HISTORY.md`; `docs/STATUS.md` giữ hiện trạng và bàn giao mới nhất.
- CI CPU bổ sung schema drift, file policy và YAML checks; quyền read-only, không có bước publish/deploy.
- SOT v1.10 / ADR-025 đóng G2: benchmark/fallback chọn A3 GPT-5.4 image+OCR; label strategy local có điều kiện trước Phase 4, serving external vẫn disabled.

### Known limitations

- Phase 2 hoàn tất, 6,080008 USD theo usage trong cap 20 USD; chưa đối soát invoice. Một A5 schema error giữ đủ 6 QA trong denominator. API training export/Batch upload chưa được cấp, local label teacher 4B chưa pilot trong checkout này. Phase 3 đang dở trên PC theo owner; Phase 4 có tooling CPU và code GPU adapter chưa smoke, chưa silver/calibration/human audit/trainer integration/G4 thật. Serving inference chưa ready; full OOD/deployment chưa hoàn tất.
- Phase 4 base `2fa55cd` đã owner commit/push; CI của base từng được xác minh ở lượt trước. Phase 5 mới còn local, chưa stage/commit/push/CI/release. Dữ liệu, grants, cache/ledger và artifacts local bị ignore không đi kèm checkout.
