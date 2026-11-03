# Phase 2 — Teacher, ledger và baseline API

Protocol `phase2_api_v1`, ngày 02/11/2026, SOT §10/13/22 và ADR-023. Đây là workflow thực thi, không phải tuyên bố G2 đã đạt. Hiện trạng và số đo thật ở [STATUS](STATUS.md); kết quả local ở [PHASE2_RESULTS](PHASE2_RESULTS.md).

## Phạm vi đã khóa

- Integration: 50 receipt đầu của OCR G10 train đã chạy Phase 1, **344 câu hỏi / 59 request groups**. Chỉ dùng question-only loader, không nạp gold để tạo request hoặc sửa prompt theo đáp án train.
- Chất lượng: 100 component `dev_select`, chọn bằng seed42 và thứ tự `ocr-quality` trước inference, **666 câu hỏi / 113 request groups mỗi baseline**. Cùng ảnh/câu hỏi cho A1, A2, A3, A5; không chọn theo OCR confidence/đáp án. Không mở test, OOD, dev_calibrate hoặc audit để chọn teacher.
- A1: OCR text → strong; A2: ảnh → strong; A3: ảnh + OCR → strong; A5: cùng prompt image+OCR của A3 → cheap. A5 được định trước, không thử trên test. A4 few-shot là tùy chọn, chưa thực hiện.
- Tổng **150 ảnh duy nhất / 511 requests trước retry**, không phải 511 ảnh. Mỗi ảnh chia tối đa 8 câu và 12.000 UTF-8 bytes câu hỏi; tất cả qid phải xuất hiện đúng một lần trong mỗi experiment.
- Prompt `teacher_vqa_v2`: giữ raw digits/dấu/newline, không ép `¡sep¿` từ paper vào CSV, không suy tiền tệ/năm hoặc làm phép tính. Evidence là trích text, không CoT; lệnh trong ảnh/OCR/question là dữ liệu không tin cậy.

## Candidate và dự toán để duyệt

Candidate strong `gpt-5.4-2026-03-05`, cheap `gpt-5.4-mini-2026-03-17`; Responses, `store=false`, service tier default, reasoning none, image detail high, output cap4096. Account access của cả hai đã xác minh bằng các lượt chạy thật; quyết định role và số đo ở [báo cáo](PHASE2_RESULTS.md). Giá standard input/cached/output mỗi triệu token lần lượt **2,50/0,25/15 USD** và **0,75/0,075/4,50 USD**, kiểm 02/11/2026; GPT-5.4 có tier đắt hơn trên272k input. [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

Price cards nằm trong `configs/teacher`, có URL/ngày/SHA256 tài liệu công khai. Phải kiểm lại trước live run; đây không phải lock về giá/tính khả dụng của provider.

**Đã được chủ dự án duyệt: cap20 USD cho pilot + A1/A2/A3/A5, mỗi process chạy sync tuần tự; tối đa2 experiment processes đồng thời dùng chung ledger theo ADR-024.** Approval trong chat ngày02/11/2026 đã lưu ở `artifacts/phase2/approval.json`; không xin lại quyền này. Không thuê GPU, không sinh nhãn huấn luyện, không upload Batch trong đề xuất này. Nếu cap không đủ, dừng và ghi incomplete; không tự nâng cap.

Sensitivity chỉ để hiểu quy mô, **không phải token đo được hoặc báo giá đảm bảo**:

| Giả định mỗi request, không cached-input discount | 398 strong + 113 cheap, trước retry |
|---|---:|
| 1.200 input / 256 output | 2,95 USD |
| 5.000 input / 1.500 output | 15,12 USD |

Ledger không dùng các giả định này để reserve. Nó reserve full documented input limit ở tier đắt nhất + output cap: **5,342160 USD/strong attempt**, **0,222432 USD/cheap attempt**. Tổng bound511 requests không retry là **2.151,314496 USD**, cực bảo thủ, không phải dự báo chi phí. Với cap20, sync settle usage sau mỗi request sẽ giải phóng phần chưa tiêu để request sau tiếp tục; một Batch lớn phải reserve cả shard trước upload nên có thể không fit cap này. Request không rõ phí vẫn giữ toàn reservation, retry phải reserve thêm.

## Quyền trước khi gửi

`configs/teacher/permission.example.json` vẫn mặc định cap0/quyềnfalse cho clone an toàn. Chủ dự án đã xác nhận quyền và đồng ý gửi **ảnh ReceiptVQA cùng câu hỏi/OCR** cho OpenAI API phục vụ benchmark, phạm vi dữ liệu có thể chứa thông tin trên hóa đơn; kiểm điều khoản tài khoản và retention. `store=false` không có nghĩa zero retention; Batch/files có vòng đời riêng. [Data controls](https://developers.openai.com/api/docs/guides/your-data).

Đã lưu permission record thật tại `artifacts/phase2/approval.json`: archive/split hash, model snapshots, exact511 request keys, người/ngày/căn cứ duyệt, cap20.000.000 micro-USD. Đây là owner attestation về terms/retention/quyền dữ liệu, không phải assistant đã đọc hợp đồng tài khoản. Không bật `training_export_allowed` cho benchmark. Không lưu API key trong record, config, Git hoặc chat. Runtime lấy key từ `OPENAI_API_KEY`, hoặc dùng `--env-file .env` để nạp riêng key từ file do chủ dự án chỉ định sau permission gate; estimate/dry-run không đọc key. File không được eval/interpolate và không bật serving external flag. Cấu hình environment cho process chạy riêng sau khi chủ dự án cấp quyền. Không thay hệ thống/driver.

API chỉ dùng cho benchmark khi quyền distillation chưa rõ. Evaluation cache không thể export training. Label role local4B của ADR-014 vẫn là candidate chưa pilot; phải kiểm license/VRAM/chất lượng trước Phase4. Chọn fallback từ dev quality/cost nhưng triển khai cascade thuộc Phase5.

## Lệnh local

Tại repo root, Windows dùng `.venv/Scripts/python.exe`; trong WSL dùng interpreter phù hợp. Dependency `teacher` là optional (`httpx`, `PyYAML`), không kéo ML/OCR vào core. Không cần cài thêm vào Windows hiện tại vì dev environment đã có chúng.

```powershell
.venv/Scripts/python.exe -m vidoclens teacher plan artifacts/phase2/api_plan_v1
.venv/Scripts/python.exe -m vidoclens teacher estimate artifacts/phase2/api_plan_v1 --output artifacts/phase2/estimate_v1.json
```

`plan` kiểm split/hash ảnh/OCR, loader không có answer field; ghi immutable manifest/requests ở thư mục mới. `estimate` không gọi mạng, không tạo spend, không đọc API key. OCR cho100dev đã chạy local bằng cùng stack Phase1; hashes/profile/số đo ở artifacts riêng, không sửa dữ liệu/split/Phase1 evidence.

Approval đã có. Lần thử `live_pilot_v1` dừng vì `API key not configured`,0 API calls/0 charge. Chủ dự án chọn tự cấu hình `OPENAI_API_KEY` cho process rồi báo tiếp tục; biến ở một terminal khác không tự truyền ngược vào process đang chạy. Runner tùy chọn `scripts/run_phase2_live.ps1` hỏi key ẩn trong PowerShell local, giữ key trong process và khôi phục environment khi thoát; không nhập key qua chat. Runner đã parse syntax, chưa chạy interactive/live.

Chủ dự án đã cung cấp `.env` và yêu cầu tiếp tục. CLI live dùng `--env-file .env` (không in/lưu key). Pilot thật đã hoàn tất 59/59 groups; xem STATUS cho kết quả mới nhất của campaign. Sau pilot mới chạy dev, tối đa2 experiments đồng thời; timing báo rõ overlap. Nếu cần đổi prompt/model/chunk, lập version/manifest mới; không sửa run cũ. Không dùng kết quả pilot train để tối ưu gold accuracy. Các đường dẫn dưới ghi lại campaign thực tế; thư mục đã tồn tại không được ghi đè, lần thực thi mới phải chọn tên mới.

```powershell
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/live_pilot_v2 --experiment pilot --permission artifacts/phase2/approval.json --env-file .env
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/live_A1_v1 --experiment A1 --permission artifacts/phase2/approval.json --env-file .env
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/live_A2_v1 --experiment A2 --permission artifacts/phase2/approval.json --env-file .env
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/live_A3_v1 --experiment A3 --permission artifacts/phase2/approval.json --env-file .env
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/live_A5_v1 --experiment A5 --permission artifacts/phase2/approval.json --env-file .env
```

Chạy lại cùng experiment vào thư mục mới kiểm cache replay: cache hợp lệ trả nguyên status/labels, không gọi mới; error cache không trở thành success. Request active/crashed dừng để reconcile. Không xóa DB để né cap hoặc tạo cap mới cho cùng campaign. DB có cap immutable; đổi cap cần migration/rollover có carry-over spend và approval, chưa có lệnh tự động nâng budget.

Evaluator ở `vidoclens.eval.teacher` chỉ join predictions với dev_select gold, không gọi provider. CLI `teacher evaluate --help` chỉ dẫn truyền các run dirs; báo strict_nfc_v1 EM/token-F1/ANLS và LiGT-compatible accuracy/set-F1/ANLS riêng. Null/error/missing giữ trong mẫu số. Cache replay latency không trộn với network latency; usage, attempt history và cumulative ledger cùng run delta phải được báo.

## Cache, lỗi và khôi phục

- Identity chứa provider/endpoint/snapshot/role, ordered qids/questions, prompt/schema/wire policy/version, ảnh bytes hash, OCR text/provenance, preprocessing/detail/decoding, partition/purpose. Đường dẫn ảnh có thể đổi nhưng bytes phải khớp trước gửi.
- SQLite transaction reserve và claim request; hai process không được cùng submit một key. Lưu raw mỗi attempt và raw+parsed final cache kèm checksum; message tự do của HTTP401/403 được bỏ có marker để tránh lưu mảnh credential do provider echo. SQLite WAL không bật trên repo Windows mount; không coi SQLite file share giữa nhiều máy là database distributed.
- 429/timeout/5xx retry tối đa2 theo config, tối đa3 trong engine, backoff+jitter; tôn trọng Retry-After. Nếu phải chờ hơn60s thì kết thúc request/run thay vì retry sớm. Auth/schema/refusal/incomplete không auto retry.
- Timeout/5xx/usage thiếu/model hoặc tier sai giữ `uncertain_charge`. Kết quả schema đúng nhưng model/usage sai cũng không cấp success. Nếu measured cost vượt reservation do drift thì ghi spend thật, budget remaining âm sẽ chặn request tiếp theo; không sửa số để “đạt cap”. Cap là accounting guard của campaign theo price snapshot, không giới hạn chi tiêu từ ứng dụng khác trong cùng account.
- `teacher reconcile <ledger> <cap_micro_usd>` chỉ xem unresolved; khi settle phải có `--attempt-id`, `--actual-micro-usd`, `--evidence` từ provider accounting. Không tự release theo tuổi record. Reconcile phí không tự cho resubmit một request không rõ đã chạy.

## Batch

`teacher batch-prepare` tạo JSONL private offline, shard cùng model theo bytes + full input-token bound + số request. `batch-submit` cần quyền Batch riêng, reserve cả shard atomically trước upload; journal append/fsync lưu attempt/file/batch IDs. Mạng mất sau POST không được auto resubmit. Tài liệu hiện tại nêu giảm50%, window24h, tối đa50.000 requests/200MB; kiểm lại model/account limits trước gửi. [Batch guide](https://developers.openai.com/api/docs/guides/batch).

`batch-reconcile` chỉ settle khi job terminal, đọc cả output/error file, join bằng `custom_id` không theo thứ tự. Unknown/duplicate IDs lỗi trước mutation. Entry `batch_expired` xác nhận chưa chạy mới release và eligible resubmit; missing không có record giữ uncertain. Optional `--reopen-unexecuted` chỉ mở những key này; `batch-prepare --eligible-from <reconciliation.json>` tạo shard mới **chỉ gồm eligible keys**, không gửi lại shard cũ có successes. `--delete-files` xóa đúng input/output/error file của job sau khi đã lưu bản local và reconcile. Batch responses dùng chung parser/cache/ledger; chạy sync CLI cùng key sau reconcile sẽ chỉ xuất cached results để đưa vào evaluator.

## Đóng G2

Để xét G2 phải có đủ các bằng chứng sau; tests hoặc OCR riêng lẻ không thay thế live benchmark:

1. Permission/provider record và cap được duyệt, snapshots thật/account access xác minh.
2. Pilot50ảnh có raw+parsed/status/usage/cost thật; mọi invalid/refusal/missing được ghi.
3. A1/A2/A3/A5 trên cùng100dev, EM/F1/ANLS và chi phí thật; tách cached/network latency. Không đạt metric kỳ vọng vẫn báo trung thực.
4. Cache rerun thật không phát sinh calls/spend mới; budget/retry/Batch edge tests pass.
5. Freeze benchmark/fallback model+prompt+modality theo dev; label role nêu rõ nhánh có quyền hoặc local candidate cần pilot trướcPhase4. SOT/ADR/STATUS khớp.

Gate artifacts/report thiếu mục nào ghi pending/blocker, không điền metric0 thay cho chưa chạy và không gọi unit mocks là API pilot. Assistant không stage/commit/push; chủ dự án tự thực hiện Git theo CONTRIBUTING.

Role selection được khóa trước dev outputs theo `configs/teacher/selection_v1.json` và ADR-024. Finalizer `python -m vidoclens.eval.phase2 --help` kiểm raw-result hashes, cached results, live/replay coverage, ledger, checks và xuất metrics/CI/role freeze/G2 report local; không gọi provider.

Cache replay phải chạy sau khi mọi live process kết thúc để so ledger trước/sau chính xác. Có thể chỉ định một credential file **không tồn tại**: cache hit không đọc key; nếu thiếu cache thì runner dừng trước API. Ví dụ cho A1, lặp tương tự cho pilot/A2/A3/A5 với thư mục mới:

```powershell
.venv/Scripts/python.exe -m vidoclens teacher run artifacts/phase2/api_plan_v1 artifacts/phase2/replay_A1_v1 --experiment A1 --permission artifacts/phase2/approval.json --env-file artifacts/phase2/no_credential_for_replay.env
```

Finalizer chỉ đọc evidence đã lưu, join dev gold và ghi thư mục mới:

```powershell
.venv/Scripts/python.exe -m vidoclens.eval.phase2 --plan-dir artifacts/phase2/api_plan_v1 --live-dirs artifacts/phase2/live_pilot_v2 artifacts/phase2/live_A1_v1 artifacts/phase2/live_A2_v1 artifacts/phase2/live_A3_v1 artifacts/phase2/live_A5_v1 --replay-dirs artifacts/phase2/replay_pilot_v1 artifacts/phase2/replay_A1_v1 artifacts/phase2/replay_A2_v1 artifacts/phase2/replay_A3_v1 artifacts/phase2/replay_A5_v1 --permission-path artifacts/phase2/approval.json --checks-path artifacts/phase2/checks_live_v2/summary.json --output artifacts/phase2/final_v1
```

Chi phí từng experiment được cộng theo attempt/request key trong ledger; không cộng các delta ledger của run chồng thời gian vì sẽ đếm hai lần. Cost báo cáo là usage thực × price card đã khóa, chưa là đối soát hóa đơn tài khoản. Mẫu số quality giữ cả lỗi schema/refusal/null/missing; không gọi lại nhóm lỗi chỉ để cải thiện bảng điểm.
