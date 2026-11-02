# Quy trình làm việc với ViDocLens

Đọc [SOT](SOURCE_OF_TRUTH.md) để biết yêu cầu; mở [STATUS](docs/STATUS.md) để biết đang ở đâu. **Chủ dự án tự kết nối remote, commit và push thủ công. Assistant chuẩn bị thay đổi, chạy kiểm tra và bàn giao; không tự publish/sync/upload code lên GitHub.** Không cài hook hoặc đổi Git config toàn máy trong quy trình này.

## Một nơi cho mỗi loại thông tin

| File | Trách nhiệm |
|---|---|
| `SOURCE_OF_TRUTH.md` | Thiết kế, phạm vi, gate của từng phase |
| `docs/STATUS.md` | Bảng phase hiện hành, việc kế tiếp, blocker, kết quả kiểm tra và bàn giao mới nhất |
| `docs/STATUS_HISTORY.md` | Nhật ký cũ, giữ mốc và bằng chứng; không dùng làm hiện trạng |
| `docs/DECISIONS.md` | Vì sao đổi thiết kế/phạm vi; sửa cùng SOT |
| `CHANGELOG.md` | Thay đổi đáng chú ý theo phiên bản; không thay nhật ký experiment |
| Issue / mẫu task | Mục tiêu, điều kiện hoàn tất, kiểm tra cho một việc cụ thể |

Không tính tiến độ toàn dự án bằng trung bình số checkbox hoặc số phase. Phase chỉ `done` khi đủ gate và bằng chứng; code xong không đồng nghĩa đã push, CI xanh, train hay deploy.

## Vòng đời công việc

1. Chọn một việc từ STATUS, xác định phase và tiêu chí nghiệm thu; dùng [mẫu task](docs/templates/TASK.md) hoặc GitHub Issue. Việc nhỏ có thể ghi trực tiếp ở STATUS.
2. Tạo nhánh cho một mục tiêu, triển khai thay đổi trong phạm vi đó. Không mở khóa test gold hoặc tự gọi API trả phí để hoàn thành checklist.
3. Chạy kiểm tra phù hợp và review diff. Contract thay đổi phải xuất lại schema. Thay thiết kế/phạm vi phải cập nhật SOT + ADR.
4. Cập nhật STATUS: đã làm gì, lệnh/kết quả, hạn chế, việc kế tiếp. Chỉ cập nhật CHANGELOG khi có thay đổi đáng chú ý, không thêm một entry cho mọi lần sửa typo.
5. Chủ dự án review/stage/commit/push. Sau push, kiểm CI và tạo PR nếu dùng nhánh; chỉ ghi CI đạt sau khi xem run thực tế.
6. Trước merge, kiểm tiêu chí nghiệm thu. Sau merge, cập nhật commit/PR/run liên quan khi đã tồn tại; không điền hash hoặc URL giả.

Task dùng `planned → in_progress → in_review → done`; `blocked` phải ghi nguyên nhân, người xử lý và điều kiện gỡ, sau đó trở về trạng thái phù hợp. `in_review` nghĩa là đã có thay đổi cụ thể chờ kiểm tra. Phase `done` có gate riêng trong SOT; phase chưa triển khai giữ `planned` dù một dependency đang mở. GitHub upload/CI có trạng thái riêng trong STATUS.

## Branch và commit

`main` giữ bản tích hợp. Sau commit đầu tiên, dùng nhánh ngắn cho một task: `codex/phase2-teacher-contract`, `codex/fix-anls-boundary`, `codex/docs-data-card`. Prefix `codex/` là quy ước repo, người dùng cũng có thể dùng cùng quy ước. Không cần thêm nhánh `develop` cho dự án hiện tại. Commit đầu tiên trực tiếp trên local `main` là ngoại lệ bootstrap.

Theo [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <mô tả thay đổi>
```

Scope không bắt buộc; tiêu đề nên bằng tiếng Anh, dùng động từ rõ, không chấm cuối, mục tiêu dưới 72 ký tự. Đây là quy ước repo, không phải mọi yêu cầu của specification. Body có thể tiếng Việt/Anh, giải thích lý do/validation khi cần. Dùng `!` hoặc footer `BREAKING CHANGE:` khi thật sự thay contract không tương thích.

| Type | Dùng khi | Ví dụ |
|---|---|---|
| `feat` | Thêm khả năng | `feat(teacher): add provider response contract` |
| `fix` | Sửa lỗi | `fix(eval): preserve leading zeros in references` |
| `refactor` | Đổi cấu trúc, giữ hành vi | `refactor(ocr): isolate cache serialization` |
| `test` | Thêm/sửa tests | `test(data): reject quarantined gold access` |
| `docs` | Tài liệu | `docs(status): record teacher pilot evidence` |
| `ci` | Workflow kiểm tra | `ci: check generated schema drift` |
| `build` / `chore` | Dependency/đóng gói/bảo trì | `chore(repo): add issue templates` |

Một commit nên phục vụ một mục tiêu; tránh `update`, `fix all`, `done phase 2` khi thiếu bằng chứng. PR title theo cùng quy ước; squash merge phù hợp khi nhiều commit chỉ cùng một task. Không tạo release tag chỉ vì kết thúc phase; release theo [checklist](docs/RELEASE_CHECKLIST.md).

## Commit đầu tiên

Repo hiện đã có code và kết quả Phase 0–1 nên dùng:

```text
feat: add ViDocLens foundation and phase 1 pipeline
```

Body tùy chọn:

```text
Add project contracts, guarded data loaders, OCR/evaluation tooling,
and AI-assisted Phase 1 review with documented limitations.

Document phase gates, environment locks, and the manual GitHub workflow.
Keep datasets, model weights, caches, and private run artifacts local.
```

Đây là import mốc hiện có, không tạo lịch sử commit giả cho các lượt thực thi trước.

## Checklist local và push thủ công

Các lệnh dưới dành cho **bạn tự chạy**. Assistant không tự stage/commit/push khi chỉ được yêu cầu nâng cấp repo. Tại root, dùng `.venv/Scripts/python.exe` trên Windows; Linux thay bằng interpreter venv tương ứng.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/export_schemas.py --check
.\.venv\Scripts\python.exe scripts/check_repo.py
```

Chỉ sửa tài liệu: kiểm nội dung/liên kết/UTF-8; không cần chạy ML/GPU hoặc viết test cho câu chữ. `check_repo.py` kiểm tên/loại/kích thước file sẽ vào Git và cú pháp YAML trong worktree; **không là secret scanner hoặc chứng nhận quyền dữ liệu**. Rà nội dung diff trước commit; không đưa secret thật vào `.env.example`.

Trước commit đầu tiên, kiểm `git status --short --untracked-files=all` và danh sách từ `git ls-files --others --exclude-standard`. Các path `data/`, `artifacts/` có thể chỉ chứa README/.gitkeep; xem file cụ thể trước khi stage.

```powershell
git status --short --untracked-files=all
git add .
.\.venv\Scripts\python.exe scripts/check_repo.py --staged
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "feat: add ViDocLens foundation and phase 1 pipeline"
```

Chỉ chạy `git add .` sau review và policy check; các lần sau ưu tiên `git add <file>` theo task. Không dùng `git add -f` để đưa dữ liệu/weights vào repo. Nếu đã stage nhầm file trước commit đầu, dùng `git rm --cached -- <file>` để bỏ khỏi index và giữ file local; repo đã có HEAD có thể dùng `git restore --staged -- <file>`.

Sau khi **bạn** kết nối đúng remote và kiểm `git remote -v`/branch, bạn tự chạy `git push -u origin main` cho lần đầu; các nhánh sau tự push tên nhánh và mở PR. Không force-push `main`. Nếu remote có commit khác, dừng để kiểm lịch sử và tích hợp đúng, không ép ghi đè.

Trên GitHub, sau khi CI thực sự chạy, chủ dự án có thể bật rule bảo vệ `main`: PR, required checks đúng tên job đã xuất hiện, chặn force push/deletion nếu tài khoản hỗ trợ. Đây là cấu hình đề xuất, **chưa được bật bằng việc thêm file local**. Không bắt buộc một approval từ người thứ hai khi chỉ có một maintainer.

## Definition of Done và bàn giao

- Điều kiện nghiệm thu của task đạt, có đường dẫn evidence hoặc lệnh/kết quả thực tế.
- Tests liên quan đạt; phần không chạy được ghi rõ, không lấy CI CPU làm bằng chứng GPU/deployment.
- Contracts/schema/config/docs nhất quán; SOT/ADR cập nhật nếu cần.
- STATUS có hạn chế và bước tiếp theo; labels AI giữ provenance, không nhận là human gold.
- Diff không có dataset/ảnh/weights/cache/credentials; dữ liệu bị ignore có kế hoạch sao lưu riêng.
- Trạng thái local, commit, push, GitHub CI và release ghi riêng; chủ dự án vẫn là người push.

Các liên kết `data/`, `artifacts/`, `cache/`, `reports/` trong báo cáo chỉ mở trên máy có evidence local; không mong chúng xuất hiện trên GitHub. Mẫu Issue/PR tuân theo [cơ chế template của GitHub](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates); chỉ xuất hiện sau khi chủ dự án đưa chúng lên default branch.
