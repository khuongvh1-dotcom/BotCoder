# Hướng dẫn sử dụng (USAGE)

BotCoder cho **Claude tự code theo plan, ngay trong dự án của bạn**.

> Tóm tắt: cài vào dự án → `runbot init` (tạo thư mục `plan/`) → viết plan →
> `runbot run` (chọn plan) → Claude sửa code tại chỗ → chạy test → bạn `git diff` & commit.

> **Xem nhanh các lệnh:** `runbot help`

## Cách dùng nhanh (trong dự án của bạn)

```bash
# 1) Cài tool vào dự án (1 lần)
pip install git+https://github.com/khuongvh1-dotcom/BotCoder.git

# 2) Tạo scaffold: sinh thư mục plan/ + .botcoder/ ngay trong dự án
runbot init

# 3) Viết plan trong plan/ (mỗi plan 1 file .md — xem mục 2)

# 4) Chạy: liệt kê plan, chọn số để chạy
runbot run
```

`runbot run` (không tham số) chạy ở **chế độ local**:
- Liệt kê các plan trong `plan/` (bỏ qua file đã có tiền tố `done_`), cho bạn chọn **số** (1 plan) hoặc `a` (tất cả).
- Claude **sửa code trực tiếp** trong thư mục dự án — **không** clone, **không** tạo PR.
- Chạy lệnh test trong plan; nếu **fail thì Claude tự sửa lại** (fix loop, tối đa `max_fix_attempts`).
- Xong → đổi tên plan `001-x.md` → `done_001-x.md` để lần sau không đọc lại.
- Dừng để bạn tự xem `git diff` rồi `git commit`.

> **Yêu cầu:** dự án phải là **git repo** (`git init` nếu chưa) để bot biết file nào vừa đổi và bạn xem được `git diff`.

### Bảng lệnh

| Lệnh | Ý nghĩa |
|------|---------|
| `init` | Tạo scaffold `plan/` + `.botcoder/` trong **thư mục hiện tại**. |
| `init <repo>` | (nâng cao) Tạo profile `projects/<id>.yaml` cho repo `owner/name` (chế độ GitHub). |
| `run` | Chọn plan trong `plan/` → sửa code tại chỗ + test + fix loop. |
| `run <repo\|đường-dẫn>` | (nâng cao) Chế độ GitHub: clone → PR → CI. `<…>` là `owner/name`, thư mục có remote, hoặc `profile.yaml`. |
| `help` | Hiện hướng dẫn. Cũng chạy bằng `-h` / `--help` / không tham số. |

> `runbot` là lệnh tắt của `python -m src.main` (có sau khi cài). Hai dạng tương đương nhau.

---

## 0. Chuẩn bị một lần

| Việc | Lệnh / cách |
|------|-------------|
| Python 3.10+ | cài Python |
| Cài bot | `pip install git+https://github.com/khuongvh1-dotcom/BotCoder.git` — cài xong có lệnh `runbot`. (Dev: clone repo rồi `pip install -e .[dev]`.) |
| Git | dự án phải là git repo (`git init` nếu chưa) |
| GitHub (chỉ cần cho chế độ PR) | `gh auth login` |
| Claude | đăng nhập `claude` CLI (gói Pro/Max) — SDK dùng luôn login này |

Kiểm tra Claude chạy được:
```
python scripts/check_auth.py
```

> Lưu ý: nếu shell báo `python` không tìm thấy, dùng đường dẫn đầy đủ
> `C:\Users\DELL\AppData\Local\Programs\Python\Python312\python.exe` hoặc mở
> terminal mới.

---

## 1. (Nâng cao — chế độ GitHub) Trỏ bot vào repo

> Phần này **chỉ cần cho chế độ GitHub** (`run owner/name` → clone + PR). Nếu bạn
> dùng chế độ local (`runbot run` trong dự án) thì **bỏ qua mục này** — không cần profile.

Mỗi repo đích = **một profile** trong `projects/<id>.yaml`. Có 2 cách tạo:

### Cách A — Tự động (khuyên dùng)
```
runbot init OWNER/TEN_REPO --stack python
```
- `OWNER/TEN_REPO` : repo trên GitHub dạng `owner/name` (vd `khuongvh1-dotcom/my-app`).
- `--stack`: `python` | `node` | `flutter` | `generic` — chọn preset lệnh test + vùng cấm.
- (tuỳ chọn) `--id ten-profile`, `--base-branch master`, `--overwrite`.

Lệnh sẽ tự lấy owner/tên/URL/nhánh-mặc-định từ GitHub và ghi `projects/<id>.yaml`.

> **Mẹo:** thường không cần chạy `init` riêng — cứ `run owner/name` là bot tự tạo
> profile nếu chưa có (xem mục 3). Dùng `init` khi muốn tạo profile trước để
> chỉnh `commands.test` / `paths.danger` rồi mới chạy.

### Cách B — Thủ công
Copy `projects/sandbox.yaml`, sửa các trường (xem [03-configuration](03-configuration.md)).

### Sau khi tạo: kiểm tra lại profile
Mở `projects/<id>.yaml`, chỉnh cho đúng repo:
```yaml
commands:
  test: "pytest"            # ĐỔI cho đúng lệnh test repo bạn (npm test, flutter test...)
paths:
  danger:                   # vùng KHÔNG cho AI tự sửa (auth, migration, CI...)
    - ".github/**"
    - "..."
```

> **Quan trọng**: `commands.test` và `paths.danger` quyết định bot kiểm tra và bảo vệ
> repo thế nào. Điền đúng cho stack của bạn.

### Điều kiện ở repo đích
Repo đích nên có sẵn:
- **CI chạy test** (GitHub Actions) — tên job khớp `config/rules.yaml` → `ci.required_checks` (mặc định `test`).
- (nên có) `AI_PROJECT_CONTEXT.md` ở gốc repo: mô tả kiến trúc, lệnh build/test, quy ước, file cấm. Bot đọc file này để Claude hiểu repo.

---

## 2. Viết plan

Tạo file `.md` trong thư mục `plan/` (vd `plan/001-them-subtract.md`). Mỗi file là một
plan; mỗi task là một block `## TASK NNN: ...`:

```
## TASK 001: Thêm hàm subtract
Risk: safe
Repo: my-app
Allowed paths:
- calc.py
- tests/test_calc.py
Forbidden paths:
- .github/**
Goal: Thêm hàm subtract(a, b) trả về a - b. Giữ nguyên hàm cũ.
Acceptance criteria:
- subtract(5, 3) == 2
- pytest pass
Test commands:
- pytest
```

Các trường quan trọng nhất:
- **Allowed paths** — Claude CHỈ được sửa các file này (path_guard chặn phần còn lại).
- **Forbidden paths** — tuyệt đối không đụng.
- **Risk** — `safe`/`medium_risk`/`high_risk`. Task `high_risk` (auth, payment, DB migration…) sẽ bị **BLOCKED** chờ bạn duyệt, không tự code.
- **Goal / Acceptance criteria** — mô tả rõ để Claude làm đúng.

Đầy đủ trường + cách viết: [03-configuration](03-configuration.md).

---

## 3. Chạy

### 3a. Chế độ local (mặc định — khuyên dùng)

Trong thư mục dự án (đã `runbot init`):
```
runbot run                         # liệt kê plan/, chọn số hoặc 'a'
runbot run --plan plan/001-x.md    # chạy thẳng 1 plan, bỏ bước chọn
runbot run --all                   # chạy hết plan chưa done, không hỏi
```
Claude sửa code **tại chỗ** → chạy test → fail thì tự sửa lại → đổi tên plan thành
`done_…`. Xong bạn tự `git diff` và `git commit`. Không tạo PR.

### 3b. Chế độ GitHub (nâng cao)

Truyền **đường dẫn/đối tượng repo** để bật luồng clone → PR → CI:
```
runbot run owner/my-app            # repo GitHub: tự tìm/tạo profile
runbot run C:\code\my-app          # thư mục có remote 'origin'
runbot run projects/<id>.yaml      # profile có sẵn
```

Tham số `run`:
- `--plan FILE` : chạy thẳng 1 file plan (bỏ bước chọn).
- `--rules FILE`: luật (mặc định `.botcoder/rules.yaml` nếu có).
- `--state FILE`: file state (mặc định `.botcoder/state.json` nếu có).
- `--stack`     : preset — **chỉ dùng khi phải tạo profile mới** (chế độ GitHub).

> Chế độ GitHub tạo PR nên thư mục/đối tượng **bắt buộc** gắn với một repo GitHub.

Chế độ GitHub in log từng bước:
```
task 001: -> classified (risk=safe)
task 001: -> issue_created (issue #N)
task 001: -> dispatched (branch ai-task/001-...)
task 001: -> changes_ready (... files changed)
task 001: -> security_check (policy passed)
task 001: -> pr_open (PR #N)
task 001: -> ci_running -> ci_passed
task 001: -> human_review (PR #N ready for human review)
```

Bot **dừng ở human_review** — KHÔNG tự merge.

---

## 4. Đọc kết quả & duyệt

1. **Xem PR**: bot tạo PR trên repo đích. Mở trên GitHub hoặc:
   ```
   gh pr view <N> --repo OWNER/REPO
   gh pr diff <N> --repo OWNER/REPO
   ```
2. **Kiểm tra CI**: PR có checks pass chưa.
3. **Duyệt code**: đọc diff. Nếu ổn → **merge** (bạn quyết định):
   ```
   gh pr merge <N> --repo OWNER/REPO --squash --delete-branch
   ```
4. **Audit trail**: mọi thứ Claude làm được ghi ở `runs/<ngày>/task-NNN/`
   (prompt đã gửi, tóm tắt, file đổi, kết quả CI, quyết định).

---

## 5. Khi CI fail (fix loop tự động)

Nếu CI fail, bot tự gửi tóm tắt lỗi cho Claude và yêu cầu sửa, lặp tối đa
`max_fix_attempts` lần (mặc định 3, trong `config/rules.yaml`). Hết lượt mà vẫn
fail → task `FAILED`, dừng để bạn xử lý tay.

---

## 6. Khi task bị BLOCKED

Bot dừng task và báo `BLOCKED` khi:
- Task `high_risk` (chạm auth/payment/migration/sync…) → cần bạn duyệt thủ công.
- Claude sửa file **ngoài Allowed paths** hoặc trong **Forbidden/danger paths**.
- Phát hiện **secret** trong file thay đổi.

Xem lý do trong log (`reason=...`) và `runs/<ngày>/task-NNN/policy.json`. Sửa plan
(mở rộng Allowed paths, hạ Risk nếu thực sự an toàn) rồi chạy lại.

---

## 7. Chạy lại an toàn (idempotent)

Chạy lại cùng lệnh KHÔNG tạo issue/PR trùng — bot đọc `state.json` và tiếp tục
từ trạng thái hiện tại. Task đã ở `human_review`/`done`/`blocked` thì bỏ qua.

Muốn chạy **mới hoàn toàn** một task: xóa state + workspace của nó:
```
Remove-Item state.json, workspace\task-001 -Recurse -Force
# và đóng PR/branch/issue cũ nếu muốn:
gh pr close <N> --repo OWNER/REPO --delete-branch
```

---

## 8. Ví dụ trọn vẹn (đã chạy thật)

Trỏ vào repo `khuongvh1-dotcom/ai-sandbox`, thêm hàm subtract:

```
# 1) tạo profile (1 lần, tuỳ chọn — run cũng tự tạo được)
runbot init khuongvh1-dotcom/ai-sandbox --id sandbox --stack python --overwrite

# 2) viết plans/plan2.md (task subtract) — xem mục 2

# 3) chạy (trỏ thẳng vào repo owner/name, hoặc profile, hoặc thư mục local)
runbot run khuongvh1-dotcom/ai-sandbox --plan plans/plan2.md --state state2.json

# 4) kết quả: PR #7, CI SUCCESS, mergeable — duyệt rồi merge
gh pr diff 7 --repo khuongvh1-dotcom/ai-sandbox
gh pr merge 7 --repo khuongvh1-dotcom/ai-sandbox --squash --delete-branch
```

Kết quả thực tế: Claude thêm `subtract(a, b)` vào `calc.py` (giữ nguyên `add`),
thêm `test_subtract`, CI pass, dừng chờ duyệt.

---

## 9. Lỗi thường gặp

| Triệu chứng | Xử lý |
|-------------|-------|
| `python` không tìm thấy | Dùng đường dẫn đầy đủ tới python.exe, hoặc mở terminal mới |
| CI luôn fail dù code đúng | Kiểm tra repo đích có chạy test đúng (vd Python cần `pytest.ini` với `pythonpath = .`) |
| Task BLOCKED vì path | Mở rộng `Allowed paths` trong plan cho khớp file Claude cần sửa |
| `required_checks` không khớp | Đổi `config/rules.yaml` → `ci.required_checks` cho khớp tên job CI repo đích |
| Claude bị cắt "max turns" | Tăng `budget.max_claude_turns_per_task` trong `config/rules.yaml` |

Chi tiết hơn: [05-development.md](05-development.md).

---

## Xem thêm
- Toàn bộ tham số cấu hình: [03-configuration.md](03-configuration.md)
- Hiểu hệ thống: [01-architecture.md](01-architecture.md)
- Nâng cấp về sau: [06-roadmap.md](06-roadmap.md)
