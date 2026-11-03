# Phase 5 — verifier, routing và OOD offline

03/11/2026 · [ADR-P5-001](DECISIONS.md#adr-p5-001--phase-5-cpu-offline-tách-khỏi-trainerapi-trên-pc-03112026) · [SOT §15.4](../SOURCE_OF_TRUTH.md#154-phạm-vi-phase-5-offline-trên-laptop--adr-p5-001) · [bàn giao PC](PHASE5_OFFLINE_HANDOFF.md).

Tooling này chạy CPU với **prediction/OCR artifacts có sẵn**. Không load model, chạy OCR, gọi API hoặc đọc key. Laptop chỉ kiểm synthetic fixtures, chưa có dev metrics/operating point/human OOD thật. G3/G4/G5 vẫn mở; Phase 2 benchmark grant không cấp quyền fallback cho dữ liệu mới. API/deploy thuộc Phase 6.

## Entry point và đầu vào

```powershell
.\.venv\Scripts\python.exe -m vidoclens.verify --help
```

Commands: `prepare`, `profile`, `verify`, `audit`, `freeze-verifier`, `routing-grid`, `routing-select`, `ood-packets`, `ood-curate`, `preregister`. Không có command inference giả hoặc live API. Output immutable, directory mới, manifest/checksum viết cuối; tạo thư mục cha trước. Giữ run incomplete để điều tra, dùng path version mới thay vì ghi đè. Writer dùng hard-link atomic (NTFS/ext4); cần kiểm filesystem trên PC.

| Contract | Producer / ý nghĩa |
|---|---|
| [PipelineBinding](../schemas/pipeline_binding.schema.json) | Exporter PC pin student bundle manifest, student evaluation protocol, frozen F1 config, fallback profile và G4 evidence; `fixture_only` bắt buộc |
| [VerificationPool](../schemas/verification_pool.schema.json) | `prepare`; exact frozen dev membership + question-only + image/group hashes |
| [VerifierProfile](../schemas/verifier_profile.schema.json) | `profile` tạo candidate; `freeze-verifier` bind report và source hash; không tự chứng nhận G4 |
| [VerificationBatch](../schemas/verification_batch.schema.json) | Student hoặc fallback exporter trên PC; pool/binding/source/cache regime + raw per-qid observations |
| [RoutingGridPlan](../schemas/routing_grid_plan.schema.json) | Owner khai báo grid/eligibility/targets **trước** calibration report; không cấp API permission |
| [RoutingPolicy](../schemas/routing_policy.schema.json) | Explicit selection/freeze với threshold, source/version/selection hashes, timeout và retry cap |

Hash trong `pool_sha256`, `verifier_profile_sha256`, `allowed_request_sha256` và `plan_sha256` là **canonical JSON** từ `vidoclens.filtering.io.digest(model)`, không SHA bytes của file JSON được indent. `archive/inventory`, selection evidence và manifest `files` dùng SHA bytes. Implementation hash chuẩn newline, pin source ảnh hưởng rule/router. PC thống nhất `PipelineBinding` với exporters: student bundle/protocol/G4 evidence là hash manifest thực; filter/fallback profile dùng canonical model digest và lưu các models gốc để đối chiếu. Không điền chuỗi hash mẫu thành evidence thật.

`PredictionObservation` gồm `prediction: {qid,status,answer_raw}`, cost bằng **integer micro-USD**, latency ms, số actual requests và image transmissions. Thiếu usage/time để null, không điền 0 cho dữ liệu chưa đo. Student không claim API cost/calls. Cache hit phải có 0 new calls/spend; cache miss so với cache miss. Fixtures dùng `fixture_only=true`, `cache_regime=synthetic`; tool từ chối trộn hai provenance. Đây là exchange format, chưa có adapter xuất từ trainer PC. Raw provider responses cần lưu riêng trên PC; các hash không thay raw audit trail.

## Dev verifier: chuẩn bị → so sánh → freeze

Ví dụ dưới dành cho PC **sau khi** khôi phục dữ liệu/artifacts và có G4; paths là quy ước minh họa, không khẳng định đã tồn tại trên laptop. Binding/student/OCR do pipeline thật xuất, không tạo prediction để qua workflow.

```powershell
$py = '.\.venv\Scripts\python.exe'
$archive = 'data/raw/ReceiptVQA_annotations.zip'
$frozen = 'data/splits/containment_v1'
$inventory = 'data/manifests/receiptvqa/images.jsonl'
$p5 = 'artifacts/phase5/run_v1'
New-Item -ItemType Directory -Force -Path $p5 | Out-Null
& $py -m vidoclens.verify prepare --partition dev_select --archive $archive --frozen $frozen --inventory $inventory --output "$p5/dev_pool.json"
# binding.json đã được exporter PC tạo và owner đối chiếu với G4/model/filter/profile thực.
& $py -m vidoclens.verify profile --pool "$p5/dev_pool.json" --binding "$p5/binding.json" --output "$p5/candidate.json"
& $py -m vidoclens.verify verify --pool "$p5/dev_pool.json" --student "$p5/dev_student.json" --ocr "$p5/dev_ocr.jsonl" --profile "$p5/candidate.json" --output "$p5/dev_verification"
& $py -m vidoclens.verify audit --bundle "$p5/dev_verification" --archive $archive --frozen $frozen --inventory $inventory --output "$p5/dev_audit.json"
```

`profile --config path/to/config.json` cho candidate khác theo [VerifierConfig](../schemas/verifier_config.schema.json). Defaults chưa tối ưu: distance .10, min 6 chars, margin .05, geometry gap .08, 4 spans/24 tokens, 4.096 document tokens/1.024 answer chars. Chạy từng candidate đã đăng ký vào run directory riêng trên **cùng** dev_select; không chọn rule bằng test/OOD/calibration. Owner đọc cả report, examples và tradeoff trước chọn.

Verifier nhận OCR JSONL ([OCRResult](../schemas/ocr_result.schema.json)), không tạo OCR. Numeric/hybrid phải exact với token boundary; không bỏ dấu/đơn vị/leading zero để chấp nhận substring. Question cue và nhãn gần nhất theo box chỉ là heuristic: field fail/unknown thì abstain; plain merchant header thiếu nhãn có thể không được hỗ trợ. P3-check giữ raw answer kể cả fuzzy-support; P3-snap chỉ sửa text không protected content, candidate unique/margin đủ, rồi recheck. Trace lưu raw/final riêng; không thêm normalized numeric value hoặc sửa raw benchmark. Bộ unit v1 có hạn, không là ontology cho mọi hóa đơn.

Audit recompute từ bundle + frozen source trước đọc dev gold. Metrics giữ đủ mẫu số kể cả missing/error/abstain; strict NFC EM/F1/ANLS, coverage/selective EM; correction precision = corrected/applied edits, harm per edit và harm trong câu vốn đúng bị edit. Correct-answer bị abstain đếm riêng. Group bootstrap paired theo duplicate group, mặc định 2.000 resamples/seed42, <2 groups thì CI null; không bao gồm training variance. Trả `calibrated_confidence=null`, không gọi rule score là correctness probability.

```powershell
& $py -m vidoclens.verify freeze-verifier --bundle "$p5/dev_verification" --archive $archive --frozen $frozen --inventory $inventory --selected-by '<owner>' --rationale '<kết quả dev và đánh đổi đã review>' --output "$p5/verifier_freeze"
```

Freeze chỉ chấp nhận candidate trên dev_select, tự recompute report; ghi `selection.json`, `profile.json`, manifest. Freeze của fixture vẫn là fixture. Owner phải giữ các candidate reports, data/model/filter/profile manifests thực. Code/config/binding đổi phải chọn/freeze lại; đừng sửa checksum để mở calibration.

## Dev_calibrate và routing operating point

```powershell
& $py -m vidoclens.verify prepare --partition dev_calibrate --profile "$p5/verifier_freeze/profile.json" --archive $archive --frozen $frozen --inventory $inventory --output "$p5/cal_pool.json"
# Sau đó exporter PC tạo cal_student.json, cal_teacher.json, cal_ocr.jsonl đúng pool và binding.
& $py -m vidoclens.verify verify --pool "$p5/cal_pool.json" --student "$p5/cal_student.json" --ocr "$p5/cal_ocr.jsonl" --profile "$p5/verifier_freeze/profile.json" --output "$p5/cal_verification"
& $py -m vidoclens.verify routing-grid --bundle "$p5/cal_verification" --teacher "$p5/cal_teacher.json" --plan "$p5/routing_plan.json" --archive $archive --frozen $frozen --inventory $inventory --output "$p5/routing_grid"
& $py -m vidoclens.verify routing-select --grid "$p5/routing_grid" --threshold 1 --selected-by '<owner>' --rationale '<tradeoff đã review, kể cả target chưa đạt>' --archive $archive --frozen $frozen --inventory $inventory --output "$p5/routing_freeze"
```

`--threshold 1` chỉ minh họa cú pháp. `routing_plan.json` theo schema, gồm canonical pool/profile hashes, fixture flag, sorted unique thresholds (defaults 0/.85/.90/.95/1), explicit `external_eligible_qids`, targets .70 local coverage/.40 cost ratio/.02 max absolute EM gap. Eligibility cần quyền thật trước khi thu teacher predictions; khai báo trong plan **không** cấp quyền gọi API. Calibration reader yêu cầu freeze trước đọc. Không sửa F1 hoặc student sau khi xem calibration; thay chúng cần campaign mới.

Teacher-all batch cần mọi qid kể cả lỗi, đúng frozen fallback profile (ADR-025), cùng protocol/cache regime với cascade counterfactual. Fallback chỉ chọn QA student không là runtime error, có OCR khỏe và được khai báo eligible; teacher vẫn qua P3-check. Report giữ raw/verified teacher-all, local coverage, final coverage/selective accuracy, costs cả failed observations, requests/image transmissions, unique images, paired EM và Pareto dominance. Không loại QA xấu để đạt target. Report không tự chọn point. `targets_met=false` vẫn có thể freeze với rationale và giới hạn product; không đổi target lặng lẽ.

Cost unknown → null; teacher-all cost 0 → ratio null, không công nhận target cost. Recorded latency là tổng stage đã ghi, chưa bao gồm queue/verifier và không đo workload thật. Chưa có live cost curve, Brier/ECE, probability calibrator hay calibration report thật. `routing-select` replay toàn bundle/report trước ghi freeze; một file sửa sau run bị chặn.

## Library cascade: integration boundary trên PC

`vidoclens.verify.runtime.cascade` nhận `VerifierInput`, frozen `VerifierProfile`, `RoutingPolicy`, `ExternalGate` và injected `FallbackBackend`, `BudgetCache`, `CircuitBreaker`. Mặc định `mode=local`, gates false. Local pass trả source student; fail trả abstain. Cascade chỉ có tối đa **một** fallback, **zero** transport retry; request không mang gold hoặc raw student answer. Không nối Phase 2 benchmark permission vào interface này.

PC cần adapter thật kiểm image bytes theo hash, profile/model/prompt/generation settings, source permission, giá hiện hành/max usage, raw response audit, strict output parsing và I/O timeout. Mọi gate + exact canonical request hash kiểm trước cache; binding/fixture/code mismatch bị từ chối. Dùng một circuit breaker chung cho cùng provider trong tiến trình, không tạo lại mỗi request. SQLite cap immutable theo campaign riêng, không dùng đồng thời hai ledger cho cùng một budget tổng. Không quảng bá class này là multi-process production service.

Budget reserve transaction chống race; inflight/unknown requests không gọi lại, unknown cost giữ đủ reservation. Cache failure replay failure, không retry để cải thiện metric. Cost thực vượt reserve ghi đủ actual spend và abstain; không clamp/giấu overrun. Upper-bound giá sai có thể vượt cap: cần adapter/billing test thật trước dùng tiền. Timeout dùng monotonic remaining budget, kiểm sau call; Python library không kill một backend đang block. Có CPU fixtures cho timeout/circuit/budget/race, chưa chứng minh deadline provider thật. Không có command bật API, HTTP integration hay credential access trong module này.

## Human OOD và preregistration

Theo [protocol OOD](OOD_ANNOTATION_PROTOCOL.md), chuẩn bị ảnh mới/quyền/near-dedup evidence và [OODReviewPlan](../schemas/ood_review_plan.schema.json). Plan pin inventory được bảo vệ, hash nguồn/ảnh/pixels, domain/shift axes, câu hỏi; `previously_model_reviewed=false`. Không đưa 3 ảnh AI seed đã thấy vào unseen final set hoặc đổi reviewer AI thành người. Hash overlap check chưa thay near-duplicate review/all-source inventory audit.

```powershell
& $py -m vidoclens.verify ood-packets --plan "$p5/ood_plan.json" --inventory $inventory --output "$p5/ood_packets"
# Con người mở ảnh local theo qid/document/hash; điền templates bằng review blind thật.
& $py -m vidoclens.verify ood-curate --plan "$p5/ood_plan.json" --inventory $inventory --primary "$p5/human_primary.json" --second "$p5/human_second.json" --resolutions "$p5/adjudications.json" --output "$p5/ood_curated"
& $py -m vidoclens.verify preregister --routing-freeze "$p5/routing_freeze" --ood-curation "$p5/ood_curated" --systems "$p5/final_systems.json" --frozen $frozen --inventory $inventory --output "$p5/final_suite_plan.json"
```

Packets không gold/OCR/prediction, không nhúng ảnh hoặc host UI. Template cố ý chưa hợp lệ: reviewer/time/answerability/evidence/attestation cần người điền. Second review chọn seed42 `ceil(.20 × N)` QA; identity/coverage exact, timestamp có timezone. Cùng reviewer cần ≥24h và nhãn cũ bị che; báo hạn chế, không gọi inter-annotator agreement. Disagreement trong answer/evidence cần [OODResolution](../schemas/ood_resolution.schema.json) cho đúng hai labels; bỏ `--resolutions` nếu không có disagreement, không tạo adjudication giả. Unanswerable có answers/boxes rỗng. Không có human work thật được thực hiện bởi các unit fixtures.

`final_systems.json` map đủ 13 keys: `L2/17`, `L2/42`, `L2/2026`, tương tự `P1-full`, `P1-size`, `P2`, và `teacher-all`, values là hashes model bundles/profile thật. Ít nhất một P2 phải khớp student đã freeze; teacher-all khớp fallback. Core 12 runs giữ seed variance; P3/P4 dùng **P2 bundle đã chọn**, không ngầm áp một calibration cho mọi bundle.

Preregister kiểm freeze/selection/code hashes, replay OOD reconciliation và exact frozen inventory; lưu test image IDs từ split manifest, không đọc test CSV/gold. Nó không chạy final evaluation. Output luôn `execution_enabled=false`, `g5_certified=false`. Owner còn phải kiểm dataset size/diversity/rights, G4/G5 evidence và release candidate trước Phase 6. SHA/attestation không xác thực người hoặc chứng nhận chất lượng model.

## Lưu trữ và kiểm tra

Không commit OCR, raw predictions/answers, images, grants, cache/ledger, weights hoặc reports; giữ trong data/artifacts/cache ignored và sao lưu riêng trên PC. Không log secret/private provider exception. Sau merge chạy các lệnh trong [handoff](PHASE5_OFFLINE_HANDOFF.md); kết quả thực gần nhất ở [STATUS](STATUS.md).
