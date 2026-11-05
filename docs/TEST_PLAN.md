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

[test_metrics.py](../tests/unit/test_metrics.py) dùng expected values tính tay cho NFC, dấu/case/số/whitespace, multiset F1, ANLS tại ngưỡng, multi-reference/full multipart, missing/abstain/error denominator và report consistency. Đây là strict protocol. Phase 1 bổ sung [test_phase1.py](../tests/unit/test_phase1.py) cho containment/quarantine, cache identity/corruption/concurrent publication, grouped bootstrap, bounded oracle, CER và AI/human boundary. Upstream parity chạy riêng bằng [script](../scripts/check_metric_parity.py), 261 cases trên nguồn/wheel SHA-pinned. Kết quả thực và giới hạn human/OOD ở [Phase 1 report](PHASE1_RESULTS.md); G0 đã đạt.


## Phase2 đã hiện thực

[test_teacher.py](../tests/unit/test_teacher.py) có61 cases bảo vệ question-only/scoped grants, qid/strict output states, digits/newlines, đầy đủ cache identity, payload hash, budget concurrency/atomic shard reserve, retry/uncertain accounting, checksum/overrun, Batch unordered/expired/missing/idempotency và attempt mapping. CLI permission gate chạy trước credential/output; auth failure dừng campaign. Fixtures là synthetic và MockTransport, không chứng nhận provider/account hoặc chất lượng teacher.

OCR 100 dev, frozen 511-request plan, hash rerun và payload validation có evidence ở [PHASE2_RESULTS](PHASE2_RESULTS.md). Live pilot và bốn baselines đã hoàn tất; 511 cache replays không phát sinh calls/spend; metric/CI/role freeze/G2 report từ dữ liệu thật. Batch upload chưa chạy vì grant không bao gồm Batch; offline edge cases không chứng nhận live Batch.

[test_teacher_credentials.py](../tests/unit/test_teacher_credentials.py) có 8 cases về nạp `.env` tường minh, malformed/duplicate/missing values, không eval hoặc log secret; chỉ dùng fake keys. [test_phase2_finalization.py](../tests/unit/test_phase2_finalization.py) có 4 cases về chất lượng/cost tie-break, biên fallback 2pp và từ chối run chưa hoàn tất. Full suite tại mốc G2: Windows 289 passed/7 skipped, WSL 296 passed; logs/check hashes được dẫn trong STATUS. G2 đạt không chứng nhận training, cascade hoặc serving readiness.

## Phase 3 — student

[test_student.py](../tests/unit/test_student.py) kiểm mask prefix/image/EOS, từ chối truncation/template drift, causal CE và gradient tương đương full masked CE trên Torch, seed/order/partial batch, chặn gold trong inference/dev trong training, checksum/path checkpoint, RNG roundtrip, atomic progress và checkpoint selection/Numeric EM policy. Các fixture không là số đo accuracy hoặc training feasibility.

Actual processor preflight phải phủ toàn G10/dev đã chọn; smoke52 và resume50→52 chạy trên GPU thật, so adapters với tolerance đã khóa và greedy token IDs khi reload ở process mới. L2 cần toàn 3.053 QA/191 updates cho từng seed 17/42/2026, cả hai checkpoint dev được chấm, giữ cả ba seed và các lỗi trong báo cáo. Xem [workflow Phase 3](PHASE3_WORKFLOW.md); STATUS phân biệt phần đã đo và chưa hoàn tất.

Phase 3 hiện có 24 student unit cases; full suite trên code hash của [checks v2](../artifacts/phase3/checks_v2.json): Windows 311 passed/9 skipped, WSL 320 passed. WSL unit suite tắt CUDA để tách khỏi GPU campaign; smoke/resume/reload có [bằng chứng GPU riêng](../artifacts/phase3/resume_verification_v2.json). V2 buộc deterministic math attention và giữ đọc được protocol v1 lịch sử.

## Phase 3 continuation audit

`tests/unit/test_phase3_continuation.py`: fixture adoption giữ failed parent, chỉ tiếp tục missing evaluations; reject path escape, log/script/run checksum drift, cross-plan/missing seed, thay completed parent, partial/new run lỗi, execution lỗi, source/profile drift. Các fixtures không là evidence model. G3 audit còn phải replay raw predictions và kiểm đủ checkpoints trên artifacts thật.

Mốc G3 cuối ngày03/11/2026: continuation20 cases; full Windows331 passed/9 skipped, WSL340 passed; Ruff125 files,40 schemas và file policy239 candidates đạt. `checks_v3.json` bind source hashes. Audit thật `g3_report_v1.json` đạt9/9, đã replay đủ7 metrics từ raw predictions, kiểm6 checkpoint và3 training curves. CLI doctor vẫn model_not_configured; không nhận CI/Docker/serving đã đạt.

## Phase 4 offline đã hiện thực

[test_silver.py](../tests/unit/test_silver.py) và [test_silver_workflow.py](../tests/unit/test_silver_workflow.py) thêm **58 cases**: raw/NFC, numeric substring/sign/unit/Unicode guards, fuzzy minimum/margin và biên float, literal multipart/newline, repeated/reused evidence, missing/error denominators, scope/hash/gold separation, immutable checksum/replay, exact-batch approvals, matched-size strata, synthetic freeze không mở real run và freeze không chuyển sang split khác.

Workflow test tạo ZIP/manifest/OCR/teacher fixtures trong thư mục tạm rồi chạy prepare → filter → dev audit → freeze → train selection qua CLI; không dùng ảnh/nhãn thật, API hoặc GPU.

ADR-P4-002 thêm **46 cases** trong [test_local_labels.py](../tests/unit/test_local_labels.py), [test_phase4_analysis.py](../tests/unit/test_phase4_analysis.py), [test_phase4_cli.py](../tests/unit/test_phase4_cli.py): no-gold requests/chunking, malformed/duplicate JSON/qids, raw/null/truncation, exact-plan permissions, holdout freeze, fixture identity, crash resume, completed zero-call replay kể cả failures, retry cap, corrupted cache/metadata/image/snapshot, concurrent lock, atomic publish; dev-only grid/replay/freeze, blind four-stratum sampling và review import, 12-run fairness/exposure/profile checks, missing denominator, paired group CI/seed std và <2-group null CI. CLI workflow bao phủ config/plan không import ML, grid → freeze → review → full comparison.

Full suite laptop **400 passed**, **59 schemas**; kết quả kiểm tra mới nhất và logs ở STATUS. Các checks chỉ xác nhận CPU code, không chứng nhận quality teacher/filter/student, GPU adapter, G3/G4, human audit thật, pipeline training hoặc deployment.

Sau merge PC: kiểm contracts/schema cả hai nhánh; chạy lại CPU suite; validate profile/G3 và gold/silver adapter; GPU train smoke/save/reload/resume; chỉ sau local label pilot và dev rule freeze mới chạy silver/core P1/P2. Không chạy test/OOD để chọn rule.

## Phase4 integration trên main G3

[test_distillation.py](../tests/unit/test_distillation.py) kiểm cyclic sampler:1:1, cùnggoldorder giữaarm, khácseed, resume prefix/zero exposures; compact qid lossless và unknown IDs; cohort group/scope. Regression Transformers thực chạy CPU trên WSL kiểm model defaults không bật sampling.

[test_distillation_data.py](../tests/unit/test_distillation_data.py) chạy prepare/load 9 plans bằng G3 stubs tường minh trong temp fixtures; kiểm raw target, G10/dev isolation và từ chối đổi nhãn/group/source/approval dù đã hash lại file nội bộ. G4 contract cho phép H2 âm nhưng không pass khi thiếu human review. Không phải GPU training evidence.

[test_silver_reparse.py](../tests/unit/test_silver_reparse.py) kiểm strict-item parsing và cache provenance: sibling hợp lệ được giữ, envelope/qid mơ hồ bị chặn, không sửa null/digit/answer. [test_raw_teacher.py](../tests/unit/test_raw_teacher.py) kiểm raw text nguyên byte, sentinel, token cap và zero-call replay; cache mất entry phải lỗi. [test_label_teacher_selection.py](../tests/unit/test_label_teacher_selection.py) kiểm gate trước ranking, thứ tự tie-break, cohort đủ 666 QA và checksum reports trước execution. Shard OCR phải tách rời và hợp lại đúng full pool.

Integration checks v6: Windows 475 passed/10 skipped; WSL CPU 485 passed; 71 schemas. Các số này không chứng minh teacher pilot hoặc training Phase 4 đã đạt; xem STATUS và logs thực thi.

Smoke evidence audit kiểm preflight đủ population, run hash, sampler/exposure,
checkpoint bytes và proof reload/resume. Bốn cases mới sửa trajectory, checkpoint,
preflight coverage hoặc proof flag sau success đều phải bị từ chối.

[test_phase4_report.py](../tests/unit/test_phase4_report.py) kiểm báo cáo từ evidence đã bind: thiếu machine gate, checksum đổi, input ngoài gate và fixture đều bị từ chối; formatter không nâng gate incomplete thành human-complete và không ghi đè báo cáo cũ.

## Phase 4 final execution evidence — 05/11/2026

Final WSL code checks are bound at artifacts/phase4/checks_final_wsl_v1/checks.json: pytest 485 passed (one Starlette/httpx deprecation warning), Ruff pass, format pass (188 files), doctor pass with inference_not_ready, 71 schemas match, and repository policy pass (334 candidates). No new Windows run or GitHub CI was performed after this final check set.

Separate GPU/evaluation evidence includes all nine matched 191-update runs, predictions/evaluations at checkpoints 96 and 191 over 666 dev questions each, 12-result comparison/replay, completed human review, and Phase3 preservation replay. G4 passed 10/10. CPU tests alone do not establish these execution results; see [STATUS](STATUS.md), [Phase4 report](PHASE4_RESULTS.md), and [G4 report](../artifacts/phase4/g4_report_reviewed_v2.json).
