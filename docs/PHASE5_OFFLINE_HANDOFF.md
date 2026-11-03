# Bàn giao Phase 5 offline từ laptop sang PC

03/11/2026 · Branch **`phase5-offline`** · Base **`2fa55cd066c74a77ff7ed600150dffbea5bb844e`** trên `phase4-offline`.

Branch được kiểm tra chưa tồn tại trước khi tạo. Thay đổi Phase 5 hiện ở working tree; **owner tự review/stage/commit/push**. Không thêm author/co-author, không đổi Git identity. CI Phase 4 không chứng nhận code Phase 5 chưa commit. Tiến độ/check logs hiện hành ở [STATUS](STATUS.md); lệnh và contracts ở [workflow](PHASE5_OFFLINE_WORKFLOW.md).

## Đã chuẩn bị và còn phụ thuộc

| Phần | Laptop làm được | Còn trên PC / điều kiện gỡ |
|---|---|---|
| P3-check/P3-snap | Numeric guards, text/multipart evidence, field cue/geometry, ambiguity/recheck/traces | G4 student predictions + OCR thật; dev rule evaluation, human error review, chọn/freeze |
| Replay/evaluator | Frozen dev pool, immutable bundle, strict metrics, correction/harm/abstention, paired group CI | Khôi phục archive/splits/inventory/model provenance; không dùng fixture làm metric |
| Cascade library | Local default, exact external gates, 1 fallback/0 retry, teacher verify, SQLite reserve/cache, circuit/deadline | Implement/test real backend theo G2 fallback profile, scoped quyền/budget/giá, raw logging, real timeout; nối API thuộc Phase 6 |
| Routing | Dev_calibrate-only grid/Pareto/cost/coverage, explicit rationale/freeze, code hash | G4/model/filter/verifier freeze; full teacher-all cùng protocol; calibration thật/live measurement |
| Human OOD | Blind packet/blank templates, ≥20% second pass, disagreement adjudication, hash overlap check | Owner lấy nguồn có quyền, review near-duplicates/đa dạng/PII, người xem ảnh, không dùng AI seed cũ làm unseen |
| Final suite | Pin 12 core systems + teacher, selected P2 verifier/router, OOD/source/split/evaluator hashes | Artifacts thật, G5 review; final inference/evaluation/deploy ở Phase 6, execution chưa mở |

Không thể đóng G5 bằng synthetic fixtures, hash tự điền hoặc report từ prediction giả. Không có thay đổi model/filter/router operating point thật trong lượt laptop.

## File ownership / conflict

| Nhóm | Paths | Hợp nhất |
|---|---|---|
| Implementation riêng | `src/vidoclens/verify/` | P3, bundle/pool, OOD, runtime và CLI; `__init__.py` cập nhật từ stub |
| Contracts mới | `contracts/{verification,cascade,calibration,ood_review,final_suite}.py` | 22 schemas mới; không đổi old contracts/F1/TeacherRequest |
| Eval riêng | `eval/{verification,routing}.py` | Reuse strict metrics/bootstrap; không sửa evaluator lịch sử |
| Tests | `test_verifier.py`, `test_cascade.py`, `test_ood_review.py`, `test_phase5_workflow.py` | Synthetic-only, reuse Phase 4 test helpers; giữ Phase 4 dependencies khi chuyển |
| Shared registry | `scripts/export_schemas.py`, generated schemas | Hợp nhất thêm registrations Phase 3 nếu có; export lại, không copy JSON cũ đè code |
| Shared docs | SOT, DECISIONS, STATUS/HISTORY, CHANGELOG, README, schema/test README, TEST_PLAN | Hợp nhất nội dung, không chọn nguyên file laptop ghi đè tiến độ PC |
| Runbooks mới | File này, `PHASE5_OFFLINE_WORKFLOW.md` | Giữ scope/giới hạn/ràng buộc artifacts |

Phase 5 reuse read-only `filtering.io/matching`, frozen loader và strict metrics; không sửa source `student/`, `filtering/`, `teacher/`, `serving/`, root CLI, config/locks, Phase 2 ledger hoặc `PROJECT_OVERVIEW.md`. SOT v1.13/ADR-P5-001 là revision laptop; nếu PC có revision mới hơn, hợp nhất rồi chọn revision mới. Chưa đọc diff PC nên chưa chứng nhận merge sạch hoặc trainer compatibility.

## Trình tự khi về PC

1. Bảo toàn worktree Phase 3, venv, checkpoints/optimizer/scheduler/RNG và artifacts trước merge. Owner tự commit code Phase 3 trên branch của nó; dữ liệu/checkpoints cần backup riêng vì Git ignore.
2. Owner review/commit/push Phase 5 trên laptop sau kiểm tra; không chỉ chuyển `git diff`, vì file mới untracked sẽ bị thiếu. Không đưa data/artifacts/cache/.env đi cùng code.
3. Trên PC tạo nhánh tích hợp từ Phase 3 đã lưu; merge **Phase 4 đến `2fa55cd` trước**, rồi merge các commit mới của `phase5-offline`. Branch Phase 5 kế thừa Phase 4, không phải nhánh độc lập từ Phase 2. Nếu đã cherry-pick Phase 4, so nội dung/history trước tránh áp trùng; không reset/force-push để giải quyết conflict.
4. Shared docs giữ cả tiến độ PC và phần offline. `scripts/export_schemas.py` giữ registrations cả hai nhánh rồi regenerate schemas. So lại filenames/interfaces dù Git báo merge sạch.
5. Chạy CPU checks bên dưới, đối chiếu G3/G4/source artifacts. Nối **export adapter** của trainer sang `VerificationBatch`, không sửa sampler/training chỉ để khớp fixtures. Mỗi qid join đúng image/hash/group; failed/missing không bỏ mẫu số.
6. Hoàn tất G3/G4 → xuất dev student/OCR thật → verifier candidate/evaluation/human review → freeze dev_select → đủ quyền/budget để lấy teacher-all dev_calibrate → routing grid/selection → live integration tests và human OOD mới → preregister → review G5. Chỉ sau đó làm Phase 6 API/final suite/deploy.

```text
python scripts/export_schemas.py
python scripts/export_schemas.py --check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m vidoclens.verify --help
python -m vidoclens doctor
python scripts/check_repo.py
git diff --check
```

Dùng interpreter venv phù hợp trên PC, không đổi CUDA/driver hay ML locks cho CPU tests. Doctor vẫn phải phản ánh model thật chưa load; đừng đổi readiness để vượt checks.

## Boundary cần review trước real execution

- Hash/student protocol/filter/fallback profile/G4 evidence phải đến từ artifacts thật. Fixture flag được truyền xuyên suốt; không sửa false để dùng kết quả tổng hợp.
- Binding canonical JSON khác file bytes SHA; runbook chỉ rõ trường nào dùng cách nào. Lưu cả manifests gốc bên cạnh binding. Tạo code hash bằng helper, không nhập thủ công.
- Pipeline hiện chưa xác minh toàn bộ bundle G4/giá/license chỉ bằng hash: adapter/owner chịu trách nhiệm đối chiếu; ghi evidence riêng.
- Verifier chưa là general semantic model, geometry/cues có recall thấp. Kiểm các lỗi nhầm field, numeric format/unit và snap harm trên dev thật; không tune trên test/OOD.
- Backend phải xác minh image bytes và exact provider profile, giữ raw response, enforce remaining I/O timeout và reservation price bound. Library timeout không preempt backend bị block. Vượt reserve ghi actual cost/abstain; không hứa budget cap tuyệt đối khi giá bound sai.
- Không chia một budget thành nhiều ledger không phối hợp; không dùng Phase 2 grant/ledger thay approval mới. Unknown/crashed reservation không tự clear/retry. Circuit breaker phải dùng chung theo provider.
- OOD review JSON cần người thật xem ảnh local; mọi quyền/near-dedup/human fields là attestations. Trường `human_review_requirement_met` chỉ kiểm các records đã nộp, không chứng nhận nguồn/người/size/diversity. AI seed Phase 1 giữ nguyên provenance và nằm ngoài unseen final OOD.
- Final manifest chỉ preregistration: `execution_enabled=false`, `g5_certified=false`; test gold vẫn khóa, model API vẫn 501/readiness 503 như trước.
