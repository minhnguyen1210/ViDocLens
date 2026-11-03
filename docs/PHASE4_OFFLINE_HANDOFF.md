# Bàn giao Phase 4 offline từ laptop sang PC

Ngày: **03/11/2026**. Branch **`phase4-offline`**, base **`d13360e`** (Phase 2).
Owner tự review, stage, commit, chuyển code và push nếu muốn. Lượt triển khai này không stage/commit/push, không thêm author/co-author hoặc sửa Git identity.

## Trạng thái bàn giao

Phase 3 đang làm trên PC theo chủ dự án; code chưa có ở laptop, **chưa audit G3 hoặc xác nhận tương thích trainer**. Phase 4 có implementation CPU và tests; **G4 chưa đạt**. Cài `.venv` CPU riêng trên laptop, không thay ML/OCR locks hoặc CUDA.

| Task | Phạm vi local | Còn lại trên PC |
|---|---|---|
| P4-OFF-001 | Silver contracts/schema, question-only frozen pool, local result exchange | Local label teacher adapter/pilot và nguồn dữ liệu thật |
| P4-OFF-002 | F0/F1, evidence offsets, reason codes, immutable bundles/replay | Hiệu chỉnh trên dev, đo recall/precision thật; semantic checks chưa có |
| P4-OFF-003 | Audit CLI/evaluator; chín experiment selections, matched strata/counts/budget metadata | Human audit, trainer integration, sampler/resume, P1/P2 thực tế |
| P4-OFF-004 | Synthetic unit/workflow tests, runbook, SOT/ADR/status/handoff | Kiểm tra lại sau merge và GPU smoke trên PC |

Kết quả kiểm tra cuối cùng ghi ở [STATUS](STATUS.md). Dữ liệu thật, weights, grants và artifacts cũ không đi kèm checkout. Không suy trạng thái PC từ kết quả CPU của laptop.

## File ownership và điểm dễ conflict

| Nhóm | File / thư mục | Cách hợp nhất |
|---|---|---|
| Implementation mới | `src/vidoclens/contracts/silver.py`, `src/vidoclens/filtering/{io,pool,matching,pipeline,bundle,experiments,__main__}.py`, `src/vidoclens/eval/silver.py` | Giữ độc lập với student; đối chiếu nếu PC cũng đã tạo tên tương tự |
| Tests mới | `tests/unit/test_silver.py`, `test_silver_workflow.py` | Synthetic-only; không thay fixtures chung |
| Config | `configs/filtering/f1.yaml` | Candidate defaults; không copy đè config frozen của run thực |
| Contracts registry | `scripts/export_schemas.py`, 10 schema silver/filter mới | Hợp nhất cả registrations Phase 3 và Phase 4; xuất lại schema sau merge |
| Tài liệu chung | SOT, DECISIONS, STATUS, STATUS_HISTORY, CHANGELOG, README, các README liên quan và TEST_PLAN | Hợp nhất nội dung; **không chọn nguyên file của laptop ghi đè tiến độ PC** |
| Tài liệu riêng | `PHASE4_OFFLINE_WORKFLOW.md`, file bàn giao này | Giữ làm hợp đồng phạm vi và runbook |

Không sửa `src/vidoclens/student/`, configs student, ML/OCR locks, core CLI registration, API, Phase 2 provider/ledger, dữ liệu hoặc split cũ. CLI Phase 4 là `python -m vidoclens.filtering`, nên không cần tranh sửa `vidoclens.cli` với Phase 3.

ADR dùng ID **ADR-P4-001** để giảm nguy cơ trùng số ADR mà PC có thể đã thêm. SOT của laptop nâng lên v1.11; nếu PC cũng nâng version, hợp nhất nội dung và chọn revision mới, không ép quay về v1.11.

## Khi về PC

1. Giữ nguyên checkout/venv/artifacts đang train. Lưu và tự commit code Phase 3 trên nhánh của nó; bảo toàn checkpoint, optimizer/scheduler/RNG, frozen config và run evidence bằng cơ chế sao lưu riêng. Git không mang theo những payload này.
2. Trên laptop, tự review diff và file policy rồi commit nhánh `phase4-offline`. **Nhánh chưa commit vẫn trỏ về base; merge/cherry-pick sẽ không mang theo thay đổi working tree.** Không chỉ chuyển output `git diff` vì các file mới chưa tracked sẽ bị thiếu.
3. Chuyển code bằng phương thức bạn chọn. Nếu muốn không dùng GitHub, sau khi tự commit có thể tự tạo Git bundle nhánh rồi chuyển sang PC. Nếu dùng GitHub thì bạn tự push. Không gửi dataset/weights/cache/.env cùng code.
4. Tạo nhánh tích hợp từ Phase 3 đã lưu, merge hoặc cherry-pick các commit Phase 4. Giải quyết shared docs/exporter, đối chiếu semantic contract ngay cả khi Git báo không có conflict. Chưa thể đảm bảo merge sạch khi chưa đọc diff PC.
5. Chạy schema export/check, Ruff và full CPU suite. Sau đó nối trainer theo checklist bên dưới, chạy một fixture rồi GPU smoke với dữ liệu được phép. Chỉ train core matrix sau khi G3 và local label gate đạt.

Lệnh kiểm tra **sau merge**, dùng interpreter đúng trên PC:

```text
python scripts/export_schemas.py
python scripts/export_schemas.py --check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m vidoclens doctor
python scripts/check_repo.py
git diff --check
```

## Giao diện Phase 3 cần nối

- Đọc manifest selection và kiểm manifest/file hashes, pool/access-plan/archive identity. Kiểm model/preprocessing/LoRA/schedule/profile thực tế trùng `training_profile_sha256`; hash một file profile không tự chứng minh G3.
- Từ `gold_qids`, chỉ lấy G10 qua loader gold hiện có; từ `silver_qids`, lấy **raw answer** trong `silver_targets.json`. Không bọc silver thành gold hoặc đọc nhãn ẩn của silver pool. Không train evidence, normalized answers hoặc semantic diagnostics.
- Join ảnh bằng document/source image ID và hash trong pool với resolver của Phase 3; pool không áp đặt absolute path của laptop.
- Từ chối `fixture_only=true` cho training/nghiên cứu thật; cần G3 và local label approval đúng batch. Các manifest luôn ghi chưa chạy training.
- Enforce ratio gold:silver 1:1, loss weights bằng nhau, cùng optimizer updates/resolution/base/LoRA/checkpoint rule/seeds cho L2/P1/P2 theo SOT. Log unique sample counts, oversampling và exposure thực tế; giữ RNG/sampler state khi resume.
- Dùng answer-only loss/image-token alignment đã kiểm chứng ở Phase 3. Dry-run này không thiết kế lại collator hoặc checkpoint format trên PC.

## Điều kiện đóng Phase 4

Local teacher pilot + silver thật có provenance/quyền, config chốt trên dev_select, audit holdout sau freeze, core P1-full/P1-size/P2 ba seed và so sánh L2 công bằng. Báo retention, nhóm bị loại, noise/false reject, chi phí/compute và CI thích hợp; kết quả âm hợp lệ. Xem [G4 trong SOT](../SOURCE_OF_TRUTH.md#phase-4--chưng-cất-có-kiểm-chứng).
