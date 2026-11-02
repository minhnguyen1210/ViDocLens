# Phương án thiết lập môi trường ViDocLens

Ngày lập/cập nhật: **02/11/2026**. **Chủ dự án đã cho phép cài/tải và đã reboot Windows.** WSL 3.0.3/Ubuntu 24.04.5 nhận GPU; Python 3.11.14, hai venv ML/OCR và hai venv dựng lại từ hash lock đã được tạo. Student NF4 GPU và OCR CPU đã chạy 20 ảnh. `.wslconfig` 12 GB/8 CPUs/4 GB swap có hiệu lực; driver giữ 617.42. Xem [STATUS](STATUS.md) cho kết luận gate mới nhất và [runbook thực tế](PHASE0_ENVIRONMENT.md) để chạy lại.

Các mục dưới lưu **phương án và lệnh ứng viên ban đầu**. Khi tái lập, dùng lock/runbook đã đo thay vì resolve lại các range. Ảnh và student/OCR weights đã tải; không tải trùng. Không cần reboot hoặc cài lại WSL ở trạng thái hiện tại.

Thiết kế tuân theo [SOT](../SOURCE_OF_TRUTH.md). Máy đã kiểm kê: Windows 11 Pro, i5-14400F, RTX 3060 12 GB, RAM 31,76 GiB, ổ C trống khoảng 284,19 GiB. Xem thời điểm và giới hạn phép đo ở [STATUS](STATUS.md).

## 1. Lựa chọn đề xuất

**WSL2 + Ubuntu 24.04 LTS + Python 3.11 riêng cho ML**, cùng môi trường OCR CPU độc lập. Đây là môi trường đích đã chọn trong SOT; phiên bản distro và bộ package dưới đây là ứng viên thực thi, chưa là environment lock được kiểm chứng.

| Lựa chọn | Có thể làm gì | Điều kiện / đánh đổi |
|---|---|---|
| Tiếp tục Windows `.venv` hiện có | Audit CSV, viết loader/evaluator, phát triển core/API | Có thể làm ngay; chưa xác nhận VLM/OCR GPU |
| WSL2 + Ubuntu — đề xuất | ML trong Linux, gần môi trường deploy dự kiến | Cài thành phần Windows/Linux, cần admin/reboot; dùng thêm đĩa/RAM |
| Windows native cho ML | Một môi trường Python mới trên Windows | Phải pilot toàn bộ Torch/Transformers/PEFT/bitsandbytes/OCR; nếu chọn làm chuẩn thì cập nhật SOT/ADR |
| Máy Linux/cloud khác | Giữ Windows phục vụ code và client | Cần tài nguyên, quyền dữ liệu và ngân sách riêng; chưa chọn |

Không cần Docker để hoàn thành pilot local Phase 0. Docker thuộc công việc đóng gói sau này. Driver NVIDIA Windows hiện tại sẽ được giữ để thử trước; kết quả `nvidia-smi` chưa đủ chứng minh framework hoạt động.

## 2. Những thay đổi dự kiến và phạm vi ảnh hưởng

| Thao tác về sau | Phạm vi ảnh hưởng | Cách kiểm soát |
|---|---|---|
| Cài WSL2/Ubuntu | Windows features, Linux kernel/distro, virtual disk; có thể cần reboot | Lưu công việc trước cài; ghi trạng thái trước/sau; không tự reboot |
| Cấu hình `.wslconfig` | Áp dụng toàn bộ WSL2 distros của tài khoản | Đọc/backup file có sẵn trước khi sửa; không ghi đè cấu hình khác |
| Cài package Ubuntu | Chỉ hệ thống bên trong distro Linux | Không dùng Python/pip Windows để cài vào Linux |
| Python/venv ML và OCR | Thư mục người dùng Linux, không thay Python hệ thống | Dùng đường dẫn interpreter rõ, không `sudo pip` |
| Torch CUDA wheel | Venv ML cùng dependency runtime | Không tự cài NVIDIA Linux display driver hoặc CUDA toolkit toàn máy |
| Tải model/dataset | Dung lượng đĩa, băng thông; GPU/RAM khi chạy | Kiểm tra kích thước, quyền, hash; chỉ tải artifact đã chọn |

Microsoft mô tả bước cài WSL cần quyền administrator và restart, đồng thời cài distro Linux. WSL2 dùng một VM do Windows quản lý; Windows vẫn là hệ điều hành host. [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install), [WSL versions](https://learn.microsoft.com/en-us/windows/wsl/compare-versions).

NVIDIA hướng dẫn dùng driver Windows cho GPU trong WSL và không cài thêm NVIDIA Linux display driver vào WSL. Kế hoạch này thử wheel PyTorch trước; chỉ xem xét toolkit nếu có nhu cầu build extension đã chứng minh. [CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

## 3. Bố trí thư mục và tài nguyên

Giữ **một nguồn code đang chỉnh sửa** tại `C:\Users\Admin\Desktop\ViDocLens`; ban đầu Linux truy cập qua `/mnt/c/Users/Admin/Desktop/ViDocLens`. Không sao chép `.venv` Windows sang Linux và không tạo hai checkout cùng sửa mà chưa có quy trình Git.

| Đường dẫn dự kiến trong Linux | Công dụng |
|---|---|
| `~/.local/share/vidoclens-bootstrap/` | Venv nhỏ chứa công cụ quản lý Python `uv` |
| `~/.venvs/vidoclens-ml/` | Python 3.11 + Torch/Transformers/PEFT/bitsandbytes |
| `~/.venvs/vidoclens-ocr/` | Python 3.11 + Paddle CPU/PaddleOCR |
| `~/vidoclens-storage/data/` | Ảnh đã nhập có manifest; dùng filesystem Linux cho I/O nặng |
| `~/vidoclens-storage/cache/` | Model/OCR cache và dữ liệu tạm được phép |
| `~/vidoclens-storage/artifacts/` | Model/run artifacts, không đưa lên Git |

Project chưa có config loader đầy đủ; không giả định đặt biến đường dẫn là pipeline tự dùng. Khi triển khai loader/runtime phải truyền đường dẫn thực, dump resolved config và kiểm tra hash. Nếu chuyển checkout chính sang Linux ở giai đoạn sau, chốt một vị trí authoritative và dùng Git đồng bộ; chưa di chuyển trong lượt này.

Đề xuất khởi điểm cho máy RAM 32 GB, **chưa áp dụng**:

```ini
[wsl2]
memory=12GB
processors=8
swap=4GB
```

Đặt tại `%UserProfile%\.wslconfig` chỉ khi bắt đầu triển khai. Đây là giới hạn tài nguyên VM, không phải VRAM GPU. 12 GB RAM là mức thử thận trọng; nếu load model cần nhiều hơn, đo peak trước khi điều chỉnh. Swap không thay thế VRAM và có thể làm chậm khi thiếu RAM. Việc thay file thường cần dừng WSL để có hiệu lực; không dừng các phiên WSL khác khi chưa lưu công việc. [Microsoft configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

Dự trù ban đầu **20–40 GiB** cho distro, hai môi trường và package caches; đây là ước lượng lập kế hoạch, chưa đo. Weights, ảnh nén và ảnh giải nén được cộng riêng sau khi biết kích thước thực. Giữ ít nhất 50 GiB trống là ngưỡng vận hành đề xuất. Không suy kích thước giải nén từ dung lượng ZIP ảnh đang hiển thị trên Drive.

## 4. Bộ phiên bản để thử đầu tiên

Các version dưới đã được kiểm tra **tồn tại trên registry/docs**, chưa cài, chưa resolve toàn bộ dependency, chưa chạy chung trên máy. Đây là bộ ứng viên có tài liệu version cụ thể, không phải tuyên bố “mới nhất”, “an toàn tuyệt đối” hoặc “đã tương thích”.

| Thành phần | Ứng viên | Gate trước khi công nhận |
|---|---|---|
| Distro | Ubuntu-24.04 trên WSL2 | Có trong danh sách distro khi cài; WSL version = 2 |
| Python | 3.11, ghi patch version thực khi resolve | Interpreter Linux đúng 3.11; tách Windows `.venv` |
| Bootstrap | uv 0.9.6 trong venv riêng | Có wheel Linux x86-64; chạy được CLI |
| Torch/torchvision | 2.8.0 / 0.23.0, CUDA wheel `cu126` | Official wheel pair; GPU matmul và torchvision import pass |
| Transformers | 4.57.1 | Import `Qwen3VLForConditionalGeneration`/processor và chạy ảnh thật |
| PEFT / Accelerate | 0.17.1 / 1.10.1 | K-bit adapter forward/backward, save/load |
| bitsandbytes | 0.48.1 | NF4 hoạt động thực trên GPU, không âm thầm fallback CPU |
| PaddlePaddle CPU / PaddleOCR | 3.2.0 / 3.2.0 | Import, CPU inference và recognizer tiếng Việt thực sự hoạt động |
| Student | `Qwen/Qwen3-VL-2B-Instruct` | Observed revision được ghi ở DATA_ACCESS_REGISTER; chưa tải/kiểm chứng hoặc khóa revision trong run config |
| OCR recognizer | `latin_PP-OCRv5_mobile_rec`, `lang=vi` | Kiểm tra model mapping của phiên bản cài; không suy từ docs `latest` |

Pair Torch/vision và `cu126` có trong [hướng dẫn phiên bản PyTorch](https://pytorch.org/get-started/previous-versions/). [Transformers 4.57.1](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl) có Qwen3-VL; [bitsandbytes 0.48.1](https://huggingface.co/docs/bitsandbytes/v0.48.1/installation) có hướng dẫn NVIDIA. Đã kiểm tra PyPI metadata cho cả chín package trong bảng, có wheel Python 3.11/Linux x86-64 hoặc universal phù hợp ở mức tên wheel.

PaddleOCR docs hiện hành liệt kê recognizer tiếng Việt, nhưng trang version 3.2.0 không truy cập được qua web reader trong lượt này. Vì vậy **hỗ trợ `vi` ở tổ hợp Paddle 3.2.0 vẫn là gate mở**, không phải điều đã kiểm chứng. Nếu mapping/import không đạt, dừng và chọn phiên bản OCR khác có bằng chứng; không đổi âm thầm sang model ngôn ngữ khác. [OCR quick start](https://www.paddleocr.ai/latest/en/quick_start.html), [language mapping](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html).

## 5. Trình tự dự kiến — các lệnh chưa chạy

### A. Cài nền WSL, chỉ ở lượt triển khai được cho phép

Trước bước này: lưu công việc, kiểm tra quyền administrator, dung lượng ổ C, trạng thái Windows update/reboot và khả năng đăng nhập lại sau reboot. Không thay firewall/VPN hoặc driver để “thử cho chạy”.

PowerShell administrator:

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

Lệnh đầu phụ thuộc thành phần WSL có thể cần được bootstrap trước; nếu máy hiện tại báo WSL chưa cài thì dùng bước cài theo hướng dẫn Microsoft và kiểm tra lại distro sau đó. Restart theo yêu cầu của hệ thống tại thời điểm người dùng chọn. Tạo tài khoản Linux ở lần khởi động đầu; không đưa mật khẩu vào repo hoặc chat.

Sau cài:

```powershell
wsl --status
wsl --list --verbose
wsl -d Ubuntu-24.04 -- uname -r
wsl -d Ubuntu-24.04 -- nvidia-smi
```

**Gate A:** Ubuntu chạy dưới WSL2, nhận RTX 3060 và driver; nếu chưa đạt thì dừng trước cài framework.

### B. Tạo Python Linux riêng

Các lệnh dưới chạy **trong Ubuntu**, sau Gate A. `apt` chỉ áp dụng bên trong distro; bootstrap dùng Python Ubuntu để tải uv, rồi uv quản lý Python 3.11. Cách cài uv bằng pip trong môi trường riêng và cài Python có tài liệu tại [uv installation](https://docs.astral.sh/uv/getting-started/installation/) và [managed Python](https://docs.astral.sh/uv/guides/install-python/).

```bash
sudo apt update
sudo apt install -y python3-venv ca-certificates
python3 -m venv "$HOME/.local/share/vidoclens-bootstrap"
"$HOME/.local/share/vidoclens-bootstrap/bin/python" -m pip install "uv==0.9.6"
VIDOCLENS_UV="$HOME/.local/share/vidoclens-bootstrap/bin/uv"
"$VIDOCLENS_UV" python install 3.11
"$VIDOCLENS_UV" venv --python 3.11 "$HOME/.venvs/vidoclens-ml"
"$VIDOCLENS_UV" venv --python 3.11 "$HOME/.venvs/vidoclens-ocr"
VIDOCLENS_ML_PY="$HOME/.venvs/vidoclens-ml/bin/python"
VIDOCLENS_OCR_PY="$HOME/.venvs/vidoclens-ocr/bin/python"
"$VIDOCLENS_ML_PY" --version
"$VIDOCLENS_OCR_PY" --version
```

Giữ các biến trong cùng terminal hoặc khai báo lại khi mở terminal mới. Nếu các venv đích đã tồn tại, kiểm tra trước; không tạo đè hoặc xóa tự động. Không sửa PATH/Python mặc định của Windows hay Python hệ thống Ubuntu.

### C. Cài ứng viên VLM và kiểm tra dependency

```bash
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_ML_PY" \
  "torch==2.8.0" "torchvision==0.23.0" \
  --index-url https://download.pytorch.org/whl/cu126
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_ML_PY" \
  "transformers==4.57.1" "peft==0.17.1" "accelerate==1.10.1" "bitsandbytes==0.48.1"
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_ML_PY" \
  -e '/mnt/c/Users/Admin/Desktop/ViDocLens[serve,dev]'
"$VIDOCLENS_UV" pip check --python "$VIDOCLENS_ML_PY"
```

Đây chưa phải lock toàn dependency. Trước và sau bước cài tiếp theo, kiểm tra Torch/vision vẫn đúng version/CUDA build; nếu resolver thay ngoài dự kiến thì dừng, lập constraints rõ và resolve lại. Dùng default SDPA, chưa cài FlashAttention/xFormers hoặc build CUDA extension trong pilot đầu.

Smoke không tải model:

```bash
"$VIDOCLENS_ML_PY" - <<'PY'
import torch, torchvision, transformers, peft, accelerate, bitsandbytes
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
assert torch.cuda.is_available(), "CUDA unavailable"
assert torch.__version__.startswith("2.8.0"), torch.__version__
assert torchvision.__version__.startswith("0.23.0"), torchvision.__version__
assert torch.version.cuda == "12.6", torch.version.cuda
x = torch.randn(256, 256, device="cuda")
y = x @ x.T
torch.cuda.synchronize()
assert torch.isfinite(y).all().item()
print(torch.cuda.get_device_name(0), torch.__version__, torch.version.cuda)
print("GPU tensor + imports passed; VLM and QLoRA not yet tested")
PY
```

**Gate C:** dependency/import/tensor pass; chưa đồng nghĩa model, NF4 hay training đã đạt.

### D. Cài OCR CPU độc lập

```bash
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_OCR_PY" "paddlepaddle==3.2.0"
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_OCR_PY" "paddleocr==3.2.0"
"$VIDOCLENS_UV" pip check --python "$VIDOCLENS_OCR_PY"
"$VIDOCLENS_OCR_PY" -c 'import paddle, paddleocr; paddle.set_device("cpu"); print(paddle.__version__, paddle.get_device())'
```

Sau import, kiểm tra mapping `vi` và recognizer cụ thể trước khi tải weights. Nếu cần thư viện Linux bổ sung do wheel báo thiếu, ghi đúng dependency lỗi rồi bổ sung trong distro; không cài cả desktop/OpenCV GPU tùy tiện. OCR chạy bằng subprocess/CLI của venv OCR và trả JSON theo contract; không import Paddle từ venv ML. Adapter này chưa được viết.

### E. Pilot model và khóa môi trường

Chỉ tải weights khi bước triển khai đó đã được giao và đã chốt nguồn/revision/dung lượng. Dùng ảnh train hoặc dev_select có quyền, tuyệt đối không dùng test để chọn model/config.

1. OCR 10–20 ảnh đại diện, kiểm tra tiếng Việt/số/bbox; pilot chọn OCR đầy đủ theo SOT dùng 100 ảnh.
2. Student NF4, một ảnh, pixel cap 262.144; đo latency, RAM và GPU peak allocated/reserved; kiểm tra answer có nội dung thật.
3. Khi chuyển sang kiểm tra training feasibility, chạy 50–100 steps và save/load adapter theo SOT; đây là gate riêng, không suy từ inference pass.
4. Lưu Python patch, package freeze, wheel/index provenance, OS/WSL/kernel/driver, processor/model revision và kết quả smoke. Lệnh freeze dự kiến:

```bash
mkdir -p "$HOME/vidoclens-storage/artifacts/environment"
"$VIDOCLENS_UV" pip freeze --python "$VIDOCLENS_ML_PY" \
  > "$HOME/vidoclens-storage/artifacts/environment/ml-freeze.txt"
"$VIDOCLENS_UV" pip freeze --python "$VIDOCLENS_OCR_PY" \
  > "$HOME/vidoclens-storage/artifacts/environment/ocr-freeze.txt"
```

Freeze là inventory, chưa đủ để gọi lock tái lập. Tiếp tục resolve lock/constraints, lưu nguồn CUDA wheels và thử dựng lại môi trường sạch trước khi công nhận environment chuẩn. Ghi trạng thái pass/fail thực vào STATUS và cập nhật ADR khi ứng viên trở thành lựa chọn chính thức.

## 6. Dừng, phục hồi và bước có thể làm trước khi cài

Nếu WSL/GPU/import lỗi: giữ log đã bỏ secrets, dừng ở gate đó; không tự đổi driver, cài Linux NVIDIA driver, tắt bảo mật hoặc đổi firewall. Có thể tiếp tục xử lý annotations và evaluator trên Windows trong lúc giải quyết.

`wsl --shutdown` chỉ dừng WSL VM, không gỡ dữ liệu; cần lưu các job trước khi dùng. Gỡ distro/unregister là thao tác khác và có thể xóa toàn bộ dữ liệu Linux: không đưa vào lệnh cài đặt tự động. Nếu cần hoàn tác về sau, backup/export distro và dữ liệu trước, kiểm tra phục hồi rồi mới thực hiện quy trình gỡ được chấp nhận. Khôi phục `.wslconfig` cũ nếu đã thay.

Loader CSV bảo vệ gold và metric `strict_nfc_v1` đã triển khai trên Windows; xem [hướng dẫn](ANNOTATION_LOADER_AND_METRICS.md). Generator split/near-dedup và official scorer parity vẫn thuộc G1. Các bước A–E đã được thực thi trong phạm vi pilot inference theo quyền chủ dự án; training feasibility/save adapter vẫn thuộc G3. Các sai khác thực tế, dependency bổ sung và hash locks ở [runbook](PHASE0_ENVIRONMENT.md).
