# Kế hoạch kiểm thử và gate

**Tài liệu mô tả kiểm thử cần có xuyên dự án.** Một test được liệt kê không có nghĩa đã được cài đặt hoặc đã pass. Kết quả thực tế đi trong run/CI artifact và [STATUS.md](STATUS.md).

| Gate | Kiểm tra có ý nghĩa | Bằng chứng chấp nhận |
|---|---|---|
| Nền móng | Import package; liveness; readiness fail khi chưa load model; inference scaffold trả lỗi tường minh | CI log + HTTP contract, không trả đáp án giả |
| Dữ liệu | Corrupt image; duplicate xuyên nguồn/split; QA cùng document; quyền unknown; hidden-label access | Fixture tái hiện lỗi bị chặn trước teacher/training |
| Metric | NFC; giữ dấu tiếng Việt; ANLS sát ngưỡng; multi-reference; empty/abstention; denominator; numeric ambiguity | Expected outputs tính tay + đối chiếu official scorer khi có |
| OCR | Rotation, tọa độ sau resize, cache invalidation khi đổi weights/preprocess, OCR failure | Fixture ảnh synthetic hoặc có quyền công bố; provenance đủ |
| Teacher | Missing/duplicate qid, refusal, truncated JSON, invalid evidence, retry, timeout, cost reserve/reconcile | Mock provider không gọi trả phí; không mất/nhân record |
| Training | Loss chỉ trên assistant answer, image tokens không bị mask sai, gradient adapter, save/resume | Smoke trên mẫu nhỏ + adapter load roundtrip |
| Filtering | Chuỗi đúng chữ nhưng sai trường; số khác một chữ số; duplicate candidates; OCR không nhận ra đáp án đúng | Filter decisions + reason codes khớp ý nghĩa thiết kế |
| Verifier/router | Sửa sai thành đúng và đúng thành sai; no external consent; exhausted budget; teacher fail | Trả lời/từ chối đúng policy; không fallback âm thầm |
| API/Track B | File bytes và MIME, oversized/decompression input, question length, null field, raw/normalized/evidence | Contract + integration fixture, không suy diễn trường thiếu |
| Deployment | Model readiness, bounded concurrency, GPU OOM, timeout, restart, auth/rate limit, rollback | Smoke/load/rollback log trên host đích |

## Các trường hợp bắt buộc

**Metric:** `125.000` và `125.001` phải bị phát hiện là sai số; không bỏ mọi dấu chấm/phẩy rồi kết luận đúng khi format mơ hồ. Scorer official và scorer normalized bổ sung được báo cáo tách biệt. Câu từ chối không được bỏ khỏi mẫu số all-question accuracy.

**Grounding:** ảnh có `Tổng cộng: 125.000` và `Khách đưa: 200.000`; trả `200.000` cho câu hỏi tổng tiền phải thể hiện sai trường dù OCR support là thật. Fuzzy matching không được âm thầm thay chữ số hoặc chọn giữa nhiều evidence tương đương.

**Chi phí:** hai worker/request đồng thời không vượt budget qua race condition; retries và Batch partial results không double count; cache key đổi khi image, question/order, model, prompt, OCR hoặc sampling thay đổi. Cache của external request không được làm mất kiểm tra quyền hiện tại.

**Privacy:** local mode và `allow_external=false` có test chứng minh không gọi provider, kể cả khi OCR/student lỗi. Log có kiểm tra không lộ API key/base64/PII. Không cho client truyền path máy chủ hoặc URL tùy ý.

**Track B:** thiếu ngày/giờ/tiền tệ cho `null` hoặc trạng thái thiếu phù hợp schema. Không tự bổ sung timezone/ngày/đơn vị từ giả định. Field precision/recall/EM và record completeness được đo riêng với Track A.

## Kiểm thử nghiên cứu

P1/P2 dùng cùng teacher pool, gold split, student initialization và seed. Có so sánh matched-size và matched-compute; log số mẫu bị lọc và số update. Primary comparison dùng `k=10%` trong `train_fit`; audit holdout không tham gia fit/tuning. Kiểm tra bootstrap resample theo document/duplicate cluster và ghép cặp cùng đơn vị giữa hệ thống.

Trước final test, khóa toàn bộ candidate configurations, thresholds và bảng so sánh dự kiến. Một chiến dịch final test có thể chạy mọi hệ thống/seeds đã đăng ký; không cần hiểu “một lần” là chỉ một model được chạy. Sửa lỗi scorer sau freeze phải ghi protocol amendment và tái chạy đồng đều mọi hệ thống liên quan.

## Phân tầng và vận hành CI

PR chạy kiểm tra nhanh không cần GPU/API key: lint, import, unit, schema/contract và fixture dữ liệu nhỏ. Integration GPU/paid API là job riêng với artifact, budget và data permission; chưa có phần cứng thì ghi `not run`, không đổi thành pass. Release gate thêm image build, scan dependencies/secrets, smoke host đích, tải giới hạn và rollback rehearsal.

Chỉ thêm test khi bảo vệ một hợp đồng, rủi ro thực hoặc regression; không tạo test chỉ để xác nhận một placeholder trả hằng số ngoài yêu cầu scaffold trung thực.

## Phần đã hiện thực cho annotations/metric CPU

[test_receiptvqa_loader.py](../tests/unit/test_receiptvqa_loader.py) kiểm tra output không gold, default-safe view, raw newlines/NFC, namespace ID, selected gold theo toàn receipt, group không vượt partition/gold selection, hash/coverage manifest, test bị khóa trước đọc, selected reader không mở test CSV, malformed input/CRC và CLI không lộ payload.

[test_metrics.py](../tests/unit/test_metrics.py) dùng expected values tính tay cho NFC, dấu/case/số/whitespace, multiset F1, ANLS tại ngưỡng, multi-reference/full multipart, missing/abstain/error denominator và report consistency. Đây là strict protocol. Phase 1 bổ sung [test_phase1.py](../tests/unit/test_phase1.py) cho containment/quarantine, cache identity/corruption/concurrent publication, grouped bootstrap, bounded oracle, CER và AI/human boundary. Upstream parity chạy riêng bằng [script](../scripts/check_metric_parity.py), 260 cases trên nguồn/wheel SHA-pinned. Kết quả thực và giới hạn human/OOD ở [Phase 1 report](PHASE1_RESULTS.md); G0 đã đạt.


## Phase2 đã hiện thực

[test_teacher.py](../tests/unit/test_teacher.py) có61 cases bảo vệ question-only/scoped grants, qid/strict output states, digits/newlines, đầy đủ cache identity, payload hash, budget concurrency/atomic shard reserve, retry/uncertain accounting, checksum/overrun, Batch unordered/expired/missing/idempotency và attempt mapping. CLI permission gate chạy trước credential/output; auth failure dừng campaign. Fixtures là synthetic và MockTransport, không chứng nhận provider/account hoặc chất lượng teacher.

OCR 100 dev, frozen 511-request plan, hash rerun và payload validation có evidence ở [PHASE2_RESULTS](PHASE2_RESULTS.md). Live pilot và bốn baselines đã hoàn tất; 511 cache replays không phát sinh calls/spend; metric/CI/role freeze/G2 report từ dữ liệu thật. Batch upload chưa chạy vì grant không bao gồm Batch; offline edge cases không chứng nhận live Batch.

[test_teacher_credentials.py](../tests/unit/test_teacher_credentials.py) có 8 cases về nạp `.env` tường minh, malformed/duplicate/missing values, không eval hoặc log secret; chỉ dùng fake keys. [test_phase2_finalization.py](../tests/unit/test_phase2_finalization.py) có 4 cases về chất lượng/cost tie-break, biên fallback 2pp và từ chối run chưa hoàn tất. Full suite tại mốc Phase 2: Windows 289 passed/7 skipped, WSL 296 passed; logs/check hashes được dẫn trong STATUS. G2 đạt không chứng nhận training, cascade hoặc serving readiness.


## Phase 4 offline đã hiện thực

[test_silver.py](../tests/unit/test_silver.py) và [test_silver_workflow.py](../tests/unit/test_silver_workflow.py) thêm **58 cases**: raw/NFC, numeric substring/sign/unit/Unicode guards, fuzzy minimum/margin và biên float, literal multipart/newline, repeated/reused evidence, missing/error denominators, scope/hash/gold separation, immutable checksum/replay, exact-batch approvals, matched-size strata, synthetic freeze không mở real run và freeze không chuyển sang split khác.

Workflow test tạo ZIP/manifest/OCR/teacher fixtures trong thư mục tạm rồi chạy prepare → filter → dev audit → freeze → train selection qua CLI; không dùng ảnh/nhãn thật, API hoặc GPU.

ADR-P4-002 thêm **46 cases** trong [test_local_labels.py](../tests/unit/test_local_labels.py), [test_phase4_analysis.py](../tests/unit/test_phase4_analysis.py), [test_phase4_cli.py](../tests/unit/test_phase4_cli.py): no-gold requests/chunking, malformed/duplicate JSON/qids, raw/null/truncation, exact-plan permissions, holdout freeze, fixture identity, crash resume, completed zero-call replay kể cả failures, retry cap, corrupted cache/metadata/image/snapshot, concurrent lock, atomic publish; dev-only grid/replay/freeze, blind four-stratum sampling và review import, 12-run fairness/exposure/profile checks, missing denominator, paired group CI/seed std và <2-group null CI. CLI workflow bao phủ config/plan không import ML, grid → freeze → review → full comparison.

Full suite laptop **400 passed**, **59 schemas**; kết quả kiểm tra mới nhất và logs ở STATUS. Các checks chỉ xác nhận CPU code, không chứng nhận quality teacher/filter/student, GPU adapter, G3/G4, human audit thật, pipeline training hoặc deployment.

Sau merge PC: kiểm contracts/schema cả hai nhánh; chạy lại CPU suite; validate profile/G3 và gold/silver adapter; GPU train smoke/save/reload/resume; chỉ sau local label pilot và dev rule freeze mới chạy silver/core P1/P2. Không chạy test/OOD để chọn rule.

## Phase 5 offline đã hiện thực

- [test_verifier.py](../tests/unit/test_verifier.py): numeric substring/digit/sign/unit guards, raw và snap traces, field sai/unknown, geometry, repeated candidates/margin ngoài threshold, multipart/reuse, OCR limits/identity/NFC, checksum/replay, missing denominator, correction/harm/abstention và code-bound freeze.
- [test_cascade.py](../tests/unit/test_cascade.py): local default, từng external gate trước call/cache, exact request identity, một fallback rồi teacher verify, OCR/OOM không gọi ngoài, timeout/circuit, concurrent SQLite reservations, unknown/crash holds, immutable cap, overspend accounting và failure replay.
- [test_ood_review.py](../tests/unit/test_ood_review.py): reference-free packets, ceil ≥20%, blank templates chưa hợp lệ, rights/unseen/raw/pixel/near-duplicate boundaries, exact coverage, AI/fixture không thành human evidence thật, delayed same-person review và adjudication bind cả hai labels.
- [test_phase5_workflow.py](../tests/unit/test_phase5_workflow.py): synthetic archive → prepare/profile → verify/audit → dev_select freeze → dev_calibrate grid/selection → OOD exchange → final preregistration; monkeypatch chặn test CSV. Cost unknown/zero denominator, missing predictions, Pareto/paired groups, provenance/cache regime và immutable artifacts.

Các checks này không đo model accuracy, live API cost/deadline, workload latency, quality human gold hoặc G5. PC cần adapter exporter/backend thực, approved price/request grants, dev calibration/human error review và OOD nguồn mới. Counterfactual stage times không là p95 end-to-end. Counts/logs mới nhất ở [STATUS](STATUS.md), cùng [merge checklist](PHASE5_OFFLINE_HANDOFF.md).
