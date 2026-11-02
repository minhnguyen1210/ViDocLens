# Môi trường và cách chạy lại pilot Phase 0

Ngày thực thi: **02/11/2026**. Máy đích Windows 11 + WSL2 Ubuntu 24.04.5, RTX 3060 12 GB, driver NVIDIA **617.42**. Driver không đổi. Python ML/OCR **3.11.14**, bản managed CPython build **20251028**, công cụ bootstrap **uv 0.9.6**. [STATUS](STATUS.md) là kết luận gate; tài liệu này là runbook của các thao tác thực tế, không phải hướng dẫn deploy API.

## Môi trường thực tế

- Code duy nhất: `C:\Users\Admin\Desktop\ViDocLens`, được Linux truy cập qua `/mnt/c/Users/Admin/Desktop/ViDocLens`.
- User WSL mặc định: `vidoclens`, UID 1000, không thuộc sudo group, password login bị khóa. Không tạo hoặc đưa mật khẩu vào chat/repo. Khi cần quản trị distro, Windows owner dùng `wsl -d Ubuntu-24.04 -u root`; chạy model bằng user thường.
- Hai venv chính: `/home/vidoclens/.venvs/vidoclens-ml` và `/home/vidoclens/.venvs/vidoclens-ocr`.
- Hai venv kiểm chứng dựng lại: cùng đường dẫn với hậu tố `-repro`. Không copy site-packages từ môi trường đầu: tạo venv mới và `uv pip sync --require-hashes --only-binary :all:` từ lock.
- `.venv` Windows vẫn dành cho core; không cài Torch/Paddle vào đó. Không chỉnh PATH/Python mặc định Windows.
- `.wslconfig`: RAM 12 GB, 8 logical CPUs, swap 4 GB. WSL thực tế báo giới hạn tương ứng; không có Docker trong pilot.

Ubuntu đã cài `python3-venv`, `ca-certificates` và **`libgomp1`**. Import Paddle lần đầu lỗi thiếu `libgomp.so.1`; cài `libgomp1` giải quyết lỗi. `apt` kéo các cập nhật dependency Python 3.12 của Ubuntu, nhưng Python 3.11 cho dự án ở user directory, không thay interpreter hệ thống. Warning thiếu `ccache` không chặn wheel inference; không cài compiler/CUDA toolkit hoặc Linux NVIDIA driver.

[Inventory sau reboot](../artifacts/phase0/environment_post_reboot.json) lưu WSL/OS/kernel, GPU, RAM/swap, apt versions, hash executable Python và hashes locks. Đây là artifact local bị Git ignore; không phải bằng chứng tương thích trên mọi host.

| Thành phần | Phiên bản đã cài và smoke ở môi trường đầu |
|---|---|
| PyTorch / torchvision | `2.8.0+cu126` / `0.23.0+cu126`, CUDA runtime wheel 12.6 |
| Transformers / PEFT / Accelerate | `4.57.1` / `0.17.1` / `1.10.1` |
| bitsandbytes | `0.48.1`, 300 lớp Linear4bit NF4, double quantization thực |
| PaddlePaddle CPU / PaddleOCR / PaddleX | `3.2.0` / `3.2.0` / `3.2.0` |
| Student | Qwen3-VL-2B-Instruct, revision `89644892e4d85e24eaac8bacfd4f463576704203` |
| OCR detector | PP-OCRv5_server_det, revision `ca867c897ecbca8873081573a802ad70d499cb94` |
| OCR recognizer | latin_PP-OCRv5_mobile_rec, revision `ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57` |

Nguồn API/version: [Torch wheel pair](https://pytorch.org/get-started/previous-versions/), [Transformers 4.57.1](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl), [mapping PaddleOCR 3.2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.2.0/paddleocr/_pipelines/ocr.py), [uv hashed locks](https://docs.astral.sh/uv/pip/compile/). Mã đã cài xác nhận `vi` → recognizer Latin v5; khi truyền model directories trực tiếp, profile lưu mapping thay vì giả định tham số `lang` còn được áp dụng.

## Lock và dựng lại

**Đã kiểm chứng:** cả hai venv mới chạy lại đủ 20 ảnh; 20/20 raw student answers/output tokens và 20/20 canonical OCR results giống lượt đầu. Xem [báo cáo đối chiếu](../artifacts/phase0/reproducibility_verification.json). Review trực quan riêng ở [artifact](../artifacts/phase0/ocr_visual_review.json); không sửa cờ review trong summary tự động hoặc giả có OCR gold.

Hai lock đầy đủ gồm transitive dependencies và hashes, dành cho **Linux x86-64 / CPython 3.11.14**:

- [ML lock](../infra/requirements/phase0-ml-linux-py311.lock): 71 third-party packages; PyPI + official PyTorch CUDA 12.6 index.
- [OCR lock](../infra/requirements/phase0-ocr-linux-py311.lock): 91 third-party packages; PyPI.

Project `vidoclens` được cài editable riêng bằng `--no-deps`; không đưa local source path thành hash wheel giả. Git chưa có commit; source snapshot của mỗi runner và hash được lưu cùng run. Muốn tái lập ở máy khác cần đúng source checkout, model/dataset manifests và apt/driver tương thích, không chỉ hai lock.

Script [lock_phase0_environment.sh](../scripts/lock_phase0_environment.sh) ghi freeze của môi trường hiện có, compile hash lock, tạo venv `-repro`, sync, pip check và so sánh freeze. Script từ chối ghi đè lock/venv đã tồn tại. Không chạy lại script đó chỉ để kích hoạt môi trường; không xóa venv hoặc tái resolve lock đã kiểm chứng.

Ví dụ dựng từ lock hiện có vào **đường dẫn mới**, trong Ubuntu; các lệnh quản lý Python và pip đều dùng full path:

```bash
VIDOCLENS_UV="$HOME/.local/share/vidoclens-bootstrap/bin/uv"
VIDOCLENS_REPO=/mnt/c/Users/Admin/Desktop/ViDocLens
VIDOCLENS_NEW="$HOME/.venvs/vidoclens-ml-new"
test ! -e "$VIDOCLENS_NEW" || exit 1
"$VIDOCLENS_UV" venv --python 3.11.14 "$VIDOCLENS_NEW"
"$VIDOCLENS_UV" pip sync --python "$VIDOCLENS_NEW/bin/python" \
  --require-hashes --only-binary :all: --index-strategy unsafe-best-match \
  "$VIDOCLENS_REPO/infra/requirements/phase0-ml-linux-py311.lock"
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_NEW/bin/python" --no-deps -e "$VIDOCLENS_REPO"
"$VIDOCLENS_UV" pip check --python "$VIDOCLENS_NEW/bin/python"
```

Với OCR, dùng đường dẫn mới riêng và OCR lock, không cần `--index-strategy`. Với ML, cờ index strategy chỉ phục vụ hai nguồn publisher đã ghi trong lock và toàn bộ versions/hashes đã cố định; không thêm index khác.

## Chạy lại với ảnh và weights local

Từ PowerShell ở repository:

```powershell
wsl -d Ubuntu-24.04 -u vidoclens -- bash /mnt/c/Users/Admin/Desktop/ViDocLens/scripts/run_phase0_pilot.sh student student_new_run -repro
wsl -d Ubuntu-24.04 -u vidoclens -- bash /mnt/c/Users/Admin/Desktop/ViDocLens/scripts/run_phase0_pilot.sh ocr ocr_new_run -repro
```

Chạy tuần tự để tránh OCR tranh CPU khi đo student. Bỏ `-repro` để dùng venv chính. Tên run phải mới; runner không ghi đè kết quả cũ. Script đặt Hugging Face/Transformers offline và tắt telemetry; student dùng `local_files_only=True`, OCR truyền đường dẫn model local. Không gọi teacher/API hoặc gửi ảnh ra dịch vụ.

Các runner nằm trong [student smoke](../src/vidoclens/student/smoke.py) và [OCR smoke](../src/vidoclens/ocr/smoke.py); không phải implementation API/training. Input được validate bởi [Pydantic pilot contract](../src/vidoclens/contracts/pilot.py), reject extra gold fields, duplicate IDs/hash, ảnh sai hash, đường dẫn thoát repo và hash chạm split ngoài train. Dùng image inventory local đã audit; đây là boundary kỹ thuật, không phải ACL chống người có quyền sửa filesystem.

- Student: một warm-up, 20 ảnh, batch/concurrency 1, NF4 + double quant, BF16 compute, SDPA; pixel cap 262.144, output cap 128; prompt gồm ảnh và nguyên câu hỏi. Ghi output raw, tokens/grid, CUDA peak allocated/reserved, RSS, load và latency sau CUDA synchronize. Không OCR-correct đáp án hoặc đọc gold.
- OCR: một warm-up, 20 ảnh; CPU 4 threads, MKLDNN off, detector cạnh tối đa 960, không orientation/unwarping vì pilot dùng rotated archive. Lưu raw polygons, text, confidence và `OCRResult` với box normalized `[0,1]`; NFC không sửa digit. Reading order là thứ tự engine, chưa có thuật toán bố cục/cross-line riêng.
- Output local `artifacts/phase0/<run>/`: environment/profile, manifest, source snapshots, per-sample diagnostics và summary. OCR có ảnh box để kiểm tra; ảnh, text/OCR/predictions và model weights đều Git ignored. Không upload artifacts này như log công khai.

## Giới hạn phép thử

Smoke chứng minh đường chạy kỹ thuật trên host hiện tại. Không có EM/F1/ANLS/CER, kết luận chất lượng, QLoRA backward/train/save-resume, teacher 4B hay deploy. Lượt student đầu có 7/20 đầu ra chạm cap 128 tokens; OCR nhận đủ 20 ảnh nhưng quan sát thấy mất dấu tiếng Việt và tách dòng. Không tăng cap/chọn prompt theo test để che lỗi. Các profile này là điểm xuất phát cho G1/G3, chưa là lựa chọn chất lượng cuối cùng.

`vidoclens doctor` và API readiness vẫn báo `model_not_configured`: offline smoke không tự tích hợp model vào server. Docker, public hosting và API trả phí không nằm trong lượt này.
