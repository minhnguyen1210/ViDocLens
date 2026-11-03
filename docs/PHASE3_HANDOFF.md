# Phase 3 — bàn giao khi tạm dừng

**Phase3/G3 đã hoàn tất local sau khi tiếp tục ngày03/11/2026. Đây là handoff lịch sử pause; không còn việc Phase3 dang dở. Xem STATUS và PHASE3_RESULTS.** Phần dưới giữ điểm dừng và kế hoạch lúc bàn giao, không phải trạng thái chạy hiện tại. Đọc `AGENTS.md`, [SOT](../SOURCE_OF_TRUTH.md), [STATUS](STATUS.md), [workflow](PHASE3_WORKFLOW.md) trước khi tiếp tục. Chủ dự án tự stage/commit/push; assistant không thực hiện.

## Đã hoàn thành và lưu trên máy

- Nhánh `codex/phase3-student-training`, base `d13360e`; code/docs còn local, chưa stage/commit/push. Không thay PROJECT_OVERVIEW, không cài thêm dependency/driver hoặc tải model/data trong Phase 3.
- Contract Pydantic + 3 schemas; chuẩn bị G10 và dev, bảo vệ gold, collator mask chỉ answer/EOS, QLoRA, checkpoint optimizer/scheduler/RNG, resume training, predictor không gold, evaluator EM/F1/ANLS/numeric/bootstrap, campaign và final audit đã triển khai trong `src/vidoclens/student`, `src/vidoclens/eval/{student,phase3}.py`. CLI thực tế dùng Python modules trong workflow.
- Protocol v2: Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`, NF4/BF16, LoRA rank8, deterministic SDPA math. Gold-only 3.053 QA/454 ảnh/405 nhóm, dev100 ảnh/666 QA, numeric379 QA. Không dùng API outputs để train; không mở test/OOD/audit/dev_calibrate.
- Preflight toàn train/dev đạt, 0 truncate. Smoke52 + resume50→52 + fresh-process reload đạt; adapter max diff0, greedy IDs trùng. V1 writer/resume failures được giữ trong artifacts, không sửa bằng chứng.
- **Cả ba seed17/42/2026 train hoàn tất**, mỗi seed191 updates, 3.053 unique QA. Thời gian train lần lượt2.176,76/2.149,10/2.160,07s, tổng108,10 phút; không OOM. Hai checkpoint96/191 mỗi seed đã lưu. Không cần train lại.

| Evaluation đã hoàn tất | QA | Strict EM | Numeric EM |
|---|---:|---:|---:|
| L1 | 666 | 34,3844% | 47,4934% |
| Seed17 step96 | 666 | 44,2943% | 59,6306% |
| Seed17 step191 | 666 | 45,6456% | 61,2137% |
| Seed42 step96 | 666 | 43,8438% | 59,3668% |
| Seed42 step191 | 666 | 45,7958% | 61,7414% |

Seed17/42 chọn step191 theo rule đã khóa. Chưa có tổng hợp ba seed hoặc final G3 report.

## Điểm dừng và bằng chứng

`artifacts/phase3/campaign_v1/L2_seed2026_step96/run.json`: **complete=false, completed238, expected666**. Partial predictions SHA256 `51819658cd253a2c15210dfe48256ab371039528583e99a82cdf7ee02559bee7`. Step191 seed2026 chưa bắt đầu. Parent đã được tạm giữ để tránh chạy bước mới, child nhận SIGINT, sau đó parent thoát fail-fast. `campaign.json` giữ `complete=false`, last step exit `-2`, error `RuntimeError`; đây là dừng theo yêu cầu chủ dự án. Không chấm partial như kết quả đủ666.

| Evidence cần giữ | Path tương đối repo |
|---|---|
| Plan | `artifacts/phase3/data_v2/manifest.json` |
| Frozen numeric/dev protocol | `artifacts/phase3/dev_protocol_v2.json` |
| Processor preflight | `artifacts/phase3/processor_preflight_v2.json` |
| Smoke / resume / proof | `artifacts/phase3/smoke_v3`, `smoke_resume_v2`, `resume_verification_v2.json` |
| Campaign / logs / training / metrics | `artifacts/phase3/campaign_v1/` |
| Kiểm tra code | `artifacts/phase3/checks_v2.json` |
| Sự kiện pause | `artifacts/phase3/pause_event_v1.json` |

Plan SHA256 `2cc060be5c31ff5a6216909039751c2a0f39756db7e5067796fdd8217d62b8a2`. Protocol SHA256 `db3134d89de01d833080efb7b0dccd6ed99ce3521dcddbecd5187bc20975016a`. Artifacts/data/weights bị ignore; GitHub checkout không chứa chúng. Không xóa hoặc ghi đè.

## Cách tiếp tục khi được yêu cầu

1. Kiểm tra git diff, hiện trạng file và hashes; giữ nguyên thay đổi của chủ dự án. Không đọc/in `.env`. Windows dùng `.venv/Scripts/python.exe`; GPU dùng WSL `Ubuntu-24.04`, user `vidoclens`, interpreter `/home/vidoclens/.venvs/vidoclens-ml-repro/bin/python`. Stack đã xác minh71/71 packages; không cần cài thêm.
2. **Campaign/predictor chưa có resume/append.** Không chạy lại toàn campaign hoặc output cũ. Training `--resume` có thật nhưng không cần dùng vì cả ba seed đã train xong.
3. Chạy lại đủ666 predictions seed2026/step96 vào thư mục MỚI để giữ nguyên partial và latency nhất quán; tiếp đó chạy step191. Các lệnh sau dành cho WSL tại repo, **chưa được thực thi**:

```bash
PY=/home/vidoclens/.venvs/vidoclens-ml-repro/bin/python
"$PY" -m vidoclens.student.predict --plan-dir artifacts/phase3/data_v2 --checkpoint artifacts/phase3/campaign_v1/L2_seed2026/checkpoint-0096 --output artifacts/phase3/continuation_v1/L2_seed2026_step96
"$PY" -m vidoclens.eval.student evaluate --plan-dir artifacts/phase3/data_v2 --run-dir artifacts/phase3/continuation_v1/L2_seed2026_step96 --protocol-path artifacts/phase3/dev_protocol_v2.json --output artifacts/phase3/continuation_v1/L2_seed2026_step96/metrics.json
"$PY" -m vidoclens.student.predict --plan-dir artifacts/phase3/data_v2 --checkpoint artifacts/phase3/campaign_v1/L2_seed2026/checkpoint-0191 --output artifacts/phase3/continuation_v1/L2_seed2026_step191
"$PY" -m vidoclens.eval.student evaluate --plan-dir artifacts/phase3/data_v2 --run-dir artifacts/phase3/continuation_v1/L2_seed2026_step191 --protocol-path artifacts/phase3/dev_protocol_v2.json --output artifacts/phase3/continuation_v1/L2_seed2026_step191/metrics.json
```

4. **Phần code còn thiếu cho phục hồi:** final audit hiện yêu cầu một campaign complete và layout cố định; chưa nhận các output continuation ở ngoài campaign. Cần triển khai manifest continuation/adoption có checksum/provenance cho các run cũ đã hoàn tất + hai run mới; giữ nguyên campaign thất bại do pause. Không sửa `complete=true`, không bỏ failed step để giả pass. Chưa triển khai tính năng này trong lượt pause.
5. Chạy kiểm tra liên quan sau thay đổi code, lưu checks mới (không ghi đè checks_v2). Audit checkpoint/coverage/source hashes, chọn checkpoint seed2026 theo rule đã khóa, tổng hợp đủ ba seed mean/sample SD, paired group bootstrap và compute estimate. Hoàn tất PHASE3_RESULTS/MODEL_CARD/STATUS/SOT/ADR khi G3 thật sự đạt; serving vẫn thuộc phase sau.

## Kiểm tra đã thực hiện

Checks v2: Windows311 passed/9 skipped; WSL320 passed; student24 cases; Ruff check/format120 files,39 schemas và file policy233 candidates đạt tại thời điểm kiểm. Doctor `inference_ready=false`/`model_not_configured`. Chưa xác minh GitHub CI mới/Docker/release. Lượt pause chỉ cập nhật tài liệu và kiểm tra nhẹ; không chạy thêm model.

Kiểm tra lúc bàn giao pause: không còn process training/predict/campaign Phase 3 trong WSL; 16/16 source hashes khớp checks_v2; UTF-8 và git diff --check đạt; file policy/YAML đạt235 candidates. Không chạy lại GPU hoặc full tests cho cập nhật tài liệu.

## Tiếp tục sau bàn giao

Chủ dự án đã yêu cầu đọc handoff và tiếp tục. Evaluation seed2026 chạy vào `continuation_v1`; code manifest/resolver/final audit đã bổ sung theo ADR-027. Hướng dẫn chính thức ở PHASE3_WORKFLOW; dùng STATUS để biết kết quả mới nhất.

## Kết thúc lượt tiếp tục

Hai dev evaluations seed2026 đã hoàn tất666 QA/run; G3 audit9/9 pass, mean EM ba seed46,00%, mọi seed chọnstep191. Đã có continuation manifest, raw metric replay, model card và báo cáo. Các lệnh/thiếu sót mô tả trong phần pause ở trên chỉ giữ làm lịch sử; không rerun vào các output đã có. Phase4 vẫn planned.
