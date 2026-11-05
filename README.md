# ViDocLens


Hệ thống hiểu biên lai tiếng Việt bằng VLM nhỏ, chưng cất qua nhãn có kiểm chứng OCR và cascade local → API.

**Tài liệu chuẩn:** [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md). Tài liệu này chốt phạm vi, kiến trúc, dữ liệu, phương pháp, thí nghiệm, tech stack, API, triển khai và lộ trình 8 phase. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) được giữ nguyên làm ý tưởng gốc.

## Trạng thái hiện tại

Quy trình làm việc: [CONTRIBUTING](CONTRIBUTING.md) · [bảng phase/việc tiếp theo](docs/STATUS.md) · [CHANGELOG](CHANGELOG.md). Chủ dự án tự kết nối GitHub, commit và push thủ công. Các link data/artifacts trong báo cáo là evidence local, không đi kèm GitHub checkout.

**G0–G4 đã đạt local; Phase 4 hoàn tất.** [Kết quả](docs/PHASE4_RESULTS.md). Phase3 train đủ ba seed G10, L2 dev mean strict EM46,00% so L134,38%; [kết quả Phase3](docs/PHASE3_RESULTS.md). Phase 2 chạy đủ pilot/baselines API trên 150 ảnh, 511 requests, chi phí theo usage 6,080008/20 USD; replay toàn bộ không thêm calls/spend. Benchmark/fallback chọn GPT-5.4 image+OCR (A3), dev strict EM 76,28%; serving chưa bật. [Kết quả/gates](docs/STATUS.md), [báo cáo Phase 2](docs/PHASE2_RESULTS.md), [workflow](docs/PHASE2_WORKFLOW.md).

Phase 1 ingest đủ 9.500 ảnh; freeze containment 19.496 candidate pairs, giữ 4.527 ảnh train_fit và cách ly 2.873 ảnh. OCR 100/100, 260 parity fixtures và R1 training diagnostic đã có số. Đã kiểm tra chéo 38 dòng OCR và bắt đầu OOD với 3 ảnh có giấy phép/24 QA; AI reference theo ADR-021 không là human gold hoặc final benchmark. [Báo cáo Phase 1](docs/PHASE1_RESULTS.md), [OOD data card](docs/data/COMMONS_OOD_SEED_V1.md).

| Thành phần | Đã hoạt động |
|---|---|
| `python -m vidoclens doctor` | Chẩn đoán package và trạng thái foundation; không nạp GPU |
| `GET /health/live` | HTTP 200 |
| `GET /health/ready` | HTTP 503, `model_not_configured` |
| `POST /v1/vqa`, `POST /v1/extract` | Validate ảnh/request; HTTP 501 khi đầu vào hợp lệ |
| Contracts | Chặn nhãn trong teacher input, phân biệt abstention và answer, hỗ trợ đáp án nhiều phần |
| Audit annotations | `python -m vidoclens.data.audit_receiptvqa`; CRC, SHA-256, CSV/ID checks; không xuất QA |
| CSV loader | `python -m vidoclens.data.receiptvqa`; train/dev question-only; gold cần manifest riêng; test bị khóa |
| Metric CPU | Strict + compatible scorer, 260 parity cases; grouped bootstrap, multipart và bounded R1 |
| Pilot local Phase 0 | Student GPU NF4 và OCR CPU, input train-only không gold; chưa tích hợp vào API |
| Ingestion/dedup | Full decode/raw+pixel hash; rotation/crop/gradient candidates; frozen containment và gold plans |
| OCR Phase 1 | 100/100 ảnh G10 train, cache; R1 686 QA (oracle EM 58,02%, không phải student accuracy) |
| OOD seed / AI review | 3 ảnh/24 QA có rights và cross-source audit; 62 lượt local review/adjudication, human flags false |
| Teacher Phase 2 | Responses thật, permission gates, cache/ledger/retry, Batch offline, evaluator và role freeze; G2 đạt, API training export vẫn false |
| Student Phase 3 | Gold-only G10/QLoRA, checkpoint/resume/reload, L1 + L2 ba seed; G3 audit9/9 đạt; chưa tích hợp serving |
| Phase4 | **G4 pass 10/10 local**; 9 matched runs, 12 results, human review thật; [báo cáo](docs/PHASE4_RESULTS.md). Serving vẫn chưa ready |
| Kiểm tra local | Final WSL 485 passed, Ruff/format/schema/policy pass; Windows integration v6 475 passed/10 skipped; xem STATUS để biết phạm vi và evidence |

Phase 3 dùng config JSON được kiểm bằng Pydantic và đóng băng trong plan; [workflow](docs/PHASE3_WORKFLOW.md) ghi lệnh thực tế. YAML serving vẫn là cấu hình thiết kế. Python 3.11.14 Linux/WSL2 đã chạy backward/smoke; G3 đã đạt đủ resume/reload và baselines ba seed; [model card](docs/MODEL_CARD.md). Docker, Gradio và API model backend chưa được chạy xác minh trên máy này; readiness vẫn false cho đến khi tích hợp runtime thật.

## Chạy foundation trên Windows

Nếu chưa có môi trường riêng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[serve,dev]"
```

Kiểm tra và chạy API:

```powershell
.\.venv\Scripts\python.exe -m vidoclens doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m uvicorn vidoclens.serving.api:app --host 127.0.0.1 --port 8000
```

Mở [API docs local](http://127.0.0.1:8000/docs). API chỉ bind loopback. Không cần API key, không tải trọng số và không gọi dịch vụ trả phí khi khởi động.

Trên Linux/WSL2 dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`. Khi được phép thực thi phần GPU của Phase 0, cài PyTorch/OCR trong môi trường ML riêng; core package không kéo toàn bộ GPU stack.

## Demo và container tùy chọn

Cài `.[demo]` vào cùng venv, giữ API chạy ở terminal khác rồi chạy `python app/demo.py`. Demo hiện chỉ hiển thị liveness/readiness.

Nếu máy đã có Docker:

```shell
docker compose up --build
```

Để chạy thêm demo:

```shell
docker compose --profile demo up --build
```

Đây là container **CPU foundation**. Healthcheck container kiểm tra process sống, không chứng nhận model sẵn sàng. GPU image, authentication, reverse proxy HTTPS và monitoring thuộc Phase 6.

## Các phần của dự án

| Đường dẫn | Vai trò |
|---|---|
| `src/vidoclens/` | Modules data, OCR, teacher, filtering, student, verify, eval, serving |
| `configs/`, `prompts/`, `schemas/` | Cấu hình, prompt có phiên bản, schema sinh từ Pydantic |
| `app/`, `infra/` | Demo và cấu hình triển khai |
| `tests/`, `.github/workflows/` | Kiểm thử và CI CPU |
| `data/`, `cache/`, `artifacts/` | Dữ liệu, cache, weights và run outputs; payload không commit |
| `reports/`, `notebooks/` | Bảng/biểu đồ và phân tích |
| `docs/` | Tiến độ, ADR, khảo sát, cards, test plan và runbooks |

Các điểm bắt đầu: [tiến độ](docs/STATUS.md), [quyết định](docs/DECISIONS.md), [khảo sát](docs/LITERATURE.md), [access register](docs/DATA_ACCESS_REGISTER.md), [dự toán](docs/PHASE0_BUDGET.md), [test plan](docs/TEST_PLAN.md), [release checklist](docs/RELEASE_CHECKLIST.md).

## Nguyên tắc triển khai

- Không đưa test/OOD hoặc nhãn ẩn vào training, teacher prompts hay bước chọn threshold.
- OCR support không đồng nghĩa câu trả lời đúng câu hỏi; không fuzzy sửa chữ số.
- Mặc định local, external off, ngân sách API bằng 0 cho tới khi chốt policy và budget.
- Dataset, model, output teacher và code có quyền sử dụng/phát hành riêng; chưa chọn license code để public.
- Thay đổi thiết kế cập nhật SOT và ADR; kết quả thực nghiệm phải có manifest tái lập.

Phase 2 đã hoàn tất **G2** với predictions/metrics/cost/replay/role freeze thật. Runtime hỗ trợ `--env-file .env`; quyền benchmark chỉ theo grant đã duyệt, không cấp API training export hoặc serving external. [Workflow](docs/PHASE2_WORKFLOW.md), [kết quả](docs/PHASE2_RESULTS.md), [STATUS](docs/STATUS.md). Phase 3 student training đã đạt G3; [workflow](docs/PHASE3_WORKFLOW.md) và [báo cáo](docs/PHASE3_RESULTS.md); chủ dự án tự commit/push các thay đổi local.

Phase 4 hoàn tất local theo ADR-P4-003 trên nền G3: [protocol](SOURCE_OF_TRUTH.md#116-tích-hợp-và-thực-thi-phase-4--adr-p4-003), [runbook](docs/PHASE4_EXECUTION.md), [kết quả](docs/PHASE4_RESULTS.md). Phase 5 chưa triển khai.
