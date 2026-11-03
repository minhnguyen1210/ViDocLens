# Bàn giao Phase 4 offline từ laptop sang PC

Ngày: **03/11/2026**. Branch **`phase4-offline`**, base **`d13360e`** (Phase 2), HEAD **`3ae2c4f`** do owner đã commit/push; bổ sung ADR-P4-002 đang ở working tree, chưa commit.
Owner tự review, stage, commit, chuyển code và push nếu muốn. Lượt triển khai này không stage/commit/push, không thêm author/co-author hoặc sửa Git identity.

## Trạng thái bàn giao

Phase 3 đang làm trên PC theo chủ dự án; code chưa có ở laptop, **chưa audit G3 hoặc xác nhận tương thích trainer**. Phase 4 có implementation CPU và tests; **G4 chưa đạt**. Cài `.venv` CPU riêng trên laptop, không thay ML/OCR locks hoặc CUDA.

| Task | Phạm vi local | Còn lại trên PC |
|---|---|---|
| P4-OFF-001 | Silver contracts/schema, question-only frozen pool, local result exchange | Xác minh nguồn dữ liệu/model thật |
| P4-OFF-002 | F0/F1, evidence offsets, reason codes, immutable bundles/replay | Hiệu chỉnh trên dev, đo recall/precision thật; semantic checks chưa có |
| P4-OFF-003 | Audit CLI/evaluator; chín experiment selections, matched strata/counts/budget metadata | Human audit, trainer integration, sampler/resume, P1/P2 thực tế |
| P4-OFF-004 | Synthetic unit/workflow tests, runbook, SOT/ADR/status/handoff | Kiểm tra lại sau merge và GPU smoke trên PC |
| P4-OFF-005 | Local plan/parser/raw SQLite attempts/cache/resume; snapshot/config và lazy Qwen NF4 adapter | GPU smoke, local quality pilot, quyền/license, image map, generation thật |
| P4-OFF-006 | Grid đủ 4 ngưỡng dev, bundles/replay + selection rationale/freeze | Chạy dev thật và owner chọn threshold bằng evidence |
| P4-OFF-007 | Seeded blind human packet, template và complete-review importer | Người review ảnh thật; gói JSON chưa có annotation UI |
| P4-OFF-008 | Result contract, fairness/exposure checks, 12-run/3-seed comparison + paired component bootstrap | Nối result exporter của trainer PC, train/evaluate thật |

Kết quả kiểm tra cuối cùng ghi ở [STATUS](STATUS.md). Dữ liệu thật, weights, grants và artifacts cũ không đi kèm checkout. Không suy trạng thái PC từ kết quả CPU của laptop.

## File ownership và điểm dễ conflict

| Nhóm | File / thư mục | Cách hợp nhất |
|---|---|---|
| Implementation mới | `src/vidoclens/contracts/silver.py`, `src/vidoclens/filtering/{io,pool,matching,pipeline,bundle,experiments,__main__}.py`, `src/vidoclens/eval/silver.py` | Giữ độc lập với student; đối chiếu nếu PC cũng đã tạo tên tương tự |
| Bổ sung lần này | `contracts/{local_teacher,silver_review,silver_results}.py`, `teacher/{local_labels,local_qwen,local_cli}.py`, `eval/{filter_grid,silver_review,silver_comparison}.py`, `filtering/offline_cli.py`; atomic writer trong `filtering/io.py` | Module mới, không thay Phase 2 provider; kiểm hard-link filesystem và GPU adapter trên host |
| Tests mới | `tests/unit/test_silver.py`, `test_silver_workflow.py`, `test_local_labels.py`, `test_phase4_analysis.py`, `test_phase4_cli.py` | Synthetic-only; không thay fixtures chung |
| Config | `configs/filtering/f1.yaml` | Candidate defaults; không copy đè config frozen của run thực |
| Contracts registry | `scripts/export_schemas.py`, 23 schemas Phase 4 (10 cũ + 13 bổ sung); tổng laptop 59 | Hợp nhất cả registrations Phase 3 và Phase 4; xuất lại schema sau merge |
| Tài liệu chung | SOT, DECISIONS, STATUS, STATUS_HISTORY, CHANGELOG, README, các README liên quan và TEST_PLAN | Hợp nhất nội dung; **không chọn nguyên file của laptop ghi đè tiến độ PC** |
| Tài liệu riêng | `PHASE4_OFFLINE_WORKFLOW.md`, `PHASE4_LOCAL_TOOLS.md`, file bàn giao này | Giữ làm hợp đồng phạm vi và runbook |

Không sửa `src/vidoclens/student/`, configs student, ML/OCR locks, core CLI registration, API, Phase 2 provider/ledger, dữ liệu hoặc split cũ. CLI Phase 4 là `python -m vidoclens.filtering`, nên không cần tranh sửa `vidoclens.cli` với Phase 3.

ADR dùng ID **ADR-P4-001/002** để giảm nguy cơ trùng số ADR mà PC có thể đã thêm. SOT laptop v1.12; nếu PC cũng nâng version, hợp nhất nội dung và chọn revision mới, không ép quay về version laptop.

## Khi về PC

1. Giữ nguyên checkout/venv/artifacts đang train. Lưu và tự commit code Phase 3 trên nhánh của nó; bảo toàn checkpoint, optimizer/scheduler/RNG, frozen config và run evidence bằng cơ chế sao lưu riêng. Git không mang theo những payload này.
2. Bản đầu `3ae2c4f` đã được owner commit/push. Trên laptop, tự review/stage/commit và push **phần bổ sung lần này** trên `phase4-offline`; assistant không thực hiện các bước Git ghi này. Merge branch hiện chỉ có commit cũ sẽ thiếu working-tree supplement. Không chỉ chuyển `git diff` vì file mới untracked sẽ bị thiếu.
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
- Thêm adapter xuất `SilverTrainingResult` theo [runbook](PHASE4_LOCAL_TOOLS.md#result-exchange-từ-trainer-phase-3): đúng selection/profile/checkpoint/G3/eval hashes, measured completed updates và per-qid exposure counts kể cả zero. Không suy exposure từ cấu hình. L2 null selection/no silver; tất cả raw dev predictions theo cùng protocol.

## Thứ tự sử dụng phần bổ sung

G3 hoàn tất → xác minh local model/license/data + GPU adapter smoke → dev teacher quality pilot → approved train generation → grid dev và explicit freeze → holdout generation/filter/human review → selections/trainer integration → 3-seed L2/P1/P2 và comparison. Có thể nối adapter và kiểm fixtures trước G3, nhưng không công nhận training/G4 từ fixtures. Các đường dẫn data/weights/grants/run artifacts phải khôi phục riêng trên PC.

`PROJECT_OVERVIEW.md`, student/ML locks/Phase 2 provider/root CLI không bị sửa. Kiểm tra hash/interface sau merge dù Git merge sạch; các field attestation/hash không là bằng chứng tự động rằng GPU pipeline đã thực thi đúng.

## Điều kiện đóng Phase 4

Local teacher pilot + silver thật có provenance/quyền, config chốt trên dev_select, audit holdout sau freeze, core P1-full/P1-size/P2 ba seed và so sánh L2 công bằng. Báo retention, nhóm bị loại, noise/false reject, chi phí/compute và CI thích hợp; kết quả âm hợp lệ. Xem [G4 trong SOT](../SOURCE_OF_TRUTH.md#phase-4--chưng-cất-có-kiểm-chứng).
