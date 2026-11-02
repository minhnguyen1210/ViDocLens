# Dự toán compute và chi phí Phase 0

Ngày lập/cập nhật: **02/11/2026**. Đây là **mô hình ước tính**, không phải bill, benchmark hoặc budget trả phí được duyệt. Budget API hiện tại **0 USD**, external disabled. Đã được phép cài/tải và đã chạy pilot local; không gọi dịch vụ trả phí hoặc thuê GPU. Số đo feasibility dưới đây không phải accuracy benchmark.

## 1. Những số đã biết và chưa biết

- RTX 3060 có 12.288 MiB VRAM; lúc inventory còn khoảng 10.566 MiB. Đây không phải peak của student.
- ZIP annotations 1.516.419 bytes, 64.812 QA tham chiếu 9.500 ảnh. Số QA không bằng số API requests: SOT nhóm câu hỏi theo ảnh.
- Đã tải rotated_images.zip **4.071.333.203 bytes**, không tải raw 15,59 GB. Student files **4.266.647.442 bytes**, OCR files **96.570.324 bytes**; hashes/revisions ở STATUS.
- Kế hoạch môi trường dành dự trù 20–40 GiB cho distro/venvs/caches, cộng ảnh/weights/artifacts riêng và giữ 50 GiB trống. Đây là giả định vận hành.
- Đã có tokens/grid và tốc độ từng mẫu student/OCR trong pilot local; chưa có giây/update, retention, teacher snapshot/price card, watts toàn máy hoặc giá điện áp dụng.

### Số đo local sau dựng lại môi trường

Nguồn: [reproducibility verification](../artifacts/phase0/reproducibility_verification.json), 20 ảnh train, một warm-up riêng/engine, chạy tuần tự. Student NF4 output cap 128, có 7/20 outputs chạm cap. Tổng thời gian trung bình **4,215 s/ảnh/câu hỏi**, p50/p95 **4,478/6,366 s**; CUDA peak allocated **1,55 GiB**, reserved **2,15 GiB**. OCR CPU 4 threads, max side 960, trung bình **7,412 s/ảnh**, p50/p95 **7,283/8,529 s**. Lỗi dấu/tách dòng còn quan sát được.

Nếu chỉ ngoại suy tuyến tính profile OCR này: `9.500 × 7,411785 / 3.600 ≈ 19,56 giờ`, chưa gồm cold load, cache I/O, retry hoặc profile chất lượng cao hơn. Đây là **ước tính từ mẫu nhỏ**, chưa chạy toàn corpus. Không suy tốc độ training hoặc teacher 4B từ student inference; không dùng output bị cắt để dự toán chất lượng.

## 2. API — công thức để thay bằng giá và usage thật

Với nhóm request `j`, chi phí dự kiến:

```text
C = sum_j N_j * (I_j * p_in + O_j * p_out) / 1_000_000
C_reserved = C * (1 + retry_reserve) + provider_fees
```

`I_j` gồm text + image units đã đổi sang token theo **đúng model/provider**; `O_j` gồm mọi output/reasoning token tính phí nếu có. Cache/batch discount chỉ áp dụng sau xác minh price card, không mặc định. Reserve không phải mức đảm bảo: ledger phải chặn thực tế trước submit.

Bảng nhạy cảm dùng **giả định minh họa** 1.200 input và 256 output tokens/request, reserve 20%, không phải token đo trên receipts. `p_in`, `p_out` là USD/triệu token chưa chốt:

| Request groups | Base cost (USD) | Có reserve 20% |
|---:|---|---|
| 50 | `0.06*p_in + 0.0128*p_out` | Nhân 1,2 |
| 10.000 | `12*p_in + 2.56*p_out` | Nhân 1,2 |
| 50.000 | `60*p_in + 12.8*p_out` | Nhân 1,2 |

Ví dụ thuần số với **đơn giá giả định** `p_in=1`, `p_out=5`: tương ứng 0,1488 / 29,76 / 148,80 USD có reserve. Đây **không phải báo giá của OpenAI hay provider nào** và không phải đề xuất tự chi số tiền đó. Nhóm nhiều QA có thể vượt 256 output tokens; pilot phải đo lại p50/p95 và worst-case cap 1.024 đang có trong config. Đếm prompt variants, seeds nếu phát sinh calls, repair/retry và teacher-all comparison riêng.

Khi bắt đầu Phase 2: kiểm tra nguồn giá chính thức và quyền tài khoản, chọn snapshot; estimate 50 ảnh trước gửi, xin budget cụ thể từ chủ dự án; đo usage và cập nhật estimate toàn run. Không đọc API key để làm bước dự toán này.

## 3. Training và local inference

```text
effective_batch = micro_batch * gradient_accumulation * gpu_count
updates = epochs * ceil(examples_per_epoch / effective_batch)
hours = updates * measured_seconds_per_optimizer_update / 3600
total_hours = sum(hours_per_run) + evaluation + OCR + label_generation + reloads
```

Phải dùng số QA thực sau split/dedup/filter. `k=10` là tỷ lệ receipt groups có gold, không mặc định chính xác 10% QA. Tính lại cho từng arm; `P1-full` và `P1-size` là hai run riêng. Giây/optimizer update đã gồm tất cả gradient accumulation microsteps.

Ví dụ nhạy cảm **không phải phép đo**: 10.000 examples, 2 epochs, microbatch 1, accumulation 16, 1 GPU → 1.250 updates:

| Giả định giây/update | Giờ/run | 12 runs minh họa (4 arms × 3 seeds) |
|---:|---:|---:|
| 2 | 0,69 | 8,33 |
| 10 | 3,47 | 41,67 |
| 30 | 10,42 | 125,00 |

Bốn arms core là L2-k10, P1-full, P1-size, P2; bảng giả định cùng 10.000 examples để thấy độ nhạy, **không mô tả kích thước thật của bốn arms**. Sau pilot dùng thời gian/token/pixel thực để quyết định lịch. Nhánh không lọc/lọc cần matched-size và matched-compute theo SOT; không suy giảm runtime là tăng chất lượng.

OCR toàn corpus: `9.500 * measured_seconds_per_image / 3600`; teacher local tính theo nhóm ảnh/QA, gồm thời gian load luân phiên model. Điện: `hours * measured_wall_watts / 1000 * tariff_per_kWh`; chưa có power meter/tariff nên chưa ra số tiền. Không lấy TDP GPU làm mức tiêu thụ toàn máy.

## 4. Giới hạn và bước chốt sau này

1. G0: khi được cài/tải, chạy GPU inference thực; ghi p50/p95, peak allocated/reserved, RAM, image-token profile và failed requests. Không dùng số training ở bảng trên để đóng G0.
2. G3: train smoke 50–100 optimizer updates, loss finite, adapter save/reload; đo steady-state sau warm-up và cập nhật dự toán. Full training chưa cần chạy để hoàn thành Phase 0.
3. Trước mỗi lượt trả phí: budget được duyệt + price snapshot + quyền dữ liệu + ledger reservation. Nếu thiếu, dừng external; local development vẫn tiếp tục.
4. Đã có **hash locks ML/OCR**, hai venv mới được dựng và smoke pass trên cùng host. Xem [runbook](PHASE0_ENVIRONMENT.md). Train feasibility và estimate từ giây/update thật vẫn thuộc G3.
