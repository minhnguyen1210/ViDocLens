# Trạng thái ViDocLens

Cập nhật: **02/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0 và G1 đã đạt; Phase 2 chưa bắt đầu.** G1 hoàn tất theo phương án dùng AI được chủ dự án yêu cầu (ADR-021), không chứng nhận human gold hoặc final OOD benchmark. Lượt hiện tại chuẩn hóa quản lý repo và bàn giao cho commit đầu tiên.

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định task/commit/push; [nhật ký cũ](STATUS_HISTORY.md) giữ các mốc thực thi; [ADR](DECISIONS.md) ghi quyết định. Đây là nơi duy nhất ghi trạng thái phase hiện hành; không suy phần trăm dự án từ số phase đã xong.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước mở tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu và môi trường khả thi | **done** | G0: GPU/OCR pilot thật, locks dựng lại; [runbook](PHASE0_ENVIRONMENT.md), ADR-018 |
| 1 | Data pipeline, OCR, evaluator, OOD khởi đầu | **done** | G1 theo ADR-021; [báo cáo](PHASE1_RESULTS.md), [gate local](../artifacts/phase1/g1_ai_gate_v2.json) |
| 2 | Teacher, ledger/cache và baseline API | planned | G1 đã đạt; phần code offline có thể làm, chạy API thật còn gate quyền/budget |
| 3 | Student training và gold-only baseline | planned | G1 + GPU lock đã có; training smoke/reload/resume và dev metrics chưa chạy |
| 4 | Silver và chưng cất có kiểm chứng | planned | Cần G2, G3 và quyền dùng training labels |
| 5 | Verifier/cascade, calibration, full OOD | planned | Cần student/teacher bundle; full OOD human validation chưa có |
| 6 | API/demo thật, đánh giá cuối và deploy | planned | Cần G5, runtime/host và release gates |
| 7 | Báo cáo, release và bàn giao tái lập | planned | Cần final suite và reproducibility/release evidence |

Owner của các phase: chủ dự án. Thời gian dự kiến ở SOT §22 là kế hoạch, không phải ngày đã hoàn thành. `planned`, `in_progress`, `in_review`, `blocked`, `done` theo CONTRIBUTING; chỉ đổi `done` khi đủ gate, không chỉ vì đã viết code.

## Hàng đợi công việc

| ID | Việc | State | Owner / phụ thuộc | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| REPO-001 | Chuẩn hóa workflow và tiến độ | done | Assistant chuẩn bị local theo yêu cầu | STATUS/history, commit guide, templates, kiểm tra repo/schema và tests có kết quả |
| REPO-002 | Review và commit/push đầu tiên | done | **Chủ dự án đã tự push** | Local/remote main cùng 03ac245; CI Python 3.11/3.12 đạt |
| P2-001 | Chốt contract/role/policy teacher | planned | G1; không cần gọi API | Thiết kế input không gold, output/error states, role/budget; ADR nếu đổi SOT |
| P2-002 | Provider adapter, cache và ledger | planned | P2-001 | Tests offline: cache key, budget reservation, retry, missing/refusal/truncate |
| P2-003 | Pilot teacher và baseline dev | planned | P2-002 + quyền external/budget/model snapshot | Evidence pilot 50 ảnh/dev metrics/cost theo SOT, không dùng test/OOD tuning |

REPO-002 đã hoàn tất; P2-* chưa triển khai. Khi task lớn cần chi tiết, dùng [mẫu task](templates/TASK.md) hoặc GitHub Issue; STATUS chỉ giữ dòng tổng quan và link.

## Ràng buộc và blocker cụ thể

| Mục | Trạng thái / tác động | Owner / điều kiện gỡ |
|---|---|---|
| API budget | Cap = 0; chưa được gọi API trả phí | Chủ dự án chốt budget, quyền external và điều khoản provider trước P2-003 |
| Quyền teacher output | Chưa chốt quyền distillation qua API; local 4B mới là candidate | Kiểm [access register](DATA_ACCESS_REGISTER.md), pilot nhánh có quyền trước sinh silver |
| AI references | Không human gold; OOD seed không dùng confirmatory evaluation | Full OOD/human validation ở Phase 5; không sửa flag để đóng gate |
| API runtime/deploy | `inference_ready=false`, model backend chưa tích hợp | Phase 6; không coi health/live hoặc CI CPU là inference/deploy thành công |
| GitHub | Repo private, local/remote main khớp; CI đã đạt | Chủ dự án tiếp tục tự commit/push; assistant không publish/sync code |

Các ràng buộc trên không chặn viết code/tests offline của Phase 2. Giữ driver hiện tại; không tự reboot, public hosting hoặc mở test gold.

## Bằng chứng G0/G1 đã đóng

| Hạng mục | Kết quả đã đo | Bằng chứng |
|---|---|---|
| Môi trường | WSL2 Ubuntu 24.04.5, Python ML/OCR 3.11.14, RTX 3060 12 GB; driver 617.42 | [Môi trường](PHASE0_ENVIRONMENT.md), [history](STATUS_HISTORY.md) |
| ReceiptVQA | 9.500 ảnh/64.812 QA; 19.496 containment constraints | [Data card](data/RECEIPTVQA_CONTAINMENT_V1.md) |
| Split | 4.527 train_fit, 504 audit, 456 dev_select, 190 dev_calibrate, 950 test, 2.873 quarantine | [Frozen summary local](../data/splits/receiptvqa_containment_v1/summary.json); không sửa trong lượt này |
| OCR | 100/100 ảnh G10 train, 4.587 spans; p50 6,706 s/p95 9,832 s | [Phase 1](PHASE1_RESULTS.md) |
| OCR AI reference | 38 dòng/3 ảnh; CER 55/460 = 11,9565%; 1 uncertain excluded, 1 missed line là deletion | [G1 gate local](../artifacts/phase1/g1_ai_gate_v2.json); không là corpus/human CER |
| Evaluator/R1 | 260 parity cases; R1 686 train QA, EM 58,0175%, F1 69,9707%, ANLS 64,4129% | [Báo cáo](PHASE1_RESULTS.md); oracle có gold, không là student accuracy |
| OOD seed | 3 ảnh Commons/24 QA, 18 answerable + 6 unanswerable; zero candidates trong 28.503 cặp theo protocol | [OOD data card](data/COMMONS_OOD_SEED_V1.md); có nguồn/license, không là final benchmark |
| AI review | 62 local reference-free outputs + adjudications; same student base, không independent human/model family | [Provenance local](../artifacts/phase1/ai_review_final_v1/provenance.json) |

Các link artifacts/data là evidence **local, Git ignored**; người clone repo đọc báo cáo tổng hợp và làm theo workflow để có evidence được phép. GitHub checkout không kèm dataset/weights/private outputs.

## Kiểm tra local mới nhất — nâng cấp workflow

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python 3.14.9 — pytest | **216 passed, 7 skipped**; NumPy cases chạy đủ Linux |
| WSL ML-repro Python 3.11.14 — pytest | **223 passed** |
| Ruff check / format | Đạt cả hai; format kiểm 87 files |
| Schema drift | **27 schemas match**, chế độ `--check` không ghi file |
| File policy / YAML | Đạt với 179 candidates tại lúc kiểm; không phải secret/content/license scan |
| Staged diff | Đã chạy checker, báo chưa có staged files; chưa đủ điều kiện kiểm nội dung commit, người dùng chạy lại sau khi tự stage |
| GitHub CI | **Đạt** trên Python 3.11 và 3.12 tại commit 03ac245; [run 41479278954](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41479278954) |
| Docker/GPU | Không chạy thêm trong lượt workflow; GPU evidence trước đó thuộc G0/G1 |

18 tests mới kiểm file policy, index khác worktree và schema drift thiếu/sai/dư mà không sửa file. Có warning Starlette/httpx đã biết; chưa đổi dependency để xử lý warning này.

## Bàn giao nâng cấp workflow — trước push

- Đã làm: tách hiện trạng khỏi history, quy ước task/branch/commit, mẫu Issue/PR, CHANGELOG; thêm read-only checks và CI permissions read-only.
- Tài liệu điều hành: SOT v1.8/ADR-022; không thay scientific gates hoặc sửa kết quả Phase 0–1.
- Git local tại lúc kiểm: `main`, chưa có commit/staged files; đã thấy `origin` là `https://github.com/minhnguyen1210/ViDocLens.git`. Assistant chỉ đọc cấu hình này, không tạo/sửa remote, stage/commit hoặc push.
- Commit đầu tiên đề xuất: `feat: add ViDocLens foundation and phase 1 pipeline`.
- Việc tiếp theo của chủ dự án: [review/stage/commit/push thủ công](../CONTRIBUTING.md). Việc kỹ thuật sau đó: P2-001; Phase 2 chưa bắt đầu.

## Bàn giao mới nhất — xác minh push ngày 02/11/2026

- Chủ dự án đã push `03ac245e6d31ef05af5fdc174dfbbbf5bca565b3`, tiêu đề `feat: add ViDocLens foundation and phase 1 pipeline`; `git ls-remote` xác nhận remote main khớp HEAD local.
- Repo `minhnguyen1210/ViDocLens` là private, default branch main. CI run 41479278954 completed/success, cả Python 3.11/3.12 đạt. Docker Compose config đạt không đồng nghĩa container/GPU deployment đã chạy.
- Git sạch trước kiểm tra. Tracked data/artifacts/cache/reports chỉ có README/.gitkeep; env chỉ có `.env.example`; file policy đạt. Không coi đây là secret/content scan.
- Assistant chỉ đọc Git/GitHub và cập nhật STATUS local; không stage/commit/push hoặc thay remote. Bản cập nhật tài liệu này chưa thuộc commit/CI vừa xác minh.
- Bước tiếp theo: P2-001; Phase 2 chưa bắt đầu, API cap vẫn 0.

Mỗi lần bàn giao cập nhật bảng kiểm tra và mục này với kết quả thật. Khi nhật ký dài, chuyển các mốc cũ vào STATUS_HISTORY, giữ link evidence và mốc thời gian. Không sửa artifact cũ để khớp hiện trạng mới.
