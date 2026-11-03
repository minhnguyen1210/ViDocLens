# Trạng thái ViDocLens

> **Nhật ký các mốc trước.** Phần đầu lưu mốc đến 22:56 ngày 02/11/2026; các snapshot bổ sung có ngày và tiêu đề riêng. Các trạng thái “chưa đạt”, counts kiểm thử và chỉ dẫn bước tiếp theo bên dưới phản ánh từng thời điểm cũ. Hiện trạng có thẩm quyền ở [STATUS.md](STATUS.md); không cập nhật lại các mốc này cho giống hiện tại.

Ngày cập nhật: **02/11/2026, 22:56 (Asia/Saigon, UTC+07:00)** · Chủ dự án: Nguyễn Hữu Gia Minh · **G0 và G1 đạt; Phase 1 hoàn tất 100% theo phương án dùng AI được chủ dự án yêu cầu, SOT v1.7/ADR-021**. Mục **Đóng G1 bằng AI** là hiện trạng mới nhất; các mốc trước giữ lịch sử. Nhãn AI không là human gold hoặc full OOD benchmark.

**Chỉ dẫn hiện hành:** chủ dự án đã cho phép cài WSL2/Ubuntu, môi trường ML/OCR riêng và tải ảnh/trọng số cần thiết. Quyền này thay chỉ dẫn giữ nguyên hệ thống trước đó và tiếp tục có hiệu lực sau reboot. Giữ driver NVIDIA hiện tại; không tự khởi động lại máy, không gọi API trả phí hoặc bật public hosting.

Chỉ dẫn mới “sử dụng AI để hoàn thành toàn bộ phase 1” cho phép thay human review tại G1 bằng quy trình AI có provenance, kiểm tra chéo local và adjudication. Không đổi reviewer AI thành người; human validation phục vụ nghiên cứu/release vẫn chưa thực hiện.

[SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) quy định phạm vi và kiến trúc. Tài liệu này chỉ ghi tiến độ có bằng chứng; kế hoạch không được đánh dấu thành kết quả.

## Hiện trạng

| Hạng mục | Trạng thái | Bằng chứng / việc còn thiếu |
|---|---|---|
| Ý tưởng gốc | Đã tiếp nhận | `PROJECT_OVERVIEW.md` được giữ làm lịch sử |
| Thiết kế và cấu trúc repo | SOT v1.7, ADR-021 | G1 dùng AI theo chỉ dẫn mới; containment không nhận semantic duplicates, AI không là human gold |
| Kiểm thử local mới nhất | **Linux 205 passed; Windows 198 passed/7 skipped**, Ruff pass | NumPy cases chạy đủ Linux; warning Starlette/httpx; GitHub CI chưa chạy |
| Kiểm kê môi trường | Đã kiểm tra trước và sau reboot | Ubuntu 24.04.5/WSL2 nhận RTX 3060; Python ML/OCR 3.11.14, driver 617.42 giữ nguyên; không có Docker |
| ReceiptVQA: annotations và ảnh | Đã full decode/CRC toàn 9.500 ảnh và xuất inventory | Raw/pixel hashes, EXIF/RGB, 7 aliases; 9.465 exact groups, 15 nhóm xuyên split |
| ReceiptVQA: quyền sử dụng | Đã xác minh tuyên bố nguồn; chưa hoàn tất kiểm tra từng mục đích | README tác giả ghi research-only, CC BY-NC-SA 4.0; ZIP annotations không có README/LICENSE; external processing/PII còn mở |
| Môi trường WSL | Đã hoạt động, không cần reboot tiếp | WSL 3.0.3, kernel 6.18.54.1-1; 12 GB RAM/8 CPUs/4 GB swap; hai venv chính và hai venv dựng lại |
| Khảo sát Phase 0 | Hoàn tất scoping review 12 công trình | Search log/matrix trong LITERATURE.md; đã cập nhật định vị trước prior art DocVAL; chưa tái lập các paper |
| Access register / dự toán | Đã lập | DATA_ACCESS_REGISTER.md phân biệt quyền theo mục đích; PHASE0_BUDGET.md ghi công thức/kịch bản và API cap = 0 |
| Audit có thể chạy lại | Đã triển khai và chạy trên ZIP thật | Module `vidoclens.data.audit_receiptvqa`; report `data/manifests/receiptvqa_annotations_recheck.json` pass, khớp số/hash lần trước |
| CSV loader và gold boundary | Đã triển khai | `ReceiptQuestion` không có trường gold; manifest cấp gold theo receipt/group; đã load train/dev thật; test bị khóa |
| Metric CPU | Strict + compatible, bootstrap và R1 | 260 parity fixtures; 686 QA train diagnostic, không phải student/test accuracy |
| Contracts/schema | 27 schemas hiện hành | OOD source/QA, input không reference, output và adjudication; AI không được thành human gold |
| Phase 1 split/dedup | Frozen containment v1 | 19.496 constraints, 4.527 train_fit/2.873 quarantine; semantic review chưa đầy đủ |
| Git local | Đã khởi tạo nhánh `main` | Chưa có commit/remote; dữ liệu/cache/venv được kiểm tra Git ignore |
| OCR và mô hình local | OCR Phase 1 100/100; 38 dòng có AI reference và local second pass | CER AI 11,9565% trên selected lines, human CER chưa có; baseline có lỗi dấu/merge/missed lines/ảnh xoay |
| OOD khởi đầu | **3 ảnh nguồn Commons / 24 QA**, có rights và cross-source audit | 18 answerable + 6 unanswerable; 24/24 second AI review, adjudication; không dùng train/final benchmark |
| Phase 1 gate | **Đạt — `g1_ai_review_v1`** | `artifacts/phase1/g1_ai_gate_v2.json`; scope SOT §7.5/ADR-021 |
| Teacher và chi phí API | Chưa chạy | Có candidate local 4B dự phòng; chưa chọn API snapshot, chưa có usage pilot hoặc budget trả phí được duyệt |
| Huấn luyện / benchmark | Chưa model training/final benchmark | Có R1 training diagnostic; chưa student accuracy hoặc kết quả H1–H4 |
| API inference thực | Chưa triển khai | Scaffold không được trả đáp án giả hoặc báo model sẵn sàng |
| Deployment GPU | Chưa thực hiện | Có offline GPU smoke; chưa có release bundle/container/API model backend |

## Bằng chứng bàn giao foundation

Đây là kết quả lịch sử khi dựng foundation; sau đó đạt 35 tests khi bổ sung audit và 114 tests khi bổ sung loader/metrics.

- `python -m pytest -q`: **24 passed**.
- `python -m ruff check .` và `python -m ruff format --check .`: **pass**.
- `python -m vidoclens doctor`: chạy được; `inference_ready=false`; chưa cài Torch/Transformers/PaddleOCR/Gradio vào venv kiểm tra.
- 9 cấu hình YAML và 6 JSON Schema đã đọc hợp lệ; JSON Schema được tái xuất sau khi sửa contracts.
- API health/input validation được kiểm tra bằng TestClient; Docker CLI không có trên máy nên chưa chạy container. Workflow CI đã tạo, chưa chạy trên GitHub.
- Lượt dựng foundation trước đó không tải dữ liệu/trọng số, không gọi API trả phí, không train, không gửi email hoặc public dịch vụ. Lượt hiện tại đã tải riêng annotations theo yêu cầu; chưa tải ảnh/weights.

## Audit Phase 0 — môi trường máy

Đo trực tiếp trong khoảng **16:22–16:25, ngày 02/11/2026 (UTC+07:00)**. RAM/VRAM trống và GPU utilization chỉ là snapshot, thay đổi theo ứng dụng đang chạy. Chưa thực hiện inference hoặc training để đo tài nguyên của ViDocLens.

| Hạng mục | Kết quả thực tế | Bằng chứng / ý nghĩa |
|---|---|---|
| Hệ điều hành | Windows 11 Pro, 64-bit, `10.0.26300` | `Get-CimInstance Win32_OperatingSystem` |
| CPU | Intel Core i5-14400F; 10 cores, 16 logical processors | `Get-CimInstance Win32_Processor` |
| RAM | 31,76 GiB tổng; khoảng 16,82 GiB còn trống lúc đo | CIM ComputerSystem/OperatingSystem; không phải RAM đã dành riêng cho ML |
| Ổ đĩa | C: NTFS; 464,65 GiB tổng; 284,19 GiB trống | `Win32_LogicalDisk`, ổ local được phát hiện trong lượt kiểm tra |
| GPU | NVIDIA GeForce RTX 3060, 12.288 MiB VRAM, compute capability 8.6 | `nvidia-smi --query-gpu=... --format=csv`; khớp cấu hình đầu vào |
| VRAM khả dụng | 1.548 MiB đang dùng; 10.566 MiB free tại snapshot | GPU đang phục vụ desktop/WDDM; không coi toàn bộ 12 GB là trống |
| Driver | NVIDIA 617.42; NVIDIA-SMI báo CUDA UMD 13.4 | Đây là thông tin driver, không chứng minh toolkit/PyTorch CUDA đã cài hoặc tương thích |
| CUDA toolkit | Không có `nvcc` trên PATH; không thấy thư mục CUDA ở đường dẫn cài đặt thông dụng | Chưa kiểm kê mọi vị trí tùy chỉnh; không cần đổi driver cho audit này |
| Virtualization | `HypervisorPresent=true` | Có hypervisor; chưa chứng minh WSL GPU passthrough hoạt động |
| WSL/Linux | `wsl --status` trả exit code 50: WSL chưa được cài | Có `wsl.exe` nhưng `--version`, `--status`, `--list --verbose` đều báo chưa cài; chưa có môi trường Linux được xác minh |
| Docker | Không có CLI trên PATH; không thấy Docker Desktop tại đường dẫn thông dụng hoặc các service Docker đã kiểm tra | Chưa có Docker runtime khả dụng được xác minh; chưa chạy container |
| Python mặc định và `.venv` | Python 3.14.9; Python mặc định thuộc Miniconda | `python --version`, interpreter của `.venv` |
| Python bổ sung | Python 3.12.10 qua Windows launcher | `py -0p`, `py -3.12 --version`; chưa kiểm kê mọi Conda env, chưa có Python 3.11 cho ML được xác minh |
| Công cụ | Conda 26.9.4; Git 2.56.0.windows.2; không có `uv` trên PATH | Chỉ kiểm kê, không cài hay nâng cấp |
| Git của dự án tại lúc inventory | Chưa được khởi tạo thành Git repository | Lúc 16:22–16:25 `git rev-parse` trả exit 128; lượt bổ sung sau đó đã `git init --initial-branch=main`, chưa commit |

**Các package trong `.venv` dự án:** Pydantic 2.14.2, FastAPI 0.162.0, Pillow 12.3.0, pytest 9.2.0, Ruff 0.17.3. Không tìm thấy distributions Torch, Transformers, PEFT, Accelerate, bitsandbytes, PaddleOCR, PaddlePaddle và Gradio trong venv này. Kết luận này không áp dụng cho mọi môi trường Python khác trên máy.

Trong lượt kiểm kê 16:22–16:25 đã chạy lại `python -m vidoclens doctor`: `inference_ready=false`, `reason=model_not_configured`, `docker_cli_found=false`, `nvidia_smi_found=true`. Khi đó chỉ thay tài liệu nên không chạy lại bộ 24 tests foundation. Lượt bổ sung công cụ audit sau đó đã chạy 35 tests, ghi ở mục bên dưới.

**Kết luận môi trường:** phần cứng dự kiến đã được xác nhận. Môi trường ML Linux/WSL2, Python 3.11 theo SOT và GPU framework vẫn chưa được thiết lập/kiểm chứng. Chưa thể kết luận student QLoRA vừa VRAM hoặc OCR hoạt động.

## Audit Phase 0 — truy cập ReceiptVQA lúc 16:22–16:25

### Nguồn và điều kiện công bố

Đã mở [repository tác giả](https://github.com/phong-lt/LiGT_VQA), đối chiếu [README tại commit cố định](https://github.com/phong-lt/LiGT_VQA/blob/5b4376b455ed82e16b2285fca5d8b4b25ee3a3af/README.md) và kiểm tra HTTP trực tiếp từ máy local, không đăng nhập Google và không dùng cookie/credential cá nhân.

- Commit `main` quan sát được: `5b4376b455ed82e16b2285fca5d8b4b25ee3a3af`, ngày commit `2025-04-05T15:06:26Z`.
- README cố định trả HTTP 200, 2.810 bytes; SHA-256: `8d2150531e24c6d797d52cb39bb59c5c41e566fa7144ddfc9370119e6b6b7fc6`.
- Tác giả công bố mục đích nghiên cứu và giấy phép **CC BY-NC-SA 4.0**. Đây là tuyên bố nguồn đã kiểm tra, không phải kết quả đọc license bên trong archive.
- Đã đọc [license deed](https://creativecommons.org/licenses/by-nc-sa/4.0/) và [legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en): có điều kiện ghi công, phi thương mại và ShareAlike khi chia sẻ bản phái sinh; giấy phép không tự cấp mọi quyền về privacy/publicity.

Chưa xác nhận quyền xử lý ảnh qua API bên thứ ba cho workflow cụ thể, tình trạng PII, điều khoản riêng trong archive hoặc điều kiện phát hành adapter. Chưa chuyển các cờ quyền dữ liệu thành `approved` trong pipeline. Việc nghiên cứu local, truyền ảnh ra ngoài, công bố dữ liệu và sử dụng thương mại phải được phân biệt; chưa đưa ra kết luận rằng mọi mục đích đều được phép hoặc đều bị cấm.

### Truy cập và file quan sát được

[Thư mục Google Drive chính thức](https://drive.google.com/drive/folders/1mWTKRWm0FDmw1I200ixIjFzg3ij7wcy-) trả HTTP 200 và hiển thị danh sách khi truy cập ẩn danh từ máy này. Web reader chỉ hiển thị trang Drive tối giản, vì vậy đã kiểm tra thêm HTML công khai bằng HTTP local. Kích thước trong bảng là **giá trị giao diện Drive hiển thị**, không phải số byte đã tải/kiểm kê.

| Mục | Kích thước hiển thị | Kiểm tra tải trực tiếp | Kết luận |
|---|---|---|---|
| [ReceiptVQA_annotations.zip](https://drive.google.com/file/d/1-LJyQ27HNmfCCuE1AAnwF2WYm84VlWPS/view) | 1,4 MB | HEAD HTTP 200, `application/octet-stream`, `Content-Length: 1516419`, attachment đúng tên file | Download endpoint khả dụng tại lúc kiểm tra; chưa đọc body ZIP |
| [raw_images.zip](https://drive.google.com/file/d/1-29bUveglWuLCeh_sETwtU5bDXOfCGQ8/view) | 15,59 GB | HEAD HTTP 200 nhưng là HTML; GET giới hạn chỉ đọc trang xác nhận file lớn | Google Drive báo không quét virus được vì file lớn; chưa xác nhận/tải archive |
| [rotated_images.zip](https://drive.google.com/file/d/1neyVdo9Lp1yTvLjqm1dG8oiszy-eE27M/view) | 3,79 GB | HEAD HTTP 200 nhưng là HTML; GET giới hạn chỉ đọc trang xác nhận file lớn | Cùng trạng thái như raw_images; chưa xác nhận/tải archive |
| [features/](https://drive.google.com/drive/folders/1uw7v_tVAaszkDSvt5MdtpgWAImoy4Tq1) | Không hiển thị kích thước | Thấy trong listing gốc; chưa mở nội dung | Không kết luận về số file hoặc quyền tải bên trong |

GET của hai archive ảnh chỉ đọc HTML xác nhận tương ứng 2.461 và 2.466 bytes; không đọc bytes ảnh/ZIP. Các HTTP 200 này **không chứng minh tải toàn bộ archive thành công**. Chưa gặp trang yêu cầu đăng nhập/cấp quyền ở các bước đã kiểm tra; chưa kiểm tra quota hoặc tính toàn vẹn tải xuống.

**Kết luận tại thời điểm 16:25:** link tải được xác minh đến listing và bước download/confirmation; chưa cần mặc định gửi email xin quyền truy cập kỹ thuật. Khi đó `data/raw/` chỉ có `.gitkeep`. Lượt tải/audit annotations được thực hiện sau đó và ghi ở mục kế tiếp; chưa tải ảnh hoặc thực hiện dedup ảnh.

### Phạm vi thực hiện

Lượt kiểm kê 16:22–16:25 chỉ chạy chẩn đoán local và HTTP đọc metadata/trang công khai. Không thay cấu hình hệ thống, cài WSL/Docker/CUDA, tải dataset/weights, gọi API trả phí, gửi email hoặc khởi tạo Git trong lượt đó.

## Audit Phase 0 — archive annotations đã tải

Được người dùng yêu cầu tải/kiểm tra riêng annotations. Tải xong lúc **16:37:58**, hoàn tất thống kê lúc **16:38:44 ngày 02/11/2026, UTC+07:00**. Archive và manifests chỉ nằm local trong các thư mục payload đã được `.gitignore` loại trừ.

| Kiểm tra | Kết quả |
|---|---|
| Archive | [ReceiptVQA_annotations.zip](../data/raw/receiptvqa/ReceiptVQA_annotations.zip), tải ẩn danh từ link chính thức |
| Kích thước | 1.516.419 bytes nén; 6.891.879 bytes nội dung chưa nén |
| SHA-256 | `226f7dcc6421115da254b2809dc9ebfd138be0c2f175a9c1c12f7a46ae6127ea` |
| ZIP integrity | `ZipFile.testzip()` pass cho toàn bộ members; không phát hiện đường dẫn thoát thư mục/symlink |
| Thành phần | Một entry thư mục và ba CSV train/dev/test; không có ảnh hoặc file thực thi |
| Điều khoản kèm ZIP | Không có README/LICENSE hoặc tài liệu ngoài ba CSV; quyền vẫn tham chiếu nguồn tác giả đã kiểm tra |
| Định dạng | CSV UTF-8 không BOM, phân tách dấu phẩy; parser CSV xử lý quoted newlines |
| Giải nén | Đọc CSV trực tiếp trong bộ nhớ; không extract ra filesystem, không sửa archive |
| Provenance | [Download manifest](../data/manifests/receiptvqa_annotations_download.json), [audit manifest](../data/manifests/receiptvqa_annotations_audit.json); có hash từng CSV |

CRC và SHA-256 ghi nhận tính toàn vẹn/provenance của bản tải; tác giả chưa cung cấp checksum đối chiếu trong các nguồn đã đọc, nên đây không phải xác thực bằng checksum độc lập từ tác giả.

### Số lượng thực trong archive

| Split | QA rows | Unique image_id | Unique filename | Unique question_id |
|---|---:|---:|---:|---:|
| Train | 51.886 | 7.600 | 7.600 | 23 |
| Dev | 6.426 | 950 | 950 | 26 |
| Test | 6.500 | 950 | 950 | 21 |
| Tổng QA / hợp ID ảnh và tên file | **64.812** | **9.500** | **9.500** | Không cộng vì question_id được tái sử dụng |

Đây là **số ảnh được annotation tham chiếu**, không phải số ảnh đã tải hoặc giải mã. Tổng QA khớp mô tả chính của bài gốc; không dùng con số 68.412 ở bảng bất nhất của bài để sửa dữ liệu.

### Kết quả kiểm tra schema và IDs

- Header chính xác: cột đầu **không tên**, `image_id`, `question_id`, `filename`, `question`, `answer`.
- Cột không tên là số thứ tự `0..N-1`, khởi động lại ở từng split; không dùng làm qid toàn cục.
- `question_id` được lặp giữa các ảnh. Cặp `(image_id, question_id)` duy nhất trong từng split; `image_id` không giao nhau giữa split. Loader tương lai dùng ID có namespace dataset/version + cặp này, giữ IDs nguồn để truy vết.
- Không có ô rỗng/chỉ whitespace trong sáu cột, không có dòng thừa field; các ID số parse được. Mapping `image_id ↔ filename` là 1–1 ở mức annotation đã kiểm tra.
- Không có giao nhau `image_id` hoặc `filename` giữa train/dev/test. Chưa có bytes ảnh nên **chưa thể kết luận hết rò rỉ/ảnh trùng**, đặc biệt crop/resize và trùng MC-OCR.
- CSV không cung cấp bbox/evidence, question type hoặc answer type. Các trường này chưa được coi là có gold sẵn.
- Chỉ kiểm tra cấu trúc văn bản trên **train**: 879 đáp án chứa newline; không có literal `¡sep¿`; question/answer train đều NFC theo kiểm tra. Không suy ra mọi newline là một đáp án nhiều phần hoặc tự thay newline bằng separator.
- Dev/test chỉ được xử lý tự động để kiểm tra schema, số lượng, ID và sự hiện diện nhãn; không in nội dung QA, không phân tích lỗi model hoặc dùng để chọn prompt/ngưỡng. Archive chứa test answers phải tiếp tục tách khỏi teacher/student inputs.

Đã kiểm tra code nguồn tác giả ở commit đã ghi: loader dùng answer string; tìm literal `¡sep¿`/thao tác thay newline trong 47 file Python không thấy kết quả. Đây chưa phải xác nhận evaluator parity hay chứng minh không có preprocessing ngoài repository. SOT/ADR được bổ sung lưu ý định dạng thực để giữ raw CSV và để gate normalization/evaluator mở.

### Phần đã hoàn thành và phần còn thiếu

**Hoàn thành:** truy cập và tải annotations, provenance, CRC, thống kê split/ID/schema, xác định archive không kèm tài liệu điều khoản.

**Còn thiếu:** tải ảnh và kiểm tra khớp filename, decode/chất lượng/redaction, khử trùng theo nội dung xuyên nguồn, xác minh normalization với scorer, kiểm tra từng quyền sử dụng ngoài local research. Vì vậy Phase 0 chưa đạt toàn bộ G0; chưa đánh dấu gold image–QA corpus đã sẵn sàng.

## Phương án môi trường đã chuẩn bị — chưa cài

Xem [ENVIRONMENT_SETUP_PLAN.md](ENVIRONMENT_SETUP_PLAN.md). Phương án gồm WSL2 + Ubuntu 24.04 LTS, Python 3.11, venv VLM và OCR CPU riêng, tài nguyên WSL đề xuất 12 GB RAM/8 logical CPUs/4 GB swap, bộ package ứng viên có version, các bước smoke và phục hồi. Mức tài nguyên là đề xuất, chưa áp dụng.

Đã kiểm tra metadata package và tài liệu chính thức để lập kế hoạch; **chưa cài package, chưa resolve lock, chưa thử GPU compatibility**. Có gate riêng xác minh tiếng Việt ở phiên bản OCR dự kiến. Driver Windows, WSL, Python hiện tại, PATH, registry, firewall và cấu hình hệ thống không bị sửa. Không tạo `.wslconfig`, không chạy apt/pip install/WSL install hoặc reboot.

## Bổ sung Phase 0 — hoàn tất phần không cần cài/tải ảnh

1. **Khảo sát:** [LITERATURE](LITERATURE.md) có 12 công trình, query log, tiêu chí nhận/loại, phần đã đọc và giới hạn. DocVAL đã có validated distillation; SOT v1.1/ADR-013 điều chỉnh định vị đóng góp, giữ RQ1–RQ4 và hidden-gold boundary.
2. **Quyền và nhánh thay thế:** [DATA_ACCESS_REGISTER](DATA_ACCESS_REGISTER.md) tách benchmark/train-label/external/release; có phương án gold dự phòng và candidate teacher local Qwen3-VL-4B-Instruct (ADR-014), chưa tải hoặc thử. Model cards 2B/4B đã lưu theo revision vào cache local cùng hashes; không có model weights. MIT là đề xuất code license, chưa áp dụng/public.
3. **Dự toán:** [PHASE0_BUDGET](PHASE0_BUDGET.md) có công thức API/compute, scenario giả định và khoản chưa đo; không dùng giá giả định như giá dịch vụ. API vẫn disabled, budget 0.
4. **Protocol:** [PHASE0_PILOT_PROTOCOL](PHASE0_PILOT_PROTOCOL.md) quy định mẫu train, quarantine pilot khỏi audit holdout, GPU/OCR measurements và điều kiện đạt; chưa thực thi. Full OCR 100 ảnh/evaluator ở G1, full train ở các phase sau.
5. **Công cụ audit:** [audit_receiptvqa.py](../src/vidoclens/data/audit_receiptvqa.py) chỉ đọc ZIP, CRC/hash, schema/counts/ID/mapping/cross-split checks; kiểm tra newline/NFC riêng train. Output không có question/answer hoặc IDs từng receipt; không extract/download/normalize và không ghi đè archive/report cũ. Lệnh trong [scripts README](../scripts/README.md).
6. **Tái kiểm tra thật:** [recheck manifest](../data/manifests/receiptvqa_annotations_recheck.json) có `status=pass`, tổng 64.812 QA, 9.500 ID ảnh; SHA-256 archive và ba CSV khớp bản audit trước. Không phát hiện overlap image_id/filename; đây vẫn chưa phải image dedup.
7. **Môi trường core và Git:** lưu inventory 34 distributions/Python 3.14.9 tại [core inventory](../artifacts/phase0/core_environment_inventory.json), không gọi là lock. Khởi tạo Git local `main`; chưa commit, chưa remote. `git check-ignore` xác nhận annotation ZIP, manifests, cache metadata, artifacts và venv bị ignore; marker/README thư mục vẫn có thể version-control.

**Kiểm tra lịch sử sau bổ sung Phase 0, trước lượt loader/metrics:**

| Lệnh trong `.venv` Windows | Kết quả |
|---|---|
| `python -m pytest -q` | **35 passed**, một warning Starlette/httpx; 11 tests audit gồm gold không bị xuất, giữ nguyên ZIP, reused qid hợp lệ, duplicate/overlap/missing/malformed/mapping lỗi, member path lạ và chống ghi đè report |
| `python -m ruff check .` | Pass |
| `python -m ruff format --check .` | Pass, 53 files đã đúng format |
| `python -m pip check` | Không có broken requirements trong core venv |
| `python -m vidoclens doctor` | `inference_ready=false`, `model_not_configured`; Torch/Transformers/PaddleOCR/Gradio chưa có |

Đã kiểm tra 30 file Markdown: UTF-8 hợp lệ, code fences cân bằng, không có liên kết local bị thiếu. So sánh hai manifests xác nhận hash/split counts khớp; checksum `PROJECT_OVERVIEW.md` không đổi. Danh sách Git candidates không có payload data/cache/artifacts hoặc `.env`/venv; chưa có file tracked/commit/remote.

Không cài package/hệ điều hành, đổi driver/PATH/registry/firewall, tải ảnh/weights, gọi API trả phí, gửi email, push/public hosting hoặc chạy GPU trong lượt bổ sung này. Chỉ đọc nguồn công khai, sửa repo, chạy CPU tests/audit và khởi tạo `.git` local. `PROJECT_OVERVIEW.md` giữ nguyên.

## Triển khai CSV loader và EM/F1/ANLS — 17:20 ngày 02/11/2026

Thực hiện theo yêu cầu mới: xây loader/metric trên Windows, giữ nguyên hệ thống và chưa tải ảnh/weights. Tài liệu sử dụng và định nghĩa protocol: [ANNOTATION_LOADER_AND_METRICS](ANNOTATION_LOADER_AND_METRICS.md). SOT v1.2 và ADR-015/016 đã cập nhật cùng contracts.

### Thành phần đã triển khai

- [CSV loader](../src/vidoclens/data/receiptvqa.py): đọc CSV từ ZIP hiện có, không extract; kiểm tra schema/IDs/CRC, namespace theo archive hash; giữ raw và NFC question riêng, raw answer không đổi newline/delimiter.
- `load_questions` chỉ trả `ReceiptQuestion` không có trường gold. `load_silver_questions` chỉ lấy `train_fit` ngoài gold groups; `load_training_examples` chỉ lấy gold groups trong `train_fit` được chọn bằng `ReceiptAccessPlan`.
- Manifest phải khớp archive hash, phủ đúng toàn bộ selected split, không chia một receipt/duplicate group sang nhiều policy. Plan được revalidate ở boundary; test/dev/audit không thể gán gold training.
- [Gold evaluator access](../src/vidoclens/eval/receiptvqa_gold.py) tách khỏi loader câu hỏi; chỉ mở `audit_holdout`/`dev_select`/`dev_calibrate`. Test/OOD bị chặn trước khi đọc archive, chưa có override mở test.
- [Metric implementation](../src/vidoclens/eval/metrics.py): NFC EM, Counter token F1, Levenshtein ANLS với `d < 0.5`, max trên full alternatives; giữ multipart raw. Aggregate join theo qid, reject unknown/duplicate, missing/abstain/error vẫn trong mẫu số; zero coverage → selective EM null.
- Bảy schema mới (question/access plan/gold/supervised example/prediction/scores/summary), tổng **13 schema**. `EvaluationSummary` kiểm tra count/coverage/denominator nhất quán và luôn ghi `official_compatible=false`.

### Kiểm chứng trên archive thật và tests

Lúc **17:20:14 (UTC+07:00)** đã chạy loader train/dev, kiểm tra output fields của mọi record và IDs duy nhất. [Loader verification](../artifacts/phase1_annotations/loader_verification.json) chứa metadata tổng hợp; không có QA text, gold dump hoặc prediction giả.

| Split | QA đọc thành công | Receipt IDs | Qid duy nhất | Gold fields trong question output |
|---|---:|---:|---:|---|
| Train | 51.886 | 7.600 | 51.886 | Không |
| Dev | 6.426 | 950 | 6.426 | Không |
| Test | Không đọc qua loader | Không áp dụng | Không áp dụng | API bị chặn |

Hash archive giữ nguyên `226f7dcc6421115da254b2809dc9ebfd138be0c2f175a9c1c12f7a46ae6127ea`; checksum overview không đổi. Các gold training/evaluation views được kiểm tra bằng **fixtures synthetic**, chưa sinh partition manifest trên dataset thật hoặc chọn gold budget khi chưa image dedup.

| Kiểm tra local mới nhất | Kết quả |
|---|---|
| `python -m pytest -q` | **114 passed**, 1 warning Starlette/httpx; không gọi API/model |
| `python -m ruff check .` | Pass |
| `python -m ruff format --check .` | Pass, 61 files |
| `python -m pip check` | Không có broken requirements trong core venv |
| Export và so sánh JSON schema với Pydantic | **13/13 khớp** |
| `python -m vidoclens doctor` | `inference_ready=false`; Torch/Transformers/PaddleOCR/Gradio chưa có |

Đã đọc bốn file scorer upstream tại commit cố định: Accuracy/F1 mean references; F1 dùng set-token overlap; ANLS gọi package ngoài. Các khác biệt với multiset/max-reference `strict_nfc_v1` đã ghi trong protocol/ADR. **Chưa chạy scorer tác giả hoặc xác nhận official parity**, chưa cài dependency của scorer, chưa chấm prediction thật.

Gold protection là boundary API/serialization, không phải ACL: raw ZIP vẫn chứa answers; người có quyền filesystem có thể đọc nó. Không coi manifest `receipt_only` là chứng nhận image dedup. Tại mốc kiểm tra CPU 17:20, chưa chạy train/OCR/GPU, tải ảnh/weights, cài package/WSL, sửa hệ thống, gửi dữ liệu ra API hay triển khai public. Kết quả cài/tải sau đó được ghi ở mục tiếp theo.

## Triển khai WSL và artifacts Phase 0 — 21:00–21:07 ngày 02/11/2026

Đã thực thi sau khi chủ dự án cho phép cài/tải. Token shell ban đầu không elevated; gọi WSL installer qua Windows RunAs, installer kết thúc exit 0. Không thay driver hoặc tự reboot.

### Môi trường cần khởi động lại

- WSL hiện báo **3.0.3.0**, kernel **6.18.54.1-1**, default version 2.
- CIM: `VirtualMachinePlatform.InstallState=1`, `HypervisorPresent=true`; Windows xuất hiện `RebootPending` sau cài (trước cài false).
- Lệnh `wsl --install -d Ubuntu-24.04 --no-launch` trả exit 0 với thông báo thay đổi chỉ có hiệu lực sau reboot. `wsl --list --verbose` vẫn chưa có distribution; không gọi Ubuntu đã cài xong.
- Đã tạo mới `C:\Users\Admin\.wslconfig` (trước đó chưa có), giới hạn WSL2 memory 12 GB, processors 8, swap 4 GB theo phương án. Chưa chạy VM để đo hiệu lực.
- Driver vẫn NVIDIA 617.42. Chưa cài framework/Linux Python hoặc OCR; không có environment lock đã smoke.
- Bằng chứng: [WSL inventory](../artifacts/phase0/wsl_pre_reboot_state.json), [Ubuntu install attempt](../artifacts/phase0/wsl_ubuntu_install_attempt.json).

### Ảnh và pilot local

Đã tải [rotated_images.zip](../data/raw/receiptvqa/rotated_images.zip) từ Drive tác giả, **4.071.333.203 bytes**, SHA-256 `731bc35c3525c6a067363aa77ccf49189932773976148adea9994ad8e2861a5e`. Không tải raw_images.zip. Dùng rotated archive cho pilot kỹ thuật; chưa xác nhận parity với preprocessing benchmark gốc (ADR-017).

- 9.500 ảnh đã đọc, CRC và `Pillow.verify()` pass. 9.493 filenames khớp trực tiếp; 7 annotations `.png/.jpeg` khớp stem duy nhất với `.jpg` trong archive. Mapping được ghi, không sửa CSV hoặc đoán theo thứ tự.
- **9.465 SHA-256 ảnh duy nhất; 15 nhóm trùng bytes xuyên split.** Theo policy SOT, có **19 ảnh train cần quarantine** trước lập train/silver manifest. Không có ảnh dev trùng test theo byte-hash lần này. Chưa kiểm tra pixel/near duplicate hoặc nguồn ngoài, chưa tuyên bố G1 đạt.
- Chọn **20 nhóm chỉ thuộc official train**, seed 42 trên danh sách hash đã sắp xếp, loại nhóm chạm dev/test. Lưu 20 ảnh vào `data/processed/receiptvqa/phase0_pilot/`, đã decode đầy đủ; input pilot có image/question, không có gold answers. Quarantine các nhóm này khỏi audit holdout tương lai. Mẫu chưa được phân tầng độ khó/kiểm tra OCR trực quan.
- Manifests local: [download](../data/manifests/receiptvqa_rotated_download.json), [image audit](../data/manifests/receiptvqa_rotated_image_audit.json), [image mapping/hash](../data/manifests/receiptvqa_rotated_image_manifest.json), [duplicate groups](../data/manifests/receiptvqa_exact_duplicate_groups.json), [pilot](../data/manifests/receiptvqa_phase0_pilot.json). Không commit ảnh/QA payload.

### Student weights

Đã tải **11 files, 4.266.647.442 bytes** cho `Qwen/Qwen3-VL-2B-Instruct` tại revision `89644892e4d85e24eaac8bacfd4f463576704203`, gồm weights/processor/tokenizer/config/README. File `model.safetensors` 4.255.140.312 bytes có SHA-256 **khớp LFS upstream**: `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`.

[Model download manifest](../artifacts/models/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203/download_manifest.json) lưu size/hash từng file. Chưa nạp model, chưa có VRAM/latency hoặc đáp án model; chưa tải teacher 4B/OCR weights. Các kết quả 114 tests/13 schemas ở trên là lượt CPU trước đó; lượt này kiểm tra artifacts thật và tài liệu, không tuyên bố đã chạy GPU/CI.

## Hoàn tất Phase 0 sau reboot — 02/11/2026, kiểm chứng lúc 21:33

### Nền Linux và môi trường thật

Chủ dự án đã reboot Windows. `wsl --install -d Ubuntu-24.04 --no-launch` hoàn tất; Ubuntu 24.04.5 chạy dưới WSL2 và nhận GPU. Đã tạo user thường `vidoclens` (UID 1000, password login locked, không sudo group), đặt làm default WSL user. Distro administration dùng `-u root`; inference dùng user thường. Không đổi driver, PATH Windows, Python Windows hoặc cài Linux NVIDIA driver.

Python 3.11.14 managed build 20251028 qua uv 0.9.6; hai venv `/home/vidoclens/.venvs/vidoclens-ml` và `vidoclens-ocr`. Cài `python3-venv`, `ca-certificates` trong distro. Paddle import ban đầu thiếu `libgomp.so.1`; cài đúng `libgomp1` rồi import/inference pass. Warning thiếu ccache không chặn inference. Không cần CUDA toolkit/Docker. Ổ C còn **275.114.172.416 bytes (~256,21 GiB)** ở lượt kiểm tra 21:33.

Nguồn version, hashes, cấu hình và lệnh thực tế trong [runbook](PHASE0_ENVIRONMENT.md), [inventory sau reboot](../artifacts/phase0/environment_post_reboot.json). Student dùng lại weights đã tải; OCR mới tải 10 files tổng **96.570.324 bytes**, hai revision cố định, weights hash khớp LFS upstream; model cards khai báo Apache-2.0. Không tải teacher 4B.

### Kết quả pilot và giới hạn

Hai lượt đầu: `student_nf4_01` và `ocr_cpu_01`. Sau dựng lại, chạy **tuần tự** `student_nf4_repro_02` rồi `ocr_cpu_repro_02`. Bảng dưới lấy lượt dựng lại, mỗi engine một warm-up riêng bị loại khỏi latency; mỗi mẫu một ảnh/câu hỏi, concurrency 1.

| Bằng chứng | Student GPU | OCR CPU |
|---|---|---|
| Kết quả thực | **20/20 generation có nội dung, không OOM** | **20/20 có text/box/confidence; 1.004 spans** |
| Runtime | 300 Linear4bit NF4 + double quant, BF16, SDPA; toàn bộ 625 parameter tensors ở CUDA | Paddle/PaddleOCR/PaddleX 3.2.0; CPU 4 threads; MKLDNN off |
| Profile | Pixel area ≤262.144; output cap 128; seed 42, greedy | Detector PP-OCRv5_server_det, recognizer latin_PP-OCRv5_mobile_rec; `vi` mapping kiểm chứng; max side 960 |
| Latency warm p50 / p95 | Generation **4,407 / 6,319 s**; tổng **4,478 / 6,366 s** | Tổng **7,283 / 8,529 s** |
| Model load | 26,720 s, không gồm import/hash và CUDA probe trước load | 0,720 s, không gồm import/hash trước load |
| Memory | Peak allocated **1.668.071.936 bytes (~1,55 GiB)**; peak reserved **2.311.061.504 (~2,15 GiB)** | Peak RSS quan sát tại các mốc mẫu **1.162.506.240 bytes (~1,08 GiB)** |
| Lỗi/giới hạn | **7/20 outputs chạm 128 tokens**; không coi đầu ra cắt là đáp án đầy đủ | Mất dấu/ký tự tiếng Việt, tách một dòng thành nhiều spans; chưa đánh giá CER |

Đây là số đo feasibility trên host dùng GPU chung với Windows; CUDA peak là của PyTorch, không phải peak VRAM toàn máy. OCR RSS là snapshot sau từng mẫu, không phải bộ đo peak liên tục. Model load được đo trong process mới, không xóa OS filesystem cache. Không có EM/F1/ANLS/CER, quality threshold, train backward/loss-mask/save-resume hoặc kết quả teacher.

Đã xem contact sheet 20 ảnh: có hóa đơn dài, chữ nhỏ/mờ, nghiêng/phối cảnh, giấy nhăn và dấu tiếng Việt. Không thay danh sách theo model output. Review chi tiết text/box trên hai ảnh train ghi ở [visual review](../artifacts/phase0/ocr_visual_review.json): tiêu đề mất dấu/ký tự, số tiền trong các box được xem có trường hợp giữ đúng. Đây là review định tính, không phải OCR gold hoặc certification toàn corpus. Raw OCR/predictions không sửa; summary OCR tự động vẫn ghi `visual_review_complete=false`, bằng chứng review được lưu riêng có phạm vi cụ thể.

Artifact chính: [student summary](../artifacts/phase0/student_nf4_repro_02/student_smoke.json), [student profile](../artifacts/phase0/student_nf4_repro_02/profile.json), [OCR summary](../artifacts/phase0/ocr_cpu_repro_02/ocr_smoke.json), [OCR profile](../artifacts/phase0/ocr_cpu_repro_02/profile.json). Per-sample files giữ raw output, dimensions/tokens, latency, memory/error/truncation; các payload chỉ nằm local, bị Git ignore.

### Khóa và dựng lại môi trường

- [ML hash lock](../infra/requirements/phase0-ml-linux-py311.lock): 71 third-party packages; [OCR hash lock](../infra/requirements/phase0-ocr-linux-py311.lock): 91 packages. Local project được cài editable riêng `--no-deps`, không bịa package wheel hash.
- Hai venv mới hậu tố `-repro` được tạo bằng Python 3.11.14, `uv pip sync --require-hashes --only-binary :all:` từ locks; pip check pass và freeze **khớp** môi trường ban đầu.
- Đã chạy lại cả hai pilot 20 ảnh trong venv mới. **20/20 student raw answers/output tokens và 20/20 canonical OCR results khớp chính xác** giữa hai lượt. Lưu source snapshots/hash của runner ở lượt tái lập, không chỉ một path trỏ code có thể đổi.
- [Reproducibility verification](../artifacts/phase0/reproducibility_verification.json) ghi đối chiếu thật. Đây là dựng lại venv trên cùng host/driver/distro, không tuyên bố đã kiểm tra một máy hoặc OS khác.

### Kiểm tra code và giới hạn phạm vi

**130 tests pass** trên Windows Python 3.14.9 và Linux Python 3.11.14. Thêm 16 tests kiểm tra pilot reject gold fields, duplicate IDs/hash, train/dev/test overlap, file tampering, path traversal và ghi đè evidence. Ruff lint/format, pip check và shell syntax pass; **14 schemas** tái xuất từ Pydantic. Còn một warning Starlette/httpx trong suite; chưa chạy GitHub CI.

Đã loại `artifacts/cache/data/reports` khỏi Ruff để không format model cards hoặc evidence đã hash. `.gitignore` chặn cả README upstream trong `artifacts/models/`; code, locks và docs được giữ trong source. `PROJECT_OVERVIEW.md` không đổi. [Kiểm tra cuối](../artifacts/phase0/final_verification.json) xác nhận 14 schemas, YAML, UTF-8/liên kết local và payload ignore. Doctor/API readiness vẫn false vì chưa tích hợp offline model runner vào server; không giả readiness thành công.

## Chuyển tiếp từ Phase 0 sang Phase 1

G0 đã đóng, không cần reboot/cài lại môi trường. Chủ dự án yêu cầu tái kiểm tra rồi bắt đầu Phase 1 ngay; kết quả ingestion/mapping, exact graph/quarantine và draft được ghi ở mục mới bên dưới. Bước còn lại là near review, final split, pilot OCR 100 ảnh, evaluator parity và R1; không coi draft hoặc smoke là G1 hoàn tất.

Teacher local 4B vẫn là nhánh dự phòng có điều kiện theo ADR-014, phải pilot trước sinh silver. API budget vẫn 0, external disabled; không phát sinh API trả phí/hosting. QLoRA train smoke thuộc G3, Docker/API/demo/deploy thuộc các phase sau. Mốc kế hoạch G0 08/11/2026 đã hoàn thành sớm; lịch phase sau chưa tự điều chỉnh hoặc đặt automation.

## Gate Phase 0 — đã đóng

- [x] Đã kiểm kê CPU/GPU/driver/RAM/đĩa và runtime hiện có, ghi giới hạn của kết quả.
- [x] Đã xác minh nguồn ReceiptVQA, điều kiện công bố, listing công khai và bước tải từng archive chính.
- [x] Đã tải/audit annotations và rotated images, lưu SHA-256, mapping và exact duplicates.
- [x] WSL2/Ubuntu/GPU hoạt động; hai môi trường ML/OCR tách biệt, driver giữ nguyên.
- [x] Literature matrix/search log 12 công trình đủ định vị thận trọng Phase 0; không chứng minh novelty hay thay review cuối.
- [x] Phân biệt quyền benchmark, train-label, external, release; ghi nhánh teacher local có điều kiện trong ADR-014.
- [x] Có dự toán và protocol pilot cụ thể; API cap 0, model/price không được chốt bằng suy đoán.
- [x] Audit annotations chạy lại được và có tests; Git local đã init, payload được ignore.
- [x] Có ảnh pilot train khớp QA, nguồn research và mapping/CRC/decode đã kiểm tra; không cấp quyền external/public.
- [x] Student weights/processor/tokenizer và OCR models tải theo revision/hash; 11 student files được đối chiếu lại.
- [x] Candidate student suy luận được trên GPU 12GB; có latency/VRAM/truncation và không CPU fallback.
- [x] OCR tiếng Việt smoke trên ảnh thật, có qualitative review dấu/số/box và ghi lỗi; quality pilot thuộc G1.
- [x] Môi trường ML/OCR smoke, hash locks, dựng lại hai venv mới và chạy lại pilot thành công.

**Kết luận: Phase 0 hoàn tất 100% theo gate G0 của SOT, ngày 02/11/2026.** Kết luận giới hạn ở nền móng/feasibility và môi trường tái lập trên host này; không biến lỗi OCR/truncation thành accuracy đạt, không bỏ near-dedup/quarantine G1 hoặc training/deploy gates về sau.

## Tái kiểm tra G0 và bắt đầu Phase 1 — 02/11/2026

### Audit G0 độc lập

Đã đối chiếu SOT §22/G0, literature/search log, access register, budget, protocol và artifacts; không chỉ đọc checkbox. [Re-audit artifacts](../artifacts/phase0/gate_reaudit_20261102.json) kiểm tra lại SHA-256 **2 archives, 21 model files, 20 ảnh pilot**, manifest train-only, source snapshots, per-sample results và lock hashes. OCR review nằm ở artifact riêng với phạm vi hai ảnh chi tiết/contact sheet 20 ảnh, không coi cờ tự động false là đã có gold OCR.

[Live/runtime và metric audit](../artifacts/phase0/gate_reaudit_live_and_metrics.json) xác nhận Python 3.11.14/Torch 2.8.0+cu126/CUDA 12.6 vẫn chạy finite matmul trên RTX 3060, driver 617.42; **71 ML và 91 OCR third-party packages hiện cài khớp freeze**. Pip check cả hai venv dựng lại pass. Tính lại latency percentiles và memory maxima từ từng sample, khớp summaries. Bộ 130 tests trước thay đổi vẫn pass. Không chạy lại toàn bộ inference chỉ để lặp bằng chứng vừa có.

**Kết luận re-audit: G0 đạt, không có gate Phase 0 còn thiếu.** Training feasibility, chất lượng OCR/student, final evaluator/deploy là gate về sau; 7 outputs bị cắt và lỗi OCR đã được ghi, không suy thành accuracy đạt. Không cần tải thêm hoặc sửa hệ thống để bắt đầu Phase 1.

### Ingestion và dedup đã thực thi

- Chạy `vidoclens.data.ingest_receiptvqa` trên toàn rotated archive trong venv Linux đã khóa, 4 workers/bounded batches; **9.500 ảnh/64.812 QA**, CRC và full decode pass. Tất cả JPEG/RGB, không có EXIF cần xoay; dimensions/aliases trong [data card](data/RECEIPTVQA_ROTATED_V1.md).
- Tính raw SHA-256 và canonical pixel SHA-256 sau EXIF/RGB/bỏ metadata; **9.465 unique hashes cho cả hai**, 7 filename aliases giữ mapping tường minh. Canonical pixels chỉ ở RAM, không giả có processed image files hoặc re-encode raw.
- `vidoclens.data.split_draft` nối **9.465 exact groups**, trong đó 29 nhóm nhiều ảnh và **15 nhóm xuyên official split**. Quarantine trong draft **19 ảnh train/126 QA**; không xóa ảnh/đổi CSV hoặc sửa official test.
- pHash toàn ảnh threshold 6 và crop giữa 80% threshold 4 đã định trước chạy, tạo **19.391 candidate pairs**, **6.959 xuyên official split**. Tất cả pending review, không auto-merge; cùng template có thể tạo false positives. Chưa OCR/feature matching đầy đủ cho crop/rotation hoặc dedup các nguồn chưa nhập.

Artifacts local: [ingestion summary](../data/manifests/receiptvqa_ingestion_v1/summary.json), [inventory](../data/manifests/receiptvqa_ingestion_v1/images.jsonl), [dedup summary](../data/manifests/receiptvqa_dedup_v1/summary.json), [review queue](../data/manifests/receiptvqa_dedup_v1/near_duplicate_candidates.jsonl), [split draft](../data/manifests/receiptvqa_dedup_v1/split_draft.json). Giữ source/runtime/hashes cùng run; không commit dataset/payload.

### Split nháp — không là final training grant

| Partition | Ảnh | QA |
|---|---:|---:|
| train_fit | 6.822 | 46.619 |
| audit_holdout | 759 | 5.141 |
| dev_select | 665 | 4.481 |
| dev_calibrate | 285 | 1.945 |
| test | 950 | 6.500 |
| quarantine (train) | 19 | 126 |

20 pilot-exposed groups không vào audit. Nested draft gold group IDs: G5 **340**, G10 **681**, G25 **1.702**, G100 **6.811**; tỷ lệ theo group, không phải QA. Chưa stratify question type và chưa mở gold. `SplitDraft` có schema riêng, `training_allowed=false`; đã kiểm tra **training loader từ chối actual draft**. [Independent verification](../artifacts/phase1/ingestion_dedup_verification.json) xác nhận đầy đủ/duy nhất 9.500 thành viên, exact group không vượt partition sau quarantine, pilot exclusion và validity toàn review queue.

### Kiểm thử và việc còn lại G1

25 tests mới cho image decode/EXIF/pixel hashes, ZIP safety/bijection, transitive dedup, perceptual candidates, quarantine, nested budgets, draft tampering và label-free ingestion. Linux **155 passed**; Windows **149 passed, 6 skipped** do NumPy optional (6 cases đã chạy ở Linux). Ruff lint/format pass; **18 schemas** tái xuất/đối chiếu. Có một warning Starlette/httpx. CI YAML thêm extra `data` để các tests dữ liệu không bị skip trên CI; **chưa chạy GitHub CI**.

Kiểm thử Windows phát hiện `ZipInfo.filename` có thể chuẩn hóa dấu gạch chéo trước validation; đã sửa để kiểm tra cả `orig_filename`, và kiểm tra lại mọi member thật với validator hiện hành. Data pipeline vẫn chạy CPU; driver, Windows core venv, ML/OCR hash locks và `PROJECT_OVERVIEW.md` giữ nguyên.

- [x] G0 re-audit và chuyển Phase 1 theo yêu cầu chủ dự án.
- [x] Ingestion toàn ReceiptVQA, metadata mapping/decode/CRC/raw+pixel hashes và data card v1.
- [x] Exact graph/quarantine, candidate review queue, split/gold-budget draft với tests.
- [ ] Review near duplicates, bổ sung OCR/feature candidates, xử lý crop/rotation và nguồn mới khi có quyền.
- [ ] Chốt stratification, freeze graph/split và final access plan có quarantine; chưa được dùng draft để train/silver.
- [ ] OCR quality pilot 100 ảnh/cache, transcription subset có review và span recall/CER.
- [ ] Official metric/multipart parity, group bootstrap, R1 oracle và bắt đầu OOD annotation có quyền.

**G1 chưa đạt.** Bước tiếp theo là review ứng viên trùng, ưu tiên xuyên split, rồi freeze split trước các lựa chọn OCR/evaluator có dùng gold. [Workflow và lệnh chạy](PHASE1_WORKFLOW.md) ghi trình tự đầy đủ. Phase 1 bắt đầu sớm theo yêu cầu; chưa tự đổi lịch các phase sau.

## Hoàn thiện pipeline Phase 1 — mốc lịch sử trước ADR-021, 02/11/2026

[Báo cáo thực thi đầy đủ](PHASE1_RESULTS.md), [data card mới](data/RECEIPTVQA_CONTAINMENT_V1.md), [workflow](PHASE1_WORKFLOW.md). Mục này thay hiện trạng split nháp của lượt trước; artifact lịch sử giữ nguyên.

- Full feature pass trên 9.500 ảnh; union **19.496 pairs**, **5.802 containment components**. SOT v1.6/ADR-020 giữ mọi candidate chưa phân xử trong cùng constraint group, không nhận là duplicate đã chứng minh.
- Freeze thành công: **4.527 train_fit / 504 audit / 456 dev_select / 190 dev_calibrate / 950 test / 2.873 quarantine**. Quarantine gồm 2.569 train và 304 dev. G10 **454 ảnh/3.053 QA**; silver **27.774 câu hỏi không nhãn**. Kiểm độc lập toàn corpus: zero uncontained edge, zero component vượt partition sau quarantine; test reader khóa. Split này giảm dữ liệu đáng kể do template false positives.
- OCR **100/100 ảnh G10 train_fit**, **4.587 spans**, zero empty, cache có provenance/checksum. CPU p50 **6,706 s**, p95 **9,832 s**; có inference đầu tiên, không nhận benchmark deployment. Không đổi driver/hệ thống hoặc tải thêm weights.
- Tự review 100 thumbnails/3 ảnh đầy đủ, ghi nguồn AI. CER **11,9565%** trên **38 dòng/460 ký tự**, 55 edits; 1 dòng không chắc bị loại, 1 missed detection tính deletion. **Chưa human-verified**, không gọi CER này đại diện corpus. Có lỗi dấu/merge và ảnh 2017 xoay 90 độ.
- Parity upstream **260 cases pass**; strict và compatible tách tên. R1 **686 QA/100 ảnh train**: EM/span recall **58,0175%**, F1 **69,9707%**, ANLS **64,4129%**, EM CI95 **53,1850–62,5382%**. Đây là oracle có gold, **không phải student accuracy hoặc test benchmark**. Span tối đa 4 dòng/24 tokens; multipart raw được giữ, không fuzzy sửa digit.
- Kiểm thử: **Linux 190 pass; Windows 183 pass/7 skips** (NumPy cases chạy Linux), Ruff pass, **22 schemas**. GitHub CI chưa chạy. Doctor/API inference vẫn chưa ready, đúng phạm vi hiện tại.

**Phase 1 chưa hoàn tất 100%; chưa đóng G1 tổng thể.** Còn hai mục có bằng chứng bên ngoài code: **human OCR transcription review (0 records)** và **nguồn OOD có quyền để bắt đầu annotation thật (0 ảnh/QA)**. User yêu cầu assistant tự làm; đã thực hiện AI review nhưng không giả reviewer là người hoặc gọi ReceiptVQA subset là OOD. [Review/OOD package](OOD_ANNOTATION_PROTOCOL.md) đã chuẩn bị; không tự bỏ yêu cầu SOT để ghi done. Chủ dự án/reviewer được chỉ định cần hoàn tất trước khi đóng toàn bộ phase; chưa đặt ngày giả định có dữ liệu. Các mục kỹ thuật còn lại đã có artifact thực trong báo cáo.

## Đóng G1 bằng AI — 02/11/2026

Thực hiện chỉ dẫn tường minh mới của chủ dự án, đã cập nhật **SOT v1.7/ADR-021 trước triển khai phần phụ thuộc**. [Gate G1](../artifacts/phase1/g1_ai_gate_v2.json) kiểm bằng artifacts thật; không đóng bằng thay checkbox. [Báo cáo](PHASE1_RESULTS.md), [OOD data card](data/COMMONS_OOD_SEED_V1.md), [protocol](OOD_ANNOTATION_PROTOCOL.md) và [workflow](PHASE1_WORKFLOW.md) được đồng bộ.

| Yêu cầu G1 hiện hành | Kết quả và bằng chứng |
|---|---|
| Import/validate/dedup/freeze/gold boundary | 9.500 ảnh, 64.812 QA; frozen containment 19.496 edges, zero uncontained/cross-partition component sau quarantine; bốn access plans nguyên hash; test gold vẫn khóa |
| OCR pilot/cache/profile | 100/100 G10 train receipts, 4.587 spans; p50 6,706 s/p95 9,832 s; profile v5 CPU giữ với giới hạn đã đo |
| OCR reference theo ADR-021 | 3 ảnh, 38 dòng đọc được và 1 dòng không chắc bị loại; 38/38 local reference-free review, có quyết định từ ảnh; reference cũ giữ nguyên; CER 55/460 = 11,9565%, không là human/corpus CER |
| Strict/compatible/multipart/bootstrap/R1 | 260 parity fixtures; R1 686 QA train với span max 4 dòng/24 tokens; EM 58,0175%, F1 69,9707%, ANLS 64,4129%; không là student accuracy |
| Nguồn OOD có quyền và chống trùng | 3 ảnh Commons, CC0/CC BY-SA 4.0/CC BY 2.0; metadata page revision và checksum; 28.500 cặp xuyên nguồn + 3 cặp nội bộ, zero candidates theo protocol; graph extension riêng |
| Bắt đầu OOD annotation | 24 QA tiếng Việt từ ảnh thật/blank/sample; 18 có đáp án/bbox, 6 thiếu/che/cắt có answer/bbox rỗng; tất cả local second AI review và adjudication; không dùng metadata suy đáp án |
| Provenance và gold boundary | 62 input tasks không OCR/reference; Qwen3-VL-2B NF4 chạy offline, 62 outputs không chạm cap, 62 adjudications hash-bound; `human_verified=false`, `ai_reference`, training/final evaluation=false |
| Kiểm thử/contract | Linux 205 passed; Windows 198 passed/7 skipped; Ruff lint/format pass; 27 schemas tái xuất; doctor giữ `inference_ready=false` vì chưa tích hợp backend API |

Code mới: `contracts/ai_review.py`, `data/ood_seed.py`, `data/local_ai_review.py`, `data/phase1_gate.py`; 15 tests mới kiểm label-free input, provenance, quarantine, digits/answerability, path/hash và điều kiện không tự accept output model. Artifacts cũ có `phase1_complete=false` vẫn giữ như lịch sử; report G1 mới là hiện trạng.

[Kiểm tra bàn giao](../artifacts/phase1/final_checks_ai_v1.json): tái nhập OOD tạo cùng bytes manifest/overlap/graph extension; 108 evidence files hash khớp; 27 schemas tái xuất giống hệt; kiểm 25 Markdown UTF-8/liên kết, parse 10 YAML; 95 payload files mẫu được Git ignore. `PROJECT_OVERVIEW.md` và frozen split summary giữ nguyên hash. Local reviewer dùng tối đa 1.678.092.288 bytes CUDA allocated theo counters PyTorch; 36,493 s tổng thời gian task, không gồm load model và không phải serving benchmark.

Model local có lỗi chọn sai trường, chữ số/dấu và bịa nội dung bị che. Assistant đã đối chiếu toàn bộ reference với ảnh, không lấy đồng thuận model làm chứng nhận đúng. Model review dùng cùng base student; **không độc lập model family, không human gold**. OOD này là convenience seed gồm 2 mẫu biểu tiếng Việt và 1 hóa đơn in tiếng Anh; không đại diện đầy đủ domain. Full OOD/human validation và final benchmark thuộc các phase sau, không được nhận đã xong.

Lượt này chỉ tải thêm 3 ảnh nhỏ tổng 8.000.054 bytes và metadata nguồn; **không weights/package mới, không đổi driver, không reboot, không API trả phí/public hosting**. API cap vẫn 0. Phase 2 có thể bắt đầu chuẩn bị teacher/client/ledger và kiểm quyền; chạy API thật cần vượt các gate riêng về dữ liệu/điều khoản/budget. Chưa thực hiện Phase 2, training hoặc deployment.

## Quy tắc cập nhật

Mỗi lần hoàn thành ghi ngày, artifact hoặc lệnh kiểm tra, và kết quả thực tế. Không ghi `done` nếu chỉ có skeleton. Vướng mắc phải nêu tác động, người xử lý và hạn xử lý; thay đổi kiến trúc/scope phải cập nhật SOT và [DECISIONS.md](DECISIONS.md).


## Trạng thái trước Phase 2 — base commit 0226b94

Bản snapshot dưới đây là lịch sử trước lượt triển khai Phase 2, không phải hiện trạng.

# Trạng thái ViDocLens

Cập nhật: **02/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0 và G1 đã đạt; Phase 2 chưa bắt đầu.** G1 hoàn tất theo phương án dùng AI được chủ dự án yêu cầu (ADR-021), không chứng nhận human gold hoặc final OOD benchmark. Lượt hiện tại chuẩn hóa quản lý repo và bàn giao cho commit đầu tiên.

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định task/commit/push; [nhật ký cũ](STATUS_HISTORY.md) giữ các mốc thực thi; [ADR](DECISIONS.md) ghi quyết định. Đây là nơi duy nhất ghi trạng thái phase hiện hành; không suy phần trăm dự án từ số phase đã xong.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước mở tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu và môi trường khả thi | **done** | G0: GPU/OCR pilot thật, locks dựng lại; [runbook](PHASE0_ENVIRONMENT.md), ADR-018 |
| 1 | Data pipeline, OCR, evaluator, OOD khởi đầu | **done** | G1 theo ADR-021; [báo cáo](PHASE1_RESULTS.md), [gate local](../artifacts/phase1/g1_ai_gate_v2.json) |
| 2 | Teacher, ledger/cache và baseline API | planned | G1 đã đạt; phần code offline có thể làm, chạy API thật còn gate quyền/budget |
| 3 | Student training và gold-only baseline | planned | G1 + GPU lock đã có; training smoke/reload/resume và dev metrics chưa chạy |
| 4 | Silver và chưng cất có kiểm chứng | planned | Cần G2, G3 và quyền dùng training labels |
| 5 | Verifier/cascade, calibration, full OOD | planned | Cần student/teacher bundle; full OOD human validation chưa có |
| 6 | API/demo thật, đánh giá cuối và deploy | planned | Cần G5, runtime/host và release gates |
| 7 | Báo cáo, release và bàn giao tái lập | planned | Cần final suite và reproducibility/release evidence |

Owner của các phase: chủ dự án. Thời gian dự kiến ở SOT §22 là kế hoạch, không phải ngày đã hoàn thành. `planned`, `in_progress`, `in_review`, `blocked`, `done` theo CONTRIBUTING; chỉ đổi `done` khi đủ gate, không chỉ vì đã viết code.

## Hàng đợi công việc

| ID | Việc | State | Owner / phụ thuộc | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| REPO-001 | Chuẩn hóa workflow và tiến độ | done | Assistant chuẩn bị local theo yêu cầu | STATUS/history, commit guide, templates, kiểm tra repo/schema và tests có kết quả |
| REPO-002 | Review và commit/push đầu tiên | done | **Chủ dự án đã tự push** | Local/remote main cùng 03ac245; CI Python 3.11/3.12 đạt |
| P2-001 | Chốt contract/role/policy teacher | planned | G1; không cần gọi API | Thiết kế input không gold, output/error states, role/budget; ADR nếu đổi SOT |
| P2-002 | Provider adapter, cache và ledger | planned | P2-001 | Tests offline: cache key, budget reservation, retry, missing/refusal/truncate |
| P2-003 | Pilot teacher và baseline dev | planned | P2-002 + quyền external/budget/model snapshot | Evidence pilot 50 ảnh/dev metrics/cost theo SOT, không dùng test/OOD tuning |

REPO-002 đã hoàn tất; P2-* chưa triển khai. Khi task lớn cần chi tiết, dùng [mẫu task](templates/TASK.md) hoặc GitHub Issue; STATUS chỉ giữ dòng tổng quan và link.

## Ràng buộc và blocker cụ thể

| Mục | Trạng thái / tác động | Owner / điều kiện gỡ |
|---|---|---|
| API budget | Cap = 0; chưa được gọi API trả phí | Chủ dự án chốt budget, quyền external và điều khoản provider trước P2-003 |
| Quyền teacher output | Chưa chốt quyền distillation qua API; local 4B mới là candidate | Kiểm [access register](DATA_ACCESS_REGISTER.md), pilot nhánh có quyền trước sinh silver |
| AI references | Không human gold; OOD seed không dùng confirmatory evaluation | Full OOD/human validation ở Phase 5; không sửa flag để đóng gate |
| API runtime/deploy | `inference_ready=false`, model backend chưa tích hợp | Phase 6; không coi health/live hoặc CI CPU là inference/deploy thành công |
| GitHub | Repo private, local/remote main khớp; CI đã đạt | Chủ dự án tiếp tục tự commit/push; assistant không publish/sync code |

Các ràng buộc trên không chặn viết code/tests offline của Phase 2. Giữ driver hiện tại; không tự reboot, public hosting hoặc mở test gold.

## Bằng chứng G0/G1 đã đóng

| Hạng mục | Kết quả đã đo | Bằng chứng |
|---|---|---|
| Môi trường | WSL2 Ubuntu 24.04.5, Python ML/OCR 3.11.14, RTX 3060 12 GB; driver 617.42 | [Môi trường](PHASE0_ENVIRONMENT.md), [history](STATUS_HISTORY.md) |
| ReceiptVQA | 9.500 ảnh/64.812 QA; 19.496 containment constraints | [Data card](data/RECEIPTVQA_CONTAINMENT_V1.md) |
| Split | 4.527 train_fit, 504 audit, 456 dev_select, 190 dev_calibrate, 950 test, 2.873 quarantine | [Frozen summary local](../data/splits/receiptvqa_containment_v1/summary.json); không sửa trong lượt này |
| OCR | 100/100 ảnh G10 train, 4.587 spans; p50 6,706 s/p95 9,832 s | [Phase 1](PHASE1_RESULTS.md) |
| OCR AI reference | 38 dòng/3 ảnh; CER 55/460 = 11,9565%; 1 uncertain excluded, 1 missed line là deletion | [G1 gate local](../artifacts/phase1/g1_ai_gate_v2.json); không là corpus/human CER |
| Evaluator/R1 | 260 parity cases; R1 686 train QA, EM 58,0175%, F1 69,9707%, ANLS 64,4129% | [Báo cáo](PHASE1_RESULTS.md); oracle có gold, không là student accuracy |
| OOD seed | 3 ảnh Commons/24 QA, 18 answerable + 6 unanswerable; zero candidates trong 28.503 cặp theo protocol | [OOD data card](data/COMMONS_OOD_SEED_V1.md); có nguồn/license, không là final benchmark |
| AI review | 62 local reference-free outputs + adjudications; same student base, không independent human/model family | [Provenance local](../artifacts/phase1/ai_review_final_v1/provenance.json) |

Các link artifacts/data là evidence **local, Git ignored**; người clone repo đọc báo cáo tổng hợp và làm theo workflow để có evidence được phép. GitHub checkout không kèm dataset/weights/private outputs.

## Kiểm tra local mới nhất — nâng cấp workflow

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python 3.14.9 — pytest | **216 passed, 7 skipped**; NumPy cases chạy đủ Linux |
| WSL ML-repro Python 3.11.14 — pytest | **223 passed** |
| Ruff check / format | Đạt cả hai; format kiểm 87 files |
| Schema drift | **27 schemas match**, chế độ `--check` không ghi file |
| File policy / YAML | Đạt với 179 candidates tại lúc kiểm; không phải secret/content/license scan |
| Staged diff | Đã chạy checker, báo chưa có staged files; chưa đủ điều kiện kiểm nội dung commit, người dùng chạy lại sau khi tự stage |
| GitHub CI | **Đạt** trên Python 3.11 và 3.12 tại commit 03ac245; [run 41479278954](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41479278954) |
| Docker/GPU | Không chạy thêm trong lượt workflow; GPU evidence trước đó thuộc G0/G1 |

18 tests mới kiểm file policy, index khác worktree và schema drift thiếu/sai/dư mà không sửa file. Có warning Starlette/httpx đã biết; chưa đổi dependency để xử lý warning này.

## Bàn giao nâng cấp workflow — trước push

- Đã làm: tách hiện trạng khỏi history, quy ước task/branch/commit, mẫu Issue/PR, CHANGELOG; thêm read-only checks và CI permissions read-only.
- Tài liệu điều hành: SOT v1.8/ADR-022; không thay scientific gates hoặc sửa kết quả Phase 0–1.
- Git local tại lúc kiểm: `main`, chưa có commit/staged files; đã thấy `origin` là `https://github.com/minhnguyen1210/ViDocLens.git`. Assistant chỉ đọc cấu hình này, không tạo/sửa remote, stage/commit hoặc push.
- Commit đầu tiên đề xuất: `feat: add ViDocLens foundation and phase 1 pipeline`.
- Việc tiếp theo của chủ dự án: [review/stage/commit/push thủ công](../CONTRIBUTING.md). Việc kỹ thuật sau đó: P2-001; Phase 2 chưa bắt đầu.

## Bàn giao mới nhất — xác minh push ngày 02/11/2026

- Chủ dự án đã push `03ac245e6d31ef05af5fdc174dfbbbf5bca565b3`, tiêu đề `feat: add ViDocLens foundation and phase 1 pipeline`; `git ls-remote` xác nhận remote main khớp HEAD local.
- Repo `minhnguyen1210/ViDocLens` là private, default branch main. CI run 41479278954 completed/success, cả Python 3.11/3.12 đạt. Docker Compose config đạt không đồng nghĩa container/GPU deployment đã chạy.
- Git sạch trước kiểm tra. Tracked data/artifacts/cache/reports chỉ có README/.gitkeep; env chỉ có `.env.example`; file policy đạt. Không coi đây là secret/content scan.
- Assistant chỉ đọc Git/GitHub và cập nhật STATUS local; không stage/commit/push hoặc thay remote. Bản cập nhật tài liệu này chưa thuộc commit/CI vừa xác minh.
- Bước tiếp theo: P2-001; Phase 2 chưa bắt đầu, API cap vẫn 0.

Mỗi lần bàn giao cập nhật bảng kiểm tra và mục này với kết quả thật. Khi nhật ký dài, chuyển các mốc cũ vào STATUS_HISTORY, giữ link evidence và mốc thời gian. Không sửa artifact cũ để khớp hiện trạng mới.

## Phase 2 trước khi có credential — 02/11/2026

Mốc lịch sử trước lượt API thành công, không phải hiện trạng mới nhất:

- Đã triển khai contracts, Responses adapter, permission gates, cache/ledger/retry, Batch reconciliation, evaluator và CLI theo ADR-023. Windows 277 passed/7 skipped; WSL 284 passed; 36 schemas match.
- OCR dev thật 100/100; plan bất biến gồm 50 ảnh G10 train/344 QA và 100 ảnh dev_select/666 QA, tổng 511 request groups. Payload/hash validation và tái tạo plan đạt.
- Chủ dự án duyệt cap 20 USD, quyền benchmark trên đúng 150 ảnh/511 keys và xác nhận data/terms/retention; Batch upload và training export vẫn false.
- [Lần thử pilot đầu](../artifacts/phase2/live_pilot_v1/run.json) dừng vì thiếu key: 0 requests hoàn tất, ledger attempts/spend/reserved/uncertain đều 0. [Readiness tại mốc đó](../artifacts/phase2/readiness_v2.json) ghi blocked. Không có metric API hoặc role winner tại thời điểm này.
- Chủ dự án sau đó tạo `.env`, điền key và yêu cầu tiếp tục. ADR-024 bổ sung nạp credential runtime và khóa selection policy trước dev output. Lượt tiếp theo dùng thư mục `live_pilot_v2`, giữ nguyên evidence của lần thiếu key và ledger cap.
- Không stage/commit/push hoặc sửa remote. Kết quả hiện hành ở [STATUS](STATUS.md), [báo cáo Phase 2](PHASE2_RESULTS.md).

## Đóng G2 sau khi chủ dự án cấp `.env` — 03/11/2026

- Runtime nạp credential theo ADR-024; cả hai model snapshots trả Responses thật. Pilot 59/59 ok, A1/A2/A3 mỗi arm 113/113 ok; A5 112 ok + 1 schema error chứa 6 QA, giữ error denominator.
- Cùng 100 dev components/666 QA: strict EM A1/A2/A3/A5 = 57,66 / 73,72 / 76,28 / 70,27%. Benchmark và fallback chọn A3 theo policy khóa trước dev; local label teacher còn gate trước Phase 4, serving disabled.
- Tổng 511 live attempts, 6,080008 USD theo usage trong cap 20 USD; reserved/uncertain=0. Replay 511/511 cache hits, không thêm calls/spend, result hashes trùng. [Report G2](../artifacts/phase2/final_v1/report.json) đạt 9/9 criteria; SHA `7c0462bce5ffc7b888b4293376b06573c1e1926f72f080438217ef2116347e21`.
- Windows 289 passed/7 skipped, WSL 296 passed; lint/format/36 schemas/file policy đạt. SOT v1.10/ADR-025 và config/docs cập nhật. Phase 2 done local, Phase 3 planned; không stage/commit/push hoặc thay remote, chưa CI mới/deploy.


## Snapshot bàn giao Phase 2 trước nhánh laptop Phase 4 (03/11/2026)

Bản STATUS dưới đây lưu nguyên nội dung mốc Phase 2, kể cả branch/CI/check counts cũ. Hiện trạng ở STATUS; nhánh laptop hiện bắt đầu từ commit d13360e.

## Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0, G1 và G2 đã đạt. Phase 2 hoàn tất local theo SOT v1.10.** Key trong `.env` đã dùng thành công; pilot và A1/A2/A3/A5 chạy đủ **511 requests / 150 ảnh duy nhất**, tổng chi phí usage × price card **6,080008 USD trong cap 20 USD**. Replay 511/511 cache hits không thêm API calls/spend. [Báo cáo đầy đủ](PHASE2_RESULTS.md) · [gate local](../artifacts/phase2/final_v1/report.json).

[SOT](../SOURCE_OF_TRUTH.md) quy định gate; [CONTRIBUTING](../CONTRIBUTING.md) quy định Git/task; [history](STATUS_HISTORY.md) giữ các mốc trước; [ADR](DECISIONS.md) ghi quyết định. Không suy phần trăm toàn dự án từ số phase/tests. Hoàn tất Phase 2 không đồng nghĩa đã train student hoặc deploy sản phẩm.

### Bảng phase hiện hành

| Phase | Mục tiêu | State | Gate / bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng, dữ liệu/môi trường | **done** | G0: GPU/OCR pilot thật, locks dựng lại; [runbook](PHASE0_ENVIRONMENT.md), ADR-018 |
| 1 | Data, OCR, evaluator, OOD khởi đầu | **done** | G1 theo AI protocol ADR-021; [báo cáo](PHASE1_RESULTS.md), [gate local](../artifacts/phase1/g1_ai_gate_v2.json) |
| 2 | Teacher, ledger/cache và API baselines | **done** | G2: live pilot/baselines, metric/cost, cache replay, role freeze; ADR-025 |
| 3 | Student training / gold-only | planned | **Bước kế tiếp:** training smoke/save/reload/resume trên 12 GB, L1/L2 dev baselines |
| 4 | Silver và chưng cất | planned | Cần G3 và gate local label teacher; output API hiện không được dùng train |
| 5 | Verifier/cascade, calibration, full OOD | planned | Cần model bundles, routing calibration và full OOD validation |
| 6 | API/demo thật, final eval/deploy | planned | Cần G5, runtime/host và release gates |
| 7 | Báo cáo, release/tái lập | planned | Cần final suite, reproducibility và release evidence |

G1 bằng AI không là human gold/final OOD. Serving vẫn `inference_ready=false`; teacher CLI không đồng nghĩa backend sản phẩm đã triển khai.

### Hàng đợi

| ID | Công việc | State | Kết quả / điều kiện |
|---|---|---|---|
| REPO-001/002 | Workflow và push đầu tiên | done | Chủ dự án tự push; history giữ evidence/CI trước Phase 2 |
| P2-001 | Contract, permissions, prompt, model/price candidates | **done (local)** | Pydantic/schema; no-gold input; scope theo exact request keys; ADR-023 |
| P2-002 | Provider, cache, budget, retry, Batch, evaluator/CLI | **done (local)** | Offline cases đạt; Responses thật đã chạy; Batch upload chưa thuộc quyền được cấp |
| P2-004 | OCR dev và manifest pilot/baselines | **done** | OCR 100/100; 50 train + 100 dev, 511 groups; plan tái tạo trùng hashes |
| P2-003 | Live pilot/baselines, replay, metric và role freeze | **done** | 9/9 criteria của [G2 report](../artifacts/phase2/final_v1/report.json) đạt; cấu hình A3 khóa theo policy định trước |
| P3-001 | Student training feasibility | planned | Dùng stack ML đã khóa; loss mask/gradient, train smoke, save/reload/resume và số đo VRAM trước full L2 |

### Kết quả Phase 2

Pilot **50 ảnh / 344 QA / 59 groups** đều hợp lệ. Mỗi baseline dùng đúng **100 dev components / 666 QA / 113 groups**; không mở test/OOD/dev_calibrate/audit để chọn teacher. Gold dev chỉ evaluator đọc sau khi đủ predictions.

| Arm | Input/model | Strict EM | Token F1 | ANLS | USD |
|---|---|---:|---:|---:|---:|
| A1 | GPT-5.4, OCR text | 57,66% | 68,87% | 80,69% | 1,214753 |
| A2 | GPT-5.4, ảnh | 73,72% | 85,54% | 89,10% | 1,677962 |
| A3 | GPT-5.4, ảnh + OCR | **76,28%** | **87,53%** | **90,01%** | 1,750404 |
| A5 | GPT-5.4 mini, ảnh + OCR | 70,27% | 81,26% | 86,65% | 0,520879 |

Pilot tốn thêm 0,916010 USD. Đây là chi phí theo usage và price cards, chưa đối soát invoice tài khoản. Một A5 schema error chứa **6 QA** được tính lỗi trong toàn bộ 666 QA, không bỏ mẫu hoặc retry để tăng điểm. Null/error/missing đều giữ denominator. Các metric là dev subset, không phải final test.

**Benchmark/fallback chọn A3**: `gpt-5.4-2026-03-05`, image+OCR, prompt `teacher_vqa_v2`, detail high, reasoning none, output cap 4096, store false. A3−A2 = +2,55pp EM, paired 95% CI [+0,43; +4,75]pp. A5 rẻ hơn nhưng giảm 6,01pp, vượt ngưỡng fallback 2pp đã khóa. Fallback serving vẫn disabled. [Role freeze](../artifacts/phase2/final_v1/role_freeze.json), ADR-025.

### Quyền và điều kiện cho phase sau

| Mục | Hiện trạng | Điều kiện tiếp theo |
|---|---|---|
| API budget | 6,080008/20 USD; 511 attempts; reserved/uncertain=0 | Giữ ledger; số dư không mở thêm phạm vi benchmark |
| External processing | Grant owner đã xác nhận data/terms/retention, bind đúng archive/split/511 keys | Không tự mở sang test/OOD, dữ liệu mới hoặc online serving |
| Credential | `.env` đã dùng thành công, ignored; runtime không log key | `--env-file .env` sau permission gates; file không đi vào Git |
| Batch / API training export | **Chưa cấp**, flags false | Không upload Batch hoặc dùng evaluation cache train student |
| Label teacher | Strategy local open-weight ADR-014; Qwen3-VL-4B còn candidate | License/revision/VRAM/quality pilot phải đạt trước Phase 4; nếu fail giữ gold-only |
| GitHub/deploy | Thay đổi Phase 2 ở local; CI mới chưa chạy; serving chưa ready | Chủ dự án tự commit/push; deployment thuộc Phase 6 |

Template permission trong Git vẫn deny/cap0; approval thật nằm trong `artifacts/phase2/approval.json` bị ignore. Không có blocker G2 còn mở; điều kiện label/serving thuộc các phase sau theo SOT, không bị coi đã đạt.

### Kiểm tra local mới nhất

| Kiểm tra | Kết quả thực tế |
|---|---|
| Windows Python 3.14.9 pytest | **289 passed, 7 skipped**; NumPy cases chạy đủ WSL |
| WSL ML-repro Python 3.11.14 pytest | **296 passed** |
| Teacher / credential / finalization fixtures | 61 / 8 / 4 cases trong suite, không thay thế live evidence |
| Ruff check / format | Đạt; **105 Python files** |
| Schema drift | **36 schemas match** |
| File policy / YAML | Đạt **212 candidates** tại lượt kiểm; không là secret/content/license scan |
| Docs / diff | UTF-8, liên kết local và `git diff --check` đạt; role config khớp report, plan tái tạo sau freeze vẫn trùng hash |
| Live cache replay | **511/511 hits**, result hashes trùng; 0 calls/spend mới; không cần credential |
| Doctor | `inference_ready=false`, `model_not_configured` đúng hiện trạng |
| GitHub CI | CI cũ tại 03ac245 đã đạt ([run](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41479278954)); **chưa có CI cho Phase 2** |
| GPU/Docker | Không chạy thêm GPU/student/Docker tests; OCR CPU dùng stack đã khóa |

[Evidence checks](../artifacts/phase2/checks_live_v2/summary.json). Warning Starlette/httpx đã biết còn tồn tại. PowerShell runner đã kiểm AST syntax nhưng chưa chạy interactive; campaign này dùng CLI với `.env`. Không cài dependency, đổi driver, tải thêm model/dataset, reboot hoặc mở hosting.

### Bàn giao

- Local branch `codex/phase2-teacher-pipeline`, base `0226b94`; **không stage/commit/push, không thay remote**. GitHub CI/release là trạng thái riêng.
- SOT v1.10, ADR-025, role config, README/CHANGELOG, access register, workflow/results và budget notes khớp kết quả thực. G0/G1 evidence, frozen split, prompt/plan/policy và `PROJECT_OVERVIEW.md` giữ nguyên.
- Artifacts local bị ignore: [plan](../artifacts/phase2/api_plan_v1/manifest.json), [G2 report](../artifacts/phase2/final_v1/report.json), [role freeze](../artifacts/phase2/final_v1/role_freeze.json), [checks](../artifacts/phase2/checks_live_v2/summary.json). Report có hashes live/replay manifests; usage/raw/parsed giữ trong cache/ledger.
- Việc kế tiếp là **Phase 3 / P3-001**, sau đó L1 và L2-k10 trên dev theo SOT. G2 hoàn tất không mở quyền API training export và không tự bắt đầu sinh silver.


## Snapshot Phase 4 offline v1 trước bổ sung ADR-P4-002 (03/11/2026)

Bản này lưu nguyên trạng báo cáo tại lần triển khai đầu; thông tin chưa commit/push bên dưới đã được thay bằng HEAD 3ae2c4f do owner commit/push. Xem STATUS hiện hành để biết phần bổ sung.

# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G2 đã đạt theo hồ sơ; G3/G4 chưa được xác nhận trong checkout laptop.** Chủ dự án cho biết Phase 3 đang dở trên PC, chưa push. Nhánh **`phase4-offline` từ `d13360e`** đã triển khai phần CPU Phase 4 và kiểm chứng bằng fixtures. Chưa sinh silver thật hoặc train P1/P2. [Bàn giao PC/merge](PHASE4_OFFLINE_HANDOFF.md) · [workflow](PHASE4_OFFLINE_WORKFLOW.md).

[SOT v1.11](../SOURCE_OF_TRUTH.md), [ADR-P4-001](DECISIONS.md), [CONTRIBUTING](../CONTRIBUTING.md) quy định phạm vi/gates. [STATUS_HISTORY](STATUS_HISTORY.md) giữ nguyên mốc bàn giao Phase 2 và các kết quả trước. Không suy phần trăm dự án từ tests hoặc số module.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Nền móng và feasibility | done | G0/ADR-018, GPU/OCR pilot/lock ở hồ sơ trước |
| 1 | Data, OCR, evaluator, OOD seed | done | G1 theo AI protocol ADR-021; [kết quả](PHASE1_RESULTS.md), không phải human gold/final OOD |
| 2 | Teacher/API baselines | done | G2/ADR-025; [kết quả](PHASE2_RESULTS.md), code tại d13360e |
| 3 | Student/gold-only | in_progress (PC, owner-reported) | Code chưa có trên laptop; cần hoàn tất G3 và đối chiếu trainer khi tích hợp |
| 4 | Silver/chưng cất | in_progress (offline CPU) | Contracts/F0/F1/audit/selections local đạt tests; chưa local teacher/silver thật/training/G4 |
| 5 | Verifier/cascade/full OOD | planned | Chờ student bundles, calibration và validation |
| 6 | API/demo/final evaluation/deploy | planned | Serving vẫn chưa có model, chưa deploy |
| 7 | Báo cáo/release/tái lập | planned | Chờ final suite và release evidence |

## Hàng đợi và bàn giao local

| ID | Công việc | State | Kết quả / điều kiện gỡ |
|---|---|---|---|
| P2-001/002/003/004 | Teacher, OCR dev, pilot/baselines, replay/role freeze | done | Bảo toàn kết quả Phase 2, không gọi lại API |
| P3-001 và L1/L2 | Training feasibility/gold-only | in_progress (PC) | Owner hoàn tất; chưa kiểm tra code/checkpoint/G3 trên laptop |
| P4-OFF-001 | Silver contracts, pool builder, local result exchange | done (local) | 10 schema mới; no-gold/frozen split boundaries; adapter generation local chưa có |
| P4-OFF-002 | F0/F1, evidence/reasons, bundles/replay | done (local) | CPU fixtures đạt; thresholds vẫn chưa calibrated, semantic_check unknown |
| P4-OFF-003 | Audit/selection CLI | done (local) | Exact-batch approvals, matched strata/counts, 3 arms × 3 seeds; chưa train |
| P4-OFF-004 | Tests/docs/PC handoff | done (local) | 58 tests mới, full suite 354 passed; không commit/push |
| P4-PC-001 | Local teacher pilot và silver thật | blocked (execution) | Owner/PC: khôi phục artifacts, kiểm license/data/revision/VRAM/quality; đạt gate trước generation |
| P4-PC-002 | Training integration và core matrix | blocked (execution) | Hoàn tất G3, review contract adapter, freeze filter trên dev, audit holdout và train cùng budget/3 seeds |

## Kiểm tra mới nhất — laptop CPU

Môi trường mới **Windows Python 3.14.0**, `.venv` riêng: pydantic 2.14.2, pytest 9.2.0, Ruff 0.17.3, NumPy 2.5.4. Cài extras core/data/teacher/serve/dev; không đổi ML/OCR locks, không cài torch/transformers/Paddle vào venv CPU này. Đây không là lock tương thích GPU.

| Kiểm tra | Kết quả đã chạy |
|---|---|
| Full pytest `-q -p no:cacheprovider --tb=short` | **354 passed**, 1 Starlette/httpx deprecation warning |
| Phase 4 coverage | **58 cases mới**, synthetic archive/teacher/OCR và unit boundary tests; không là metric chất lượng |
| Ruff check / format --check | Đạt toàn repo tại lượt kiểm |
| Schema drift | **46 schemas match** |
| File policy / YAML | Đạt **235 candidate files** tại lượt kiểm; không là secret/license review |
| Git diff --check | Đạt |
| Docs / UTF-8 / links | Đạt trên 235 files; không có link nội bộ thiếu ngoài artifacts/data/cache/reports bị ignore; PROJECT_OVERVIEW giữ nguyên SHA256 |
| Doctor | `inference_ready=false`, `model_not_configured`; torch/transformers/PaddleOCR không có trong venv CPU |
| GPU, local teacher, training, Docker | Không chạy trong lượt laptop |
| GitHub CI/release | Không kiểm/chạy mới; không suy từ CPU checks thành CI đạt |

[Logs/summary thực](../artifacts/phase4/checks_offline_v1/summary.json) nằm trong artifacts ignored, không đi cùng Git. Test suite chạy ngoài sandbox Windows vì các lượt audit trước bị chặn socket/temp/hard link; dùng synthetic fixtures/MockTransport, không dùng `.env` thật hoặc gọi provider. Một workflow test Git chỉ stage trong temporary fixture repo riêng, không stage project.

## Quyền và kết quả nghiên cứu giữ nguyên

- Phase 2 ghi nhận 511 requests/150 ảnh, cost usage × price card **6,080008/20 USD**, replay 511/511 không calls/spend mới. Benchmark/fallback A3 có dev EM 76,28%; chi tiết và giới hạn ở [PHASE2_RESULTS](PHASE2_RESULTS.md). Không tái tính từ raw artifacts trong lượt này.
- API training export/Batch upload/online serving vẫn không được mở. Không dùng evaluation cache làm training labels. Nhánh silver dùng local open-weight sau gate, 4B chưa được chứng nhận bằng code CPU.
- Approval local Phase 4 phải bind đúng pool/batch và evidence. Fixtures không được dùng làm training thật; freeze synthetic không mở real batch. Gold audit tách filter; test/OOD/dev_calibrate không mở.
- Chưa có real-data filter accuracy/retention, student gain, human audit hoặc G4 evidence mới. `semantic_check=unknown`; OCR support không là semantic truth.

## Git và tích hợp PC

- Đã kiểm tra branch chưa tồn tại trước khi tạo **`phase4-offline`**, base/HEAD **`d13360e`**. Chỉ tạo/switch nhánh local; không đổi remote/Git identity.
- Thay đổi còn trong working tree: **không stage, không commit, không push, không author/co-author mới**. Owner tự review/commit/chuyển code. Chỉ merge nhánh chưa commit sẽ không mang theo code mới.
- Không sửa student, student configs, ML/OCR locks, core CLI, serving hoặc provider/ledger Phase 2. Các file chung cần hợp nhất thủ công với PC được liệt kê trong [handoff](PHASE4_OFFLINE_HANDOFF.md).
- Khi về PC: bảo toàn/lưu Phase 3 → tích hợp code Phase 4 → kiểm schemas/tests → nối trainer và smoke trên GPU → pilot teacher/calibrate/audit/train core matrix khi đủ gates. Không ghi đè toàn bộ STATUS/SOT của PC bằng bản laptop.

## Snapshot trước bàn giao Phase 5 offline (03/11/2026)

Bản STATUS nguyên trạng ở base Phase 4; thông tin chưa commit dưới đây thuộc thời điểm cũ.

# Trạng thái ViDocLens

Cập nhật: **03/11/2026 (Asia/Saigon)** · Owner: **Nguyễn Hữu Gia Minh**.

**G0–G2 đạt theo hồ sơ; G3/G4 chưa được xác nhận trong checkout laptop.** Chủ dự án đang làm Phase 3 trên PC, source chưa có ở đây. `phase4-offline` có bản đầu tại **`3ae2c4f`** do owner commit/push; phần bổ sung ADR-P4-002 đang **local, chưa stage/commit/push**. Đã hoàn thiện bốn nhóm tooling còn thiếu có thể kiểm CPU: local teacher orchestration, dev threshold grid, human audit workflow và core result comparison. Chưa chạy Qwen GPU, sinh silver thật, chọn ngưỡng thật, human review ảnh thật hoặc train P1/P2.

[SOT v1.12](../SOURCE_OF_TRUTH.md) · [ADR-P4-001/002](DECISIONS.md) · [workflow F0/F1](PHASE4_OFFLINE_WORKFLOW.md) · [công cụ bổ sung](PHASE4_LOCAL_TOOLS.md) · [bàn giao PC](PHASE4_OFFLINE_HANDOFF.md). Nhật ký cũ giữ trong [STATUS_HISTORY](STATUS_HISTORY.md), gồm snapshot offline v1 trước bổ sung. Code done, CPU checks, commit, push, CI và release là các trạng thái riêng.

## Bảng phase hiện hành

| Phase | Mục tiêu | State | Bằng chứng / bước tiếp |
|---|---|---|---|
| 0 | Foundation/feasibility | done | G0/ADR-018; GPU/OCR pilot và locks trong hồ sơ trước |
| 1 | Data/OCR/evaluator/OOD seed | done | G1 theo AI protocol ADR-021; [kết quả](PHASE1_RESULTS.md), không là human gold/final OOD |
| 2 | Teacher/API baselines | done | G2/ADR-025; [kết quả](PHASE2_RESULTS.md), code d13360e |
| 3 | Student/gold-only | in_progress (PC, owner-reported) | Chưa có source/checkpoint/G3 mới trên laptop; owner hoàn tất và tích hợp |
| 4 | Silver/chưng cất | in_progress | Tooling CPU đã có; Qwen adapter chưa smoke; còn real pilot/data/audit/training/G4 |
| 5 | Verifier/cascade/full OOD | planned | Chờ student bundles/calibration/validation |
| 6 | API/demo/final evaluation/deploy | planned | Inference chưa ready, chưa deploy |
| 7 | Báo cáo/release/tái lập | planned | Chờ final suite và release evidence |

## Task và bàn giao local

| ID | Công việc | State | Kết quả / điều kiện gỡ |
|---|---|---|---|
| P4-OFF-001 | Contracts/pool/local result exchange | done (code) | Bản đầu đã owner commit/push; frozen G10 boundaries không đổi |
| P4-OFF-002 | F0/F1/bundles/replay | done (code) | Numeric/raw/occurrence guards; semantic_check unknown; bổ sung atomic publish |
| P4-OFF-003 | Audit/nine experiment selections | done (code) | Exact-batch approval, P1-full/P1-size/P2 × 3 seeds; chưa training |
| P4-OFF-004 | Tests/docs/handoff | done (local) | SOT/ADR/status/history/runbooks/schema cập nhật; bổ sung chưa commit |
| P4-OFF-005 | Local teacher orchestration + adapter code | done (local CPU scope) | Snapshot/config/plan, grouped question-only requests, parser, raw transactional attempts, retry/resume; lazy Qwen GPU adapter **chưa smoke** |
| P4-OFF-006 | Dev threshold grid/selection | done (local code) | Đủ 4 thresholds trên cùng inputs; replay/hash checks, rationale/freeze; không tự chọn ngưỡng thật |
| P4-OFF-007 | Human audit workflow | done (local code) | Seeded four-stratum blind JSON packet/template/import; chưa người review ảnh thật, chưa có annotation UI |
| P4-OFF-008 | Results/fair comparison | done (local code) | 12-result contract, same data/profile/updates/exposure checks, missing denominator, seed mean/std, paired group bootstrap/CSV/slices |
| P4-PC-001 | Local teacher smoke/pilot/silver thật | blocked (execution) | Owner/PC khôi phục model/data, xác minh revision/license/quyền/VRAM/quality, exact-plan grant; mở quality gate trước silver generation |
| P4-PC-002 | Training integration/core matrix | blocked (execution) | Owner hoàn tất G3/source PC; nối selections/raw targets + per-qid exposure/result exporter; dev freeze/holdout audit rồi train/evaluate cùng budget/3 seeds |

F2/F3, label correction và semantic-constrained filter vẫn là extension/phase sau trong SOT; không đưa vào core bằng việc viết code laptop. Không thể hoàn tất G4 chỉ với mock backend hoặc fabricated training results.

## Kiểm tra đã chạy

Windows Python **3.14.0**, `.venv` CPU cục bộ; pytest9.2.0, pydantic2.14.2, Ruff0.17.3, NumPy2.5.4. Không cài torch/Transformers/Paddle, không sửa CUDA/ML/OCR locks. Không coi đây là compatibility lock GPU.

| Kiểm tra | Kết quả |
|---|---|
| Full pytest `-q -p no:cacheprovider --tb=short` | **400 passed**, 1 Starlette/httpx deprecation warning; 46 cases bổ sung trên 354 cũ |
| CLI sau khi bổ sung command `config` | **4 passed**; config/plan không import ML và workflow grid→freeze→review→comparison |
| Ruff check / format --check | Đạt; **132 Python files** formatted |
| Schema drift | **59 schemas match** (13 mới) |
| File policy/YAML | Đạt **262 candidate files**; không là secret/license review |
| Diff whitespace | `git diff --check` đạt |
| UTF-8 / links | **234 text files**, không BOM/replacement character hoặc missing repo-doc target; ignored data/artifact paths loại khỏi link existence check |
| Historical overview | Giữ nguyên SHA256 `d7d16d8d5400540c4e529cd07de92e1abf41c688584dbbf599ab5c67a6d3cf63` |
| Doctor | `inference_ready=false`, `model_not_configured`; không torch/Transformers/Paddle/NVIDIA runtime được phát hiện |
| GPU/model/data/training/Docker | Không chạy trong lượt laptop; Docker CLI có mặt không chứng minh runtime/deploy |

[Evidence local](../artifacts/phase4/checks_offline_v2/summary.json) lưu command logs và phạm vi, nằm trong artifacts ignored. Full pytest log lưu output tail của session đã hoàn tất; CLI recheck riêng sau thay đổi nhỏ. Tests dùng synthetic fixtures/MockTransport; không gọi paid provider hoặc đọc `.env`. Chạy ngoài sandbox Windows cho temp/hard-link và API TestClient sockets. Test Git workflow chỉ dùng temporary fixture repo, không stage project.

## Quyền và hạn chế

- Phase 2 giữ kết quả lịch sử: 511 requests/150 ảnh, cost theo usage **6,080008/20 USD**, replay không calls/spend mới; không tái thực thi trong lượt này. API training export/Batch upload/serving external vẫn disabled.
- Runner local chỉ dùng snapshot có sẵn, không download/public hosting. Snapshot và owner grants là attestation/hash, không tự chứng minh license/nguồn revision/quality. Grant generation và approval training tách biệt; holdout cần freeze. Model 4B/GPU adapter chưa được xác minh trên host thật.
- Grid/human/comparison đã có code, chưa có metrics nghiên cứu mới. Blind review cần người xem ảnh; fixture flag không được đổi thành evidence thật. Fairness checks kiểm manifest, không chứng minh trainer đã làm đúng. Missing/error/abstain vẫn ở denominator, bootstrap không tự bao gồm training variance.
- Test/OOD/dev_calibrate không mở trong Phase 4 workflow; gold chỉ trong evaluator. F1 không sửa raw label hoặc chứng nhận semantic truth. Data/cache/grants/weights/artifacts không đi cùng Git checkout.

## Git và bước tiếp theo

- Branch hiện tại **`phase4-offline`**, base Phase2 **`d13360e`**, HEAD **`3ae2c4f90965e6c4fb9c4cc42880a7a19a3bfff2`**. Bản đầu đã owner push; [CI của đúng commit này](https://github.com/minhnguyen1210/ViDocLens/actions/runs/41601272656) từng được xác minh success (Python3.11/3.12). Đây **không** là CI của phần bổ sung chưa commit.
- Lượt này assistant chỉ sửa worktree/kiểm tra: **không stage, commit, push, publish, đổi identity hoặc thêm author/co-author**. Không có release mới. Owner tự review/stage/commit/push bổ sung rồi kiểm CI của commit mới.
- Không sửa student/student configs, ML/OCR locks, core CLI, serving, Phase 2 provider/ledger hoặc PROJECT_OVERVIEW. Shared docs/exporter/schema cần hợp nhất nội dung khi về PC; không copy nguyên STATUS/SOT laptop đè tiến độ PC.
- Trên PC: bảo toàn Phase3 code/checkpoints → merge toàn bộ commits Phase4 → chạy CPU/schema checks → nối trainer/result exporter và smoke GPU → local teacher quality pilot/quyền → silver thật, dev grid/freeze, holdout human audit → L2/P1/P2 ba seed và comparison → xét G4 bằng evidence. Chi tiết file ownership/commands ở [handoff](PHASE4_OFFLINE_HANDOFF.md).
