# Changelog


Ghi thay đổi đáng chú ý; tiến độ và evidence ở [STATUS](docs/STATUS.md). `Unreleased` là thay đổi local/chưa phát hành, không chứng nhận đã push hoặc deploy. Version package `0.1.0` hiện tại chưa là một GitHub release.

## Unreleased

### Phase 4 complete — local (05/11/2026)

- G4 pass 10/10; 9 matched runs × 191 updates, predictions/evaluations at step96/191, 12-result comparison and actual human review.
- H2 primary P2−P1-size +2.40 EM percentage points on dev; paired group-bootstrap 95% CI [+0.72,+4.17] pp, conditional on three seeds, not final test confirmation.
- Final WSL checks pass: 485 tests, Ruff/format/doctor/repository policy and 71 schemas. Serving remains inference_not_ready.
- [Results](docs/PHASE4_RESULTS.md) · [STATUS](docs/STATUS.md) · [G4 evidence](artifacts/phase4/g4_report_reviewed_v2.json). Local only; no new CI or release; owner reviews and commits/pushes manually.


### Added

- Phase 3 hoàn tất local: contracts/plan G10, assistant-only collator, QLoRA language attention, checkpoint/optimizer/RNG resume, local inference/evaluator và campaign ba seed; G3 audit9/9 đạt; L2 ba seed mean strict EM46,00% trên dev666 QA.

- Phase 2 local: Pydantic teacher contracts/prompt v2, Responses REST adapter, request-scoped permissions, SQLite transactional cache/ledger, bounded retry, Batch sharding/reconciliation và dev evaluator/CLI.
- OCR 100 dev thật, immutable 511-request plan và payload/hash validation; 61 teacher fixtures, 8 credential fixtures, 4 finalization fixtures; CLI `--env-file` và runner PowerShell nhập key local.
- Pilot 50 ảnh và A1/A2/A3/A5 trên cùng 100 dev/666 QA; usage/cost, strict/compatible metrics, component bootstrap CI, cache replay không gọi mới; finalizer và role freeze theo policy khóa trước dev output.

- Foundation: Pydantic contracts, FastAPI validation/health, CLI doctor, cấu hình và docs nghiên cứu; inference API chưa tích hợp model.
- Phase 0: audit ReceiptVQA, gold boundary, pilot OCR/student local và hash locks có số thực.
- Phase 1: ingestion, conservative containment/frozen access plans, OCR/cache, strict/compatible metrics, bootstrap và R1 oracle.
- AI-assisted OCR/OOD review theo ADR-021, có provenance/adjudication; references không là human gold hoặc final OOD benchmark.
- Quy trình task/branch/commit/push thủ công, bảng phase hiện hành, mẫu Issue/PR và kiểm tra file policy/schema trước commit.

- Continuation manifest/schema và audit giữ nguyên failed parent/partial, adopt completed runs, replay raw metrics;20 negative/roundtrip cases,40 schemas; báo cáo/model card và compute estimate có evidence.

### Changed

- Tách nhật ký thực thi cũ sang `docs/STATUS_HISTORY.md`; `docs/STATUS.md` giữ hiện trạng và bàn giao mới nhất.
- CI CPU bổ sung schema drift, file policy và YAML checks; quyền read-only, không có bước publish/deploy.
- SOT v1.10 / ADR-025 đóng G2: benchmark/fallback chọn A3 GPT-5.4 image+OCR; label strategy local có điều kiện trước Phase 4, serving external vẫn disabled.

### Known limitations

- Phase 2 hoàn tất local, 6,080008 USD theo usage trong cap 20 USD; chưa đối soát invoice. Một A5 schema error giữ đủ 6 QA trong denominator. API training export/Batch upload chưa được cấp. Phase 3/G3 và Phase 4/G4 đã đạt local; Phase 5–7 chưa triển khai; serving inference chưa ready, chưa full OOD/deployment.
- CI main0060c32 run41628624494 đã được xác minh success khi audit; chưa có CI cho thay đổi Phase 4 chưa commit, chưa release. Dữ liệu, grants, cache/ledger và artifacts local bị ignore không đi kèm checkout.

## Phase 4 integration — local (03/11/2026)

- Hợp nhất tooling `phase4-offline` trên nền main G3; giữ nguyên trainer/artifacts Phase3.
- SOT v1.13/ADR-P4-003 khóa cohort, pilot, filter selection và matched-compute sampler trước run thật.

- Thêm cohort bind Phase3, mixed gold–silver trainer/resume/exposure,12-result exporter và G4 audit, human review form local.
- Chặn Transformers override greedy bằng model defaults; strict per-item reparse giữ raw responses và valid siblings, không sửa nhãn.
- Báo cáo Markdown bind evidence G4 và checksum, gồm chi phí sinh nhãn toàn train/holdout và kết luận H2 theo CI; giữ trạng thái incomplete khi thiếu human review, từ chối fixture hoặc file đã đổi.
- Integration check v6 đạt 475 Windows/485 WSL tests và 71 schemas. Tại mốc này pilot raw đã đạt 5/5 và F1 đã freeze; teacher holdout đủ3.454 QA, OCR còn chạy, chưa G4.
