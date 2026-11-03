# Nhật ký quyết định

Ngày khởi tạo: 02/11/2026. [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) là quy định hiện hành; ADR ghi lý do và lịch sử. Khi có xung đột, sửa cả hai trong cùng thay đổi trước khi tiếp tục phần phụ thuộc.

| ID | Trạng thái | Quyết định | Lý do / hệ quả |
|---|---|---|---|
| ADR-001 | Chấp nhận | Một tài liệu chuẩn: `SOURCE_OF_TRUTH.md`; overview được bảo toàn làm lịch sử | Không duy trì hai bản thiết kế có thẩm quyền ngang nhau |
| ADR-002 | Chấp nhận | Modular monolith Python; FastAPI phục vụ API, Gradio phục vụ demo | Phù hợp một người triển khai và một GPU; giữ module boundary để thay backend |
| ADR-003 | Chấp nhận | Tách pipeline offline khỏi request online | Huấn luyện, OCR corpus và sinh nhãn không chạy trong lifecycle request |
| ADR-004 | Chấp nhận | JSONL cho record trao đổi, Parquet cho phân tích lớn, SQLite cho ledger/cache metadata | Truy vết đủ dùng; chưa cần hệ thống phân tán hay vector database |
| ADR-005 | Chấp nhận | OCR support là bằng chứng phụ trợ, không phải chứng nhận đáp án đúng | Chuỗi có trên ảnh vẫn có thể thuộc sai trường; OCR cũng có lỗi |
| ADR-006 | Chấp nhận | Mặc định `local`, external off; yêu cầu cho phép gửi dữ liệu tường minh | Cascade không được tự gửi ảnh ra ngoài khi local yếu hoặc gặp lỗi |
| ADR-007 | Chấp nhận | Không huấn luyện từ output dịch vụ khi quyền sử dụng chưa rõ | Tách quyền inference và quyền dùng output cho student; ý kiến người hướng dẫn không thay thế điều khoản áp dụng |
| ADR-008 | Chấp nhận | Test/OOD chỉ dùng sau khi đóng băng cấu hình | Tránh lựa chọn prompt, threshold hoặc checkpoint từ kết quả test |
| ADR-009 | Chấp nhận | Release gồm base model + adapter + processor + verifier + schema + config tương thích | Rollback cả bundle, tránh ghép adapter với sai base revision |
| ADR-010 | Chờ đo | Chọn student/OCR chính | Tên candidate trong config không chứng minh tương thích, chất lượng hay vừa VRAM |
| ADR-011 | Đã chốt phạm vi Phase 2 — ADR-025 | Snapshot benchmark/fallback, price cards và cap 20 USD | Live dev evidence/role freeze ngày 03/11/2026; không mở quyền label export hoặc serving |
| ADR-012 | Chấp nhận — 02/11/2026 | Adapter ReceiptVQA giữ raw CSV, dùng qid có namespace dataset/version + image_id/question_id; chưa tự chuyển newline thành `¡sep¿` | Audit ZIP hash `226f7dcc6421115da254b2809dc9ebfd138be0c2f175a9c1c12f7a46ae6127ea`: question_id lặp giữa ảnh, cột index reset theo split, train có 879 answer chứa newline và 0 literal separator; SOT §11.1 đã bổ sung, scorer parity vẫn mở |
| ADR-013 | Chấp nhận — 02/11/2026 | Định vị đóng góp là thực nghiệm có kiểm soát; không nhận novelty riêng cho validated distillation/cascade | Matrix 12 công trình trong LITERATURE, đặc biệt DocVAL; SOT §4 cập nhật. Hidden gold vẫn không vào teacher/filter; không đổi RQ hoặc bắt buộc train CoT |
| ADR-014 | Chấp nhận phương án, candidate chưa kiểm chứng — 02/11/2026 | Nhánh label teacher local Qwen3-VL-4B-Instruct khi quyền output API chưa rõ; load luân phiên với student | Model card/API khai báo Apache-2.0; access register ghi observed revision và gate. SOT §10.4 cập nhật. Chưa tải weights, chưa cấp quyền ảnh, chưa bật API; nếu pilot fail giữ gold-only và RQ2 chưa hoàn tất |
| ADR-015 | Chấp nhận — 02/11/2026 | Loader annotations dùng question contract không trường gold, manifest theo receipt/group gắn archive hash; gold training và gold evaluator tách API | SOT §7.4; source labels không bị serialize sang teacher/silver. Manifest phủ toàn selected split; test chưa mở trước frozen runner. Chưa tạo split thực hoặc coi receipt-only grouping là image dedup |
| ADR-016 | Chấp nhận — 02/11/2026 | Triển khai `strict_nfc_v1` với multiset F1, ANLS ngưỡng strict 0,5, max full references; missing/abstain/error giữ denominator | SOT §14.1; scorer nguồn tại commit cố định có set F1/mean references nên khác protocol. Official parity vẫn mở; giữ metric dự án và metric nguồn tách tên, không đổi primary EM |
| ADR-017 | Chấp nhận cho pilot kỹ thuật — 02/11/2026 | Dùng rotated_images.zip chính thức, mapping aliases đuôi file tường minh; chọn train pilot theo exact-byte groups tránh dev/test | Chủ dự án cho phép tải/cài. Hash/source và 7 aliases đã lưu; 15 nhóm trùng xuyên split cần quarantine 19 ảnh train theo SOT §7.3. Chưa nhận official preprocessing parity hoặc coi byte dedup thay near-dedup; SOT §7.2 cập nhật |
| ADR-018 | Chấp nhận profile feasibility — 02/11/2026 | Khóa stack inference Linux Python 3.11.14: Torch 2.8.0+cu126/vision 0.23.0+cu126, Transformers 4.57.1, PEFT 0.17.1, Accelerate 1.10.1, bitsandbytes 0.48.1; OCR CPU riêng Paddle/PaddleOCR/PaddleX 3.2.0 | Student NF4/BF16 và OCR v5 Việt chạy 20 ảnh train; hai venv mới từ hash locks khớp packages và 20/20 outputs. SOT §6/§22 và runbook cập nhật. G0 đạt; 7 student outputs chạm cap, OCR có lỗi dấu/tách dòng. Chưa chốt chất lượng OCR/student (ADR-010), chưa QLoRA train hoặc deploy; API readiness vẫn false |
| ADR-019 | Chấp nhận bước đầu Phase 1 — 02/11/2026 | Ingestion versioned raw/EXIF-RGB pixel hashes; nối exact byte/pixel graph, pHash full/crop chỉ đưa vào review; split đầu ra là `SplitDraft` không cấp quyền train | Không được freeze khi near-dedup chưa review. Quarantine xuyên official split, pilot groups không vào audit; nested gold IDs chỉ là dự kiến. Không materialize/re-encode toàn corpus hoặc giả có derivative file. SOT §7.3/§7.4 cập nhật; pHash không chứng minh hết leakage hoặc thay matching OCR/feature đầy đủ |

## ADR-020 — Containment bảo thủ và evaluator Phase 1

Chấp nhận triển khai ngày 02/11/2026 theo yêu cầu hoàn thiện Phase 1. Nối candidate chưa chắc vào leakage component, không nhận là duplicate đã chứng minh; exact graph và pending queue bất biến. Quarantine component xuyên official splits trước train. Đổi lại có thể mất nhiều dữ liệu do cùng template; báo riêng counts và giữ version split. Bổ sung feature rotation/crop với thresholds định trước trong SOT §7.4. Không dùng test QA để chọn thresholds. `conservative_candidate_graph` là grouping status mới; final plan không giả review con người. OCR dùng G10 train_fit sau freeze, không audit/calibration/test. User yêu cầu assistant tự review; các annotations này ghi AI-reviewed, không đóng yêu cầu human gold/OOD bằng nhãn AI. Scorer tương thích có tên commit + anls 0.0.2, giữ strict riêng và không tuyên bố tái lập dependency không pin của bài gốc.

## ADR-021 — Hoàn tất Phase 1 bằng AI, không nhận là human gold

Chấp nhận ngày 02/11/2026 theo chỉ dẫn tường minh mới: “sử dụng AI để hoàn thành toàn bộ phase 1”. Thay blocker human tại Phase 1 bằng AI review/reference có provenance và model local reference-free kiểm thêm; human flags giữ false. SOT §7.5 đặt tối thiểu 3 ảnh/30 dòng OCR review, 3 ảnh OOD có quyền/18 QA và 20% second AI review trước đóng gate. OOD seed phải ngoài ReceiptVQA, dedup với toàn corpus, giữ riêng khỏi train/tuning, có raw answers/bbox/answerability. Không biến sample/synthetic receipt thành giao dịch thật, không đánh giá/tune model trên OOD. Nguồn Wikimedia Commons có điều kiện giấy phép lưu theo từng file; tổng tải nhỏ, không API trả phí/weights mới. Human gold/full OOD validation ở phase sau không được tự nhận đã hoàn thành. Quyết định này thay riêng yêu cầu chờ human để đóng Phase 1 trong ADR-020, không thay mọi ràng buộc nghiên cứu/release của SOT.

**Bằng chứng thực thi ADR-021:** [G1 report](../artifacts/phase1/g1_ai_gate_v2.json) đạt; [Commons seed](data/COMMONS_OOD_SEED_V1.md) có 3 ảnh/24 QA và zero overlap candidates theo protocol; 38 dòng OCR và 24 QA có local second pass + 62 adjudications. Linux 205 tests/Windows 198 + 7 skips, 27 schemas. SOT v1.7 công nhận hoàn tất G1 theo phạm vi AI, giữ human/final OOD flags false và mọi artifact lịch sử bất biến.

## ADR-022 — Quản lý trạng thái và GitHub thủ công

Chấp nhận ngày 02/11/2026 theo yêu cầu nâng cấp repo và chỉ dẫn chủ dự án tự push. Giữ STATUS ngắn, có bảng 8 phase, queue task, blocker/owner/điều kiện gỡ, validation và bàn giao; lưu lịch sử cũ riêng, không đổi scientific evidence. CONTRIBUTING quy định task lifecycle, branch `codex/`, Conventional Commits, staged review và push thủ công; CHANGELOG theo phiên bản, Issue/PR templates phục vụ review. Local done/commit/push/CI/release là các trạng thái khác nhau. Bổ sung schema `--check` không ghi file và file policy names/sizes + YAML validation; chúng không là secret scan hoặc bằng chứng model/deploy. CI read-only không publish. SOT v1.8 §19.3 cập nhật cùng quyết định. Không đổi phase gates, môi trường ML, driver hoặc quyền dataset/teacher.

Bằng chứng ADR-022: Linux **223 passed**, Windows **216 passed/7 skipped**, Ruff lint/format đạt, 27 schemas match; 32 Markdown được kiểm UTF-8/liên kết local. File policy/YAML check đạt; index chưa có staged file nên chưa chứng nhận commit sẵn sàng. GitHub CI chưa xác minh chạy. Không có stage/commit/push hoặc thay remote trong lượt nâng cấp.

## ADR-023 — Teacher có gate quyền, cache và ledger trước API pilot (02/11/2026)

- **Trạng thái:** chấp nhận triển khai local theo yêu cầu Phase 2; model/permission/role vẫn là candidate hoặc pending.
- **Vấn đề:** không để retry/concurrency/cache gây vượt budget, không đưa gold vào request hoặc dùng evaluation output để huấn luyện.
- **Quyết định:** Pydantic contracts, Responses REST qua httpx optional, SQLite transactions lưu identity/raw/parsed/checksum và từng attempt; cap integer micro-USD, unknown charge giữ reservation. Reserve full documented model input limit ở tier đắt nhất + max output. Không lấy token estimate chưa kiểm chứng làm safety bound. Retry bounded, Retry-After dài thì dừng; crash không auto-release. Batch reserve toàn shard trước upload, custom_id theo request hash, đối soát output/error terminal trước retry phần chưa chạy.
- **Dữ liệu/thí nghiệm:** 50 G10 train integration đã exposed ở Phase 1; 100 component dev_select seed42, question-only. Cùng tập cho A1/A2/A3 mạnh và A5 model rẻ với prompt A3, không mở test/OOD. Prompt v2 giữ newline/raw text; không ép literal separator từ paper vào archive CSV.
- **Candidate:** GPT-5.4-2026-03-05 và GPT-5.4-mini-2026-03-17, reasoning none, high detail, output cap4096. GPT-4.1 đã marked deprecated trong tài liệu hiện tại nên không chọn cho pilot mới. Chưa chứng nhận account access, chất lượng hoặc vai trò thắng cuộc; local4B ADR-014 vẫn pending cho training labels.
- **Nguồn:** [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Batch](https://developers.openai.com/api/docs/guides/batch), [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [data controls](https://developers.openai.com/api/docs/guides/your-data), kiểm 02/11/2026; price cards có SHA256 snapshot tài liệu local.
- **Tác động:** reservations lớn hơn chi phí kỳ vọng; sync tuần tự settle theo usage thật. Template Git vẫn deny/cap0. Trong lượt này chủ dự án đã duyệt cap20 USD và xác nhận quyền dữ liệu/terms/retention cho benchmark đúng150 ảnh/511 request keys, lưu grant local riêng; training/batch permissions vẫn false. Đây là xác nhận của chủ dự án, không là assistant kiểm hợp đồng tài khoản. Lần thử đầu chưa có key nên0 API calls/0 spend. Unit fixtures là synthetic, không là inference evidence; G2 cần pilot/baseline/role freeze thật.
- **Thay đổi:** SOT §10, contracts/schemas, configs/prompts, teacher/evaluator/CLI, protocol/status. Không thay ADR-014/021/022 hoặc scientific gates.
- **Xem xét lại:** model/snapshot/giá/terms đổi, cần provider khác, workload vượt model limit hoặc role chưa đạt chất lượng.

## ADR-024 — Credential file và quy tắc chọn role Phase2 (02/11/2026)

- **Trạng thái:** chấp nhận thực thi theo yêu cầu tiếp tục Phase2; cap20 và scope511 keys giữ nguyên.
- **Credential:** chủ dự án tạo `.env` và yêu cầu dùng key trong đó. CLI thêm `--env-file .env`, runtime chỉ đọc OPENAI_API_KEY sau permission gates; không eval/interpolate, không đưa giá trị vào log/artifacts hoặc đổi biến môi trường khác. Environment vẫn là default nếu không chỉ định file; external serving flag không tự thay bằng quyền teacher. [.env.example](../.env.example) cập nhật hướng dẫn, không sửa `.env` của chủ dự án.
- **Selection freeze trước dev predictions/metrics:** [selection_v1.json](../configs/teacher/selection_v1.json) dùng strict_nfc_em, hòa thì ANLS, rồi actual cost/QA, rồi ID. Benchmark so A1/A2/A3/A5. Fallback chọn A5 chỉ nếu không giảm quá2pp EM so best image-capable strong A2/A3 và rẻ hơn; ngược lại dùng strong đó. Đây là operating candidate tạm, không chứng nhận cascade/gần-teacher trên test.
- **Thống kê:** bootstrap2000 lần seed42 theo frozen component; paired A3−A2 và A5−A3; giữ error/null trong denominator, báo hai metric protocols riêng. Label role chuyển nhánh local4B có điều kiện theo ADR-014, API training export vẫnfalse; phải pilot license/VRAM/quality trướcPhase4.
- **Vận hành:** các experiment độc lập có thể chạy đồng thời tối đa2 process, mỗi process1 request; cùng transactional ledger/cap20. Run timestamps và báo cáo ghi overlap; không coi thời gian này là deployment latency. Không mở rộng ảnh/model/prompt, không resubmit cache success.
- **Không đổi scientific gates:** G2 vẫn yêu cầu pilot/baselines/cost/replay/role evidence thật. Không chọn trên test/OOD/dev_calibrate.

## ADR-025 — Đóng G2 và freeze teacher từ dev thực tế (03/11/2026)

- **Trạng thái:** chấp nhận; G2 đạt theo SOT v1.10, không sửa gate. [Báo cáo](PHASE2_RESULTS.md), [report local](../artifacts/phase2/final_v1/report.json), [role freeze](../artifacts/phase2/final_v1/role_freeze.json).
- **Bằng chứng:** pilot 50 ảnh/344 QA/59 groups; A1/A2/A3/A5 cùng 100 dev components/666 QA/113 groups mỗi arm. Tổng 511 live attempts, không retry; replay 511 cache hits không thêm calls/spend. Chi phí usage × price cards là 6,080008 USD trong cap 20 USD; reserved/uncertain đều 0, chưa đối soát hóa đơn account.
- **Quyết định:** theo policy ADR-024 khóa trước dev output, benchmark và fallback đều là A3: `gpt-5.4-2026-03-05`, image+OCR, `teacher_vqa_v2`, high detail, reasoning none, output cap 4096, store false. Strict EM 76,28%; A2 73,72%; A5 70,27%. A3−A2 = +2,55pp, paired component-bootstrap 95% CI [+0,43; +4,75]pp. Chỉ diễn giải trên dev subset; không suy final-test superiority.
- **Lựa chọn chi phí:** A5 tốn 0,520879 USD so A3 1,750404 USD trên cùng 666 QA, nhưng giảm 6,01pp EM, vượt ngưỡng 2pp. Do đó chưa chọn cheap làm fallback. Một A5 schema error giữ đủ 6 QA vào error denominator; raw/usage được giữ và không gọi lại để cải thiện metric.
- **Label/serving:** chọn chiến lược local open-weight theo ADR-014; 4B còn gate license/VRAM/quality trước Phase 4. `training_export_allowed=false`, fallback serving disabled, không có quyền Batch upload hoặc external cho dữ liệu mới. Kết quả Phase 2 không chứng nhận cascade/training/deployment.
- **Thay đổi:** cấu hình role, SOT §10/22, STATUS/results/workflow/access register/budget/CHANGELOG khớp report SHA `7c0462bce5ffc7b888b4293376b06573c1e1926f72f080438217ef2116347e21`. Snapshot plan/prompt/policy và artifacts cũ giữ nguyên; không mở test/OOD/dev_calibrate/audit để chọn teacher.
- **Tiếp theo:** Phase 3 student training smoke/save/reload/resume và gold-only baselines. Model/giá/prompt/dữ liệu thay đổi phải lập campaign/ADR mới theo ảnh hưởng, không sửa lịch sử hoặc tự tái dùng grant.

## ADR-P4-001 — Chuẩn bị Phase 4 CPU song song với Phase 3 trên PC (03/11/2026)

- **Trạng thái:** chấp nhận theo yêu cầu chủ dự án. Nhánh tên tường minh `phase4-offline`, base `d13360e`; ID ADR riêng để tránh trùng số với thay đổi chưa thấy trên PC.
- **Bối cảnh:** Phase 3 đang dở trên PC và chưa push; laptop chỉ có mốc Phase 2. Không suy đoán trainer/collator/checkpoint interface hoặc đánh dấu G3 đạt.
- **Quyết định:** thêm silver contracts, frozen question-only pool builder, local-result import format, F0/F1 và immutable replay bundle; privileged audit evaluator; nine matched experiment selections. CLI riêng dưới `vidoclens.filtering`, không sửa student/core CLI/ML locks. SOT v1.11 §11.4 ghi protocol và các defaults còn uncalibrated.
- **Boundary:** local open-weight result exchange không là model runner. API evaluation caches/export grants giữ nguyên. G10 gold chỉ qua loader riêng của Phase 3; filter không nhận gold. Audit holdout chỉ sau dev freeze; test/OOD/calibration không mở. Fixture provenance truyền qua freeze và selections, không tự trở thành run thật.
- **Protocol:** NFC/whitespace evidence normalization, raw target bất biến, numeric/hybrid exact, bounded contiguous spans, text minimum-length/margin, multipart literal chỉ khi khai báo. `semantic_check=unknown` do semantic checker chưa có. Không nhận OCR agreement là semantic correctness.
- **So sánh:** P1-size deterministic hash-rank trong strata question heuristic/answer type để match F1; cùng G10/seeds/profile/update budget, ratio 1:1 và equal weights. Phase 3 consumer phải xác minh profile/G3, thực hiện sampler/resume và ghi exposure; opaque profile hash không là training certification.
- **Đánh đổi:** giảm conflict và có tests CPU trước khi dùng GPU; vẫn cần review interface/diff PC và real-data calibration. Exact matching bảo thủ có thể giảm recall; chưa chọn threshold từ dữ liệu thật. Contracts/additional schemas có thể cần adapter sau merge nhưng không sửa lịch sử runs.
- **Gates giữ nguyên:** local teacher pilot/quyền, G3, silver thật, holdout audit/human error review và core training ba seed trước G4. Không API call, không tải weights/dataset, không public hosting. Chủ dự án tự commit/push; không thêm author/co-author.
- **Bàn giao:** [workflow](PHASE4_OFFLINE_WORKFLOW.md), [PC integration](PHASE4_OFFLINE_HANDOFF.md), [STATUS](STATUS.md). Kết quả tests không là metric nghiên cứu.

## ADR-P4-002 — Hoàn thiện tooling Phase 4 khả thi trên laptop (03/11/2026)

- **Trạng thái:** chấp nhận theo yêu cầu tiếp tục triển khai của chủ dự án; bổ sung ADR-P4-001, SOT v1.12 §11.5. Base bổ sung là commit owner đã push `3ae2c4f` trên `phase4-offline`.
- **Khoảng thiếu:** package đầu chỉ nhận local labels, chạy từng filter config, liệt kê review qids và xuất selections. Các phần điều phối/review/comparison vẫn làm được bằng CPU dù chưa có PC trainer/weights.
- **Quyết định:** thêm local teacher plan/parser/SQLite resume và lazy Qwen adapter; dev threshold grid + selection record; blind human audit packet/import; trainer-independent results + fairness/3-seed/paired-bootstrap reports. Tách module mới và CLI riêng, không đổi student, Phase 2 providers, locks, data/splits hoặc root CLI.
- **Local generation:** candidate image-only, prompt không gold, request split deterministic; snapshot/config/plan hashes và actual image hashes. Data/model/generation grant theo plan, pilot dev-only, silver cần quality pilot; audit_holdout sau freeze. Model chỉ đọc local snapshot, không tải; GPU adapter dùng pattern của Phase 0 và [Qwen docs](https://huggingface.co/docs/transformers/model_doc/qwen3_vl) kiểm ngày 03/11/2026, nhưng **chưa smoke host thật**. Không suy license, nguồn revision hoặc quality từ manifest tự khai báo.
- **Cache/artifacts:** SQLite transaction lưu raw cả lỗi/retries; bound inputs/environment, checksum/reparse, không replay lỗi thành answered. Complete runs immutable, kể cả failures; crash có thể recompute một request chưa commit, không hứa exactly-once. Single-writer lock cần owner kiểm process trước khi gỡ lock stale. Atomic exclusive file publish trên NTFS/ext4, không overwrite evidence.
- **Evaluation:** grid giữ mọi candidate; owner chọn bằng tradeoff và rationale, không tự tối ưu retention. Reviewer không thấy gold/outcome trong packet; sampling key giữ riêng. Strict judgments + image attestation, không nâng AI/fixtures thành human evidence hoặc tự sửa gold. Comparison chỉ dev_select, 12 run/9 selections, actual exposure logs kể cả zero; CI theo component, seed variance tách riêng. Manifest checks không chứng minh GPU training đúng.
- **Bằng chứng:** CPU fixtures và CLI integration ghi tại STATUS; không gọi model/API, không có nhãn/quality metrics thật hoặc G4 mới. F2/F3/correction là extension, semantic gate không bị thêm vào F1.
- **Bàn giao:** [công cụ mới](PHASE4_LOCAL_TOOLS.md), [hợp nhất PC](PHASE4_OFFLINE_HANDOFF.md). Owner tự commit/push; CI cũ không chứng nhận bổ sung chưa commit.

## ADR-P5-001 — Phase 5 CPU offline tách khỏi trainer/API trên PC (03/11/2026)

- **Trạng thái:** chấp nhận theo yêu cầu triển khai của chủ dự án; SOT v1.13 §15.4. Branch `phase5-offline` tạo từ `phase4-offline` tại `2fa55cd`; không stage/commit/push hoặc thêm author/co-author.
- **Bối cảnh:** không có Phase 3 source/checkpoint/G3/G4, dataset/OCR payload hoặc fallback grant mới trên laptop. Có thể chuẩn bị verifier, orchestration, evaluators và exchange contracts bằng CPU fixtures; chưa thể chạy nghiên cứu/calibration thật.
- **Quyết định:** P3-check/P3-snap với numeric/occurrence/field rules; code-bound profiles và immutable replay; rule-based routing grid/selection trên dev_calibrate sau freeze; injected fallback + riêng SQLite budget/cache + circuit/timeout; blind human OOD packets/reconciliation; final-suite preregistration không mở gold. CLI riêng `vidoclens.verify`, 22 root schemas mới.
- **Tách scope:** đọc lại helper matching/io/metrics/frozen loaders của Phase 4/1 nhưng không sửa chúng, F0/F1, trainer, Phase 2 provider/grant/ledger, API/root CLI hoặc ML locks. New verification pool mở calibration đúng phase, không nới `SilverPool` hay teacher request cũ. Raw outputs giữ riêng; rule confidence không là probability.
- **Tradeoff:** heuristic label/geometry cố ý abstain khi field unknown; chỉ text không protected content được snap, có thể giảm coverage. Không gọi support là semantic truth. Ngưỡng default chưa calibrated; so P3check/snap và đo cả harm/abstention trước freeze. Grid counterfactual không đo live queue/budget contention, latency hay provider reliability.
- **Runtime:** interface nhận backend do PC triển khai; không code HTTP/provider mới hoặc key access trong lượt này. Exact-request permission và health vẫn kiểm khi replay. Một transport attempt, không retry; unknown spend được giữ. Timeout cần backend hợp tác; cap cần price upper bound được kiểm thật. Overrun ghi chi phí thật và trả failure, không che billing bằng clamp. Không dùng ledger này làm nguồn budget chung với Phase 2.
- **OOD:** unseen sources và ≥20% QA human review; cùng người ≥24h delayed blind theo protocol v1, ghi hạn chế. Rights/near-duplicate/human fields là attestation, không authentication. Chỉ check raw/pixel overlap với inventory supplied; không tự đóng full OOD/G5 từ form hợp lệ hoặc đổi seed AI thành gold.
- **Final freeze:** cấu hình + comparison registrations có đủ hashes, fixture flag, `execution_enabled=false`/`g5_certified=false`. Không mở test CSV, không sửa evaluation lịch sử. Phase 6 vẫn cần final inference/evaluator/deployment thật.
- **Bằng chứng và điều kiện xem lại:** CPU tests/checks và limitations tại [STATUS](STATUS.md); PC phải review merge/interface, hoàn tất G3/G4, đo dev thật, bổ sung backend/price/permission/timeout integration và human OOD. Rule/code thay đổi sau freeze làm profile/policy cũ bị từ chối; version run mới và đánh giá lại trên split cho phép.
- **Bàn giao:** [workflow](PHASE5_OFFLINE_WORKFLOW.md), [merge checklist](PHASE5_OFFLINE_HANDOFF.md). Không tuyên bố merge sạch khi chưa đọc source PC, không dùng CI Phase 4 làm CI Phase 5.

## Mẫu ADR tiếp theo

```text
ID / ngày / người quyết định:
Trạng thái: đề xuất | chấp nhận | thay thế | bác bỏ
Vấn đề cần giải quyết:
Các lựa chọn đã xét:
Quyết định:
Bằng chứng (run ID / tài liệu / URL + ngày truy cập):
Tác động dữ liệu, chi phí, chất lượng, bảo mật:
Phần SOT / config / schema bị thay đổi:
Điều kiện cần xem xét lại:
Thay thế ADR nào:
```

Những thay đổi bắt buộc có ADR: đổi bài toán chính, nguồn gold, split, preprocessing metric, teacher/student, policy dữ liệu ra ngoài, tiêu chí nhận release hoặc cắt một đầu ra cam kết.
