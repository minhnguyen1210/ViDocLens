# Sổ khảo sát tài liệu

**Trạng thái: hoàn tất khảo sát có chọn lọc 12 công trình cho định vị Phase 0, ngày 02/11/2026.** Đây là scoping review có giới hạn, không phải systematic review toàn diện hay tái lập thực nghiệm. Quyết định thiết kế hiện hành nằm trong [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md). Không dùng việc chưa tìm thấy một bài để khẳng định “đầu tiên” hoặc “chưa ai làm”.

## Bằng chứng đã đối chiếu trong audit thiết kế — 02/11/2026

Các mục dưới đây tổng hợp việc đọc primary sources của tác vụ audit nghiên cứu. Đây là bằng chứng từ paper/repository/model card, **chưa phải kiểm kê archive tải về, tái lập scorer hay benchmark trên máy local**. Bản sao điều khoản, revisions và manifest thực vẫn phải được lưu khi nhập dữ liệu/chốt môi trường.

**Cập nhật sau lượt audit thiết kế:** annotations ReceiptVQA đã được tải và kiểm kê ngày 02/11/2026; xem [STATUS](STATUS.md) cho số đo, hash và khác biệt serialization thực tế. Bảng dưới giữ bối cảnh đọc tài liệu; không suy rằng CSV đã chứa literal `¡sep¿` chỉ từ mô tả paper. Scorer parity và ảnh vẫn chưa kiểm tra.

| Nguồn gốc | Điều đã đối chiếu | Hệ quả / phần chưa xác minh |
|---|---|---|
| [ReceiptVQA / LiGT paper v1](https://arxiv.org/html/2502.19202v1) | Mô tả 9.500 ảnh, 64.812 QA; train 7.600/51.886, dev 950/6.426, test 950/6.500 (ảnh/QA). Paper có chỗ bất nhất tổng QA: Table 3 ghi 68.412. Multi-part answer dùng delimiter `¡sep¿`; ANLS giữ similarity khi normalized edit distance < 0,5; token F1 tách whitespace. | Không tự sửa archive theo paper: đếm records từ archive nhận được mới chốt manifest; giữ evidence về bất nhất. Viết fixture delimiter và biên ANLS, đối chiếu code scorer trước tuyên bố tương đương official. |
| [Repository tác giả LiGT_VQA](https://github.com/phong-lt/LiGT_VQA) | Có liên kết Google Drive công khai; repository nêu nghiên cứu và CC BY-NC-SA 4.0. | Không coi ReceiptVQA là chỉ có thể xin qua email. Kiểm tra archive/version và điều kiện kèm dữ liệu; quyền tải không tự cho phép mọi mục đích external/commercial. |
| [MC-OCR: dataset chính thức](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) | Quy trình truy cập yêu cầu thỏa thuận đăng ký có chữ ký; phạm vi nghiên cứu. | Chưa có archive/thỏa thuận đã ký trong repo. Kiểm tra label mapping bốn trường KIE từ challenge và archive trước khóa schema Track B. |
| [MC-OCR: challenge chính thức](https://www.rivf2021-mc-ocr.vietnlp.com/challenge) | Đã mở trực tiếp khi cập nhật sổ: KIE có thứ tự `SELLER`, `SELLER_ADDRESS`, `TIMESTAMP`, `TOTAL_COST`; trường thiếu được để rỗng. | Adapter dataset phải giữ nhãn gốc và map rõ sang schema sản phẩm. Không tự điền giá trị/tiền tệ bị thiếu; archive thực vẫn chưa được kiểm kê. |
| [Qwen3-VL-2B-Instruct model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) | Model card khai báo Apache-2.0; candidate student ưu tiên để pilot. | Chưa ghim immutable revision, chưa thử QLoRA/VRAM/độ chính xác tiếng Việt trên RTX 3060. License thuận lợi không phải bằng chứng vừa bộ nhớ. |
| [Qwen2.5-VL-3B-Instruct LICENSE](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE) | License riêng của checkpoint này giới hạn nghiên cứu phi thương mại. | Không suy license từ model Qwen khác; chỉ giữ làm ứng viên nghiên cứu khi mục đích phù hợp. |
| [Vintern-1B-v2 model card](https://huggingface.co/5CD-AI/Vintern-1B-v2) | Có dùng Viet-Receipt-VQA trong training sources. | Có nguy cơ pretraining/SFT contamination với ảnh MC-OCR trong benchmark; dedup dữ liệu mới không loại được kiến thức đã nằm trong weights. Cần audit overlap thực. |
| [PaddleOCR PP-OCRv5 multilingual](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html) | Tài liệu liệt kê tiếng Việt `vi` và recognizer `latin_PP-OCRv5_mobile_rec`. | Candidate OCR; cần ghim engine/detector/recognizer revision và chạy pilot. Không mặc định mọi model PP-OCR đều hỗ trợ tiếng Việt. |
| [Viet-Receipt-VQA dataset](https://huggingface.co/datasets/5CD-AI/Viet-Receipt-VQA) | Truy cập trang bằng công cụ audit trả HTTP 401. | License chưa xác minh; không suy quyền từ model card Vintern hoặc nhãn license của ảnh upstream. Chưa cho phép nhập training pool chỉ dựa trên mô tả overview. |

## Search log bổ sung — 02/11/2026

Nguồn tìm: web search để phát hiện; chỉ dùng paper trên arXiv, PMLR, ACL Anthology và repo/model card tác giả làm bằng chứng. Giữ phiên bản được đọc trong link; không mặc định đó là bản mới nhất. Không tải dataset/weights. Các phần được đọc có chọn lọc được ghi trong matrix; code/scorer chưa tái lập.

| Truy vấn đã dùng | Mục đích / quyết định sàng lọc |
|---|---|
| `ReceiptVQA multimodal large language model benchmark distillation 2025 2026` | Tìm công trình cùng benchmark và receipt understanding gần đây; nhận LiGT và ReceiptBench |
| `document VQA OCR grounded pseudo label filtering distillation small vision language model` | Tìm prior art trực tiếp của lọc/chưng cất; nhận DocVAL |
| `selective prediction large small language model cascade FrugalGPT RouteLLM` | So sánh abstention/cascade và chi phí; nhận FrugalGPT, RouteLLM, SelectiveNet |
| `AutoViVQA Vietnamese visual question answering 2603.09689` | Kiểm tra synthetic QA tiếng Việt; nhận AutoViVQA, nối sang ViTextVQA/ViOCRVQA/Vintern |
| `"DocVAL" "Validated" arxiv` | Tìm full text khi PDF PMLR trả content-type không được web reader hỗ trợ; đọc arXiv v3 |
| `"ReceiptVQA" distillation filtering Vietnamese benchmark` | Kiểm tra công trình/repo cùng dữ liệu; LiGT là nguồn baseline trực tiếp |
| `Vietnamese receipt VQA OCR grounded distillation filtering` | Kiểm tra khoảng trống; phát hiện repo RON-ViT5-Deploy, giữ ở danh sách theo dõi |

Tiêu chí nhận: liên quan trực tiếp Vietnamese text/document VQA, validated distillation, selective prediction/cascade hoặc giới hạn compute của thiết kế. Bài nền tảng cũ vẫn được nhận khi giải thích phương pháp. Trang aggregator/leaderboard chỉ dùng phát hiện, không dùng làm bằng chứng cho kết quả. Không tổng hợp một bảng accuracy giữa các dataset/protocol khác nhau.

## Matrix 12 công trình và hệ quả thiết kế

Số liệu paper là do tác giả báo cáo, **không phải số đo ViDocLens**. “Đọc” ở đây là đọc các phần được chỉ rõ, không khẳng định đã đọc từng phụ lục hoặc kiểm toán mọi kết quả.

| ID / primary source và bản đọc | Phần đọc / phương pháp và evaluation | Hệ quả cho ViDocLens |
|---|---|---|
| P01 [LiGT / ReceiptVQA, v1, 2025](https://arxiv.org/html/2502.19202v1) | Dataset, LayoutHEI, metrics, baseline và ablation: kết hợp OCR/layout/language; đánh giá EM/F1/ANLS trên receipt tiếng Việt. | Baseline trực tiếp của RQ1. Archive thực và serialization đã được kiểm tra riêng; chưa có scorer parity. Không so điểm mới với bài gốc mà bỏ qua OCR/split/normalization. |
| P02 [ViTextVQA, v1, 2024](https://arxiv.org/html/2404.10652v1) | Methodology, OCR, EM/token F1 và setup; dữ liệu scene text, có phân tích tiếng Việt/dấu và cách sắp OCR. | Hỗ trợ nhu cầu kiểm tra OCR/normalization. Scene text khác receipt; không nhập điểm hoặc ngưỡng trực tiếp vào RQ1. |
| P03 [ViOCRVQA, v1, 2024](https://arxiv.org/html/2404.18397v1) | VisionReader, human validation, EM/F1, main results: dùng OCR/object/grid/text trên bìa sách. Main evaluation bỏ genre vì không luôn đọc được từ ảnh. | Phải phân biệt extraction với inference ngoài ảnh; không mặc định mọi câu hỏi có đáp án xuất hiện trong OCR. Domain và compute khác RTX 3060. |
| P04 [Vintern-1B, v1, 2024](https://arxiv.org/html/2408.12480v1) | Architecture, nguồn SFT và benchmark: Gemini sinh QA, training có Viet-Receipt-VQA; dùng GPT-4o judge và một số metric văn bản. | Prior art rõ cho synthetic Vietnamese VQA và model nhỏ. Rủi ro contamination phải audit; điểm judge không tương đương EM. Chưa đo overlap bytes ảnh. |
| P05 [AutoViVQA, v2, 2026](https://arxiv.org/html/2603.09689v2) | Pipeline, quality control, human validation/error analysis: QA tiếng Việt trên ảnh MS COCO, sinh bằng Gemini, kiểm tra ensemble/người. | Không nhận tính mới “tự sinh và lọc QA tiếng Việt”. Cần audit nhãn độc lập và false reject; silver không thành gold chỉ vì qua nhiều model. Domain không phải receipt benchmark. |
| P06 [DocVAL, arXiv v3](https://arxiv.org/html/2511.22521v3), [ICML 2026](https://proceedings.mlr.press/v306/neogi26a.html) | §3–5: spatial CoT, validator và refinement; teacher được condition trên ground-truth annotations; validator có ANLS với gold. ANLS và bbox mAP; OCR/detection dùng lúc training, student chạy không OCR. | Prior art gần nhất. ViDocLens giới hạn gold, teacher input không gold, không có gold bbox ReceiptVQA và có verifier online. Chỉ xem đây là khác biệt protocol cần kiểm nghiệm; không chứng minh novelty. Không chép validator dùng gold vào silver pipeline. |
| P07 [ReceiptBench, ACL 2026, PDF](https://aclanthology.org/2026.acl-long.2135.pdf) | Data/annotation, task decomposition, method và limitations: perception, normalization, reasoning, structure; SFT + metric-aware GRPO; dữ liệu chủ yếu tiếng Anh. | Receipt VLM benchmark và normalization đã có prior art. Giữ Track A raw answer tách Track B normalized JSON; không thêm GRPO/line items ngoài scope chỉ vì paper dùng chúng. |
| P08 [Donut, v5, 2022](https://arxiv.org/html/2111.15664v5) | Method, downstream tasks, OCR comparison và input resolution: image-to-structured-output, SynthDoG; đánh giá cả extraction/DocVQA. | OCR có thể gây lỗi lan truyền; giữ baseline image-only để biết verifier/filter giúp hay cản. Không suy khả năng tiếng Việt từ kết quả ngôn ngữ khác. |
| P09 [QLoRA, v1, 2023](https://arxiv.org/html/2305.14314v1) | NF4, double quantization, paged optimizer, evaluation và limitations; adapter học qua base lượng tử hóa. | Cơ sở chọn phương pháp tiết kiệm bộ nhớ. Bài trên LLM không xác nhận Qwen3-VL với vision tokens vừa 12 GB; inference và backward/save-load vẫn phải thử thật. |
| P10 [FrugalGPT, v1, 2023](https://arxiv.org/html/2305.05176v1) | Cascade, cost/quality và limitations: cascade học từ dữ liệu có nhãn; phụ thuộc phân phối và chi phí học router. | Không nhận “cascade tiết kiệm API” là ý tưởng mới. RQ4 phải cộng OCR/student/router/retry và xem domain shift; không dùng giá API lịch sử làm dự toán hiện tại. |
| P11 [RouteLLM, v4, 2025](https://arxiv.org/html/2406.18665v4) | Preference routing, call-performance trade-off, cost và routing overhead; benchmark LLM văn bản. | Routing theo query khác verifier sau inference; ViDocLens đã trả chi phí student trước fallback. Cần đường cong chi phí/chất lượng thực, không suy call reduction bằng tiết kiệm tiền tương ứng. |
| P12 [SelectiveNet, ICML 2019, PDF](https://proceedings.mlr.press/v97/geifman19a/geifman19a.pdf) | §2, §5, experiments/calibration: selective risk trên phần được trả lời, coverage trên toàn bộ mẫu; calibration dùng validation riêng. | Cơ sở RQ3/RQ4. Báo cả coverage và risk, calibration tách tuning; OCR confidence không tự là xác suất đúng. Bài classification/regression không bảo đảm calibration VQA. |

**Định vị sau khảo sát:** đóng góp dự kiến là thực nghiệm có kiểm soát trên receipt tiếng Việt, dưới giới hạn gold/VRAM: đo chất lượng nhãn, hiệu quả lọc cùng số mẫu/compute, lỗi số và trade-off coverage–cost. “Validated distillation”, “Vietnamese synthetic QA”, “receipt VLM benchmark” và “cascade” đều có prior art; không dùng riêng các cụm này làm tuyên bố mới. RQ1–RQ4 trong SOT vẫn là câu hỏi mở.

### Các nguồn cần theo dõi, không tính là đã review đầy đủ

- [RON-ViT5-Deploy](https://github.com/anngyn/RON-ViT5-Deploy): tìm thấy qua query ReceiptVQA; chưa đọc code, tìm paper hoặc tái lập. Kiểm tra trước final related work vì cùng domain/OCR noise.
- [NTIRE 2026 financial receipt challenge](https://openaccess.thecvf.com/content/CVPR2026W/NTIRE/papers/Guan_NTIRE_2026_Challenge_on_End-to-End_Financial_Receipt_Restoration_and_Reasoning_CVPRW_2026_paper.pdf): xuất hiện khi tìm robustness; chưa review sâu; restoration không thuộc v1.
- Kết quả tìm “Resolution-Aware Knowledge Distillation … Teacher Label Contamination” chưa được đối chiếu full text primary; không dùng claim của nó để chốt thiết kế.

Không có số PRISMA/số bài bị loại được bịa ra: tìm kiếm có chủ đích, không thu thập một corpus tìm kiếm đầy đủ. Trước viết báo cáo cuối phải tìm cập nhật và rà code/supplement của các đối thủ trực tiếp; kết luận Phase 0 chỉ đủ định vị thận trọng.

## Cách ghi bằng chứng

Ghi query, nơi tìm, ngày tìm, phiên bản bài, tiêu chí nhận/loại và link primary source. Đọc phần dữ liệu, evaluation, limitations, phụ lục và code; tách số tác giả báo cáo khỏi số tự tái lập. Đặc biệt kiểm tra hệ thống có dùng cùng split/OCR/normalization hay không.

| Cụm nghiên cứu | Câu hỏi cần trả lời | Tài liệu khởi điểm từ overview | Trạng thái khảo sát |
|---|---|---|---|
| ReceiptVQA | Split, quyền dữ liệu, annotation, official metric, baseline | LiGT / ReceiptVQA, arXiv:2502.19202 | P01 và annotations đã audit; còn ảnh/scorer parity |
| Vietnamese VLM | Dữ liệu pretraining/SFT có chứa ảnh benchmark? | Vintern-1B, arXiv:2408.12480 | Đã thấy nguồn Viet-Receipt-VQA trong model card; chưa đo overlap |
| Vietnamese OCR-VQA | Khác biệt với receipt domain; metric dùng chung được không? | ViTextVQA, ViOCRVQA | Đã đọc chọn lọc P02–P03 |
| Synthetic VQA | Cơ chế sinh nhãn, validation, human audit | AutoViVQA và Viet-Receipt-VQA | P04–P05; quyền nguồn Viet-Receipt-VQA vẫn chưa xác minh |
| Grounded distillation | Filtering có vượt random data selection ở cùng size/compute? | DocVAL | P06; phân biệt gold-aware validator với nhánh không gold của ViDocLens |
| Selective prediction | Calibration, coverage-risk, fallback không có quyền external | SelectiveNet / FrugalGPT / RouteLLM | P10–P12; chưa tái lập trên receipt |
| Model và OCR | Khả năng tiếng Việt, hỗ trợ QLoRA, license và môi trường | Official model cards, PaddleOCR, Transformers/PEFT | Cần pilot thay vì suy từ parameter count |

## Mẫu một mục nghiên cứu

```text
Paper ID, trích dẫn, URL chính thức, version, ngày truy cập:
Query + nguồn phát hiện:
Dataset / split / số ảnh và QA:
License / cách xin dữ liệu / quyền công bố:
Model và training data (đặc biệt ảnh trùng benchmark):
Phương pháp, baseline, ablation:
Metric và normalization chính xác:
Kết quả tác giả báo cáo (bảng/trang), không phải kết quả ViDocLens:
Giới hạn / nguồn nhiễu / nguy cơ leakage:
Liên quan RQ nào; cần thay đổi phát biểu gap nào:
Code / weights / manifest có sẵn:
Quyết định đưa vào hay loại, lý do:
```

## Tiêu chí đóng khảo sát Phase 0

- Có bảng so sánh các công trình gần nhất và các công trình trực tiếp dùng ReceiptVQA.
- Có bằng chứng riêng cho mọi nhận định về dữ liệu, metric và training contamination.
- G1–G4 được viết thành câu hỏi có thể kiểm tra; tính mới chưa chứng minh phải ghi là chưa chứng minh.
- Các hạn chế chưa giải quyết được được đưa vào báo cáo, không xóa khỏi bảng.
