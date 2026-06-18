# 03 — Configuration

3 nguồn cấu hình + auth. Tất cả validate bằng pydantic ([`src/config.py`](../src/config.py)).

---

## 1. Project Profile — `projects/<id>.yaml`

Mỗi **repo đích** một profile. Cho phép dùng bot cho nhiều dự án mà không sửa code.

```yaml
project:
  id: sandbox                 # định danh profile
  name: AI Sandbox
  type: python                # python | flutter_supabase | ...

repo:
  owner: khuongvh1-dotcom
  name: ai-sandbox
  url: https://github.com/khuongvh1-dotcom/ai-sandbox.git
  base_branch: main

branch_prefix: "ai-task/"     # branch = ai-task/001-<slug>

labels:
  task: ai-task               # label gắn cho issue
  pending: pending

commands:                     # lệnh đặc thù repo (đưa vào context cho coder)
  install: "pip install -e ."
  test: "pytest"

paths:
  danger:                     # gộp vào forbidden khi review (chặn cứng)
    - ".github/**"
    - "pyproject.toml"
  readonly:
    - "docs/**"

context_file: AI_PROJECT_CONTEXT.md   # đọc từ repo đích, ghép vào prompt
workspace_dir: workspace              # nơi clone per-task
```

Profiles có sẵn: `projects/sandbox.yaml` (MVP), `projects/bts.yaml` (mẫu Flutter, cần điền `CHANGE_ME`).

**Thêm repo mới — cách nhanh (khuyên dùng)**:
```
runbot init OWNER/NAME --stack python
```
Tự lấy owner/name/url/base_branch từ GitHub (qua `gh`) + áp preset theo `--stack`
(`python`/`node`/`flutter`/`generic`: lệnh test + danger paths), ghi `projects/<id>.yaml`.
Sau đó mở file chỉnh `commands.test` + `paths.danger` cho đúng repo. Xem [USAGE](USAGE.md) mục 1.

**Cách thủ công**: copy `sandbox.yaml`, đổi `repo.*`, `commands`, `paths.danger`.

---

## 2. Rules — `config/rules.yaml`

Quy tắc dùng chung (không gắn repo). **Khai đủ cho song song; MVP đặt sequential.**

```yaml
ci:
  required_checks: [test]         # tên check phải pass (khớp tên job trong CI repo đích)
  poll_interval_seconds: 15
  timeout_seconds: 900

fix_loop:
  max_fix_attempts: 3             # vượt → FAILED (chống loop vô hạn)

merge:
  auto_merge: false               # MVP: KHÔNG auto-merge

budget:
  max_tasks_per_run: 1            # MVP chạy 1 task/lần
  max_claude_turns_per_task: 15   # giới hạn turn của Claude (đã nâng từ 5)
  max_runtime_minutes_per_task: 30

execution:                        # MVP: sequential; v0.3 đổi parallel
  mode: sequential                # sequential | parallel
  max_parallel_tasks: 1
  max_parallel_per_repo: 1
  max_parallel_high_risk: 0
  allow_parallel_safe_tasks: true

locks:                            # đọc ở MVP nhưng chưa dùng (tuần tự)
  enable_path_lock: true
  enable_conflict_group_lock: true

plans:
  input_glob: "plans/**/*.md"     # v0.2 (plan_loader) dùng; MVP đọc 1 file --plan
  allow_multiple_plans: true

risk_rules:                       # keyword cho task_classifier
  high_risk: [database migration, auth, payment, storage delete, sync queue, RLS, production config]
  safe:      [docs, UI text, tests, pure function]

dispatch:
  backend: sdk                    # sdk (MVP) | action (cloud) | openhands (sau)
  claude:
    allowed_tools: [Read, Write, Edit, Bash]
    permission_mode: acceptEdits
```

**Chỉnh thường gặp**:
- CI hay timeout → tăng `ci.timeout_seconds`.
- Claude bị cắt giữa chừng ("max turns") → tăng `budget.max_claude_turns_per_task`.
- Muốn bot làm nhiều task/lần → tăng `budget.max_tasks_per_run` (vẫn tuần tự ở MVP).

---

## 3. Plan format — `plans/plan.md`

Mỗi task = 1 block `## TASK NNN: title`. Field thiếu → default.

```
## TASK 001: Implement add function
Risk: safe                    # safe | medium_risk | high_risk (ưu tiên hơn classifier)
Repo: ai-sandbox
Parallel: true                # v0.3 honor; MVP lưu nhưng bỏ qua
Depends on:
- none                        # "none" bị bỏ; hoặc liệt kê id task khác
Conflict group: core          # v0.3 dùng để khóa
Estimated size: small         # small | medium | large
Agent type: coder             # coder | tester | reviewer | doc | security
Allowed paths:                # path_guard: CHỈ sửa các path này
- calc.py
- tests/test_calc.py
Forbidden paths:              # path_guard: KHÔNG đụng
- .github/**
- pyproject.toml
Goal: Hoàn thiện hàm add(a, b) trả về a + b.
Acceptance criteria:
- add(2, 3) == 5
- pytest pass
Test commands:
- pytest
Rollback note: revert branch nếu fail.
```

Default khi thiếu field: `parallel=false, depends_on=[], conflict_group=null, agent_type=coder`.
Block heading thường (`## Làm gì đó`) cũng parse được — title + body thành task, còn lại default.

---

## 4. Company policy — `company/AI_COMPANY_POLICY.md`

Văn bản policy ghép vào **đầu mọi prompt** gửi coder (tầng 1/5). Quy định: chỉ sửa allowed paths, không commit secret, không đụng high-risk khi task không yêu cầu, thêm test, không tự commit/push.

## 5. Project context — `<repo>/AI_PROJECT_CONTEXT.md`

Đặt trong **repo đích** (không phải repo bot). Ghép vào prompt (tầng 2/5): kiến trúc, lệnh build/test, quy ước, file cấm. Bot đọc từ workspace sau khi clone.

---

## 6. Auth — Claude & GitHub

### Claude (cho dispatcher SDK) — thứ tự ưu tiên
1. `ANTHROPIC_API_KEY` (pay-as-you-go) — **thắng nếu set**.
2. `CLAUDE_CODE_OAUTH_TOKEN` — token gói Pro/Max, tạo bằng `claude setup-token`.
3. **Login Claude Code CLI sẵn có** — SDK kế thừa session. **Không cần env var nào** nếu `claude` đã đăng nhập.

> Người dùng hiện tại dùng **gói subscription** (không API key) → chỉ cần `claude` CLI đã login là chạy được. Usage tính vào giới hạn gói. Nếu cả API key + OAuth token cùng set → API key thắng (tốn credits).

Tạo OAuth token cho CI/máy khác:
```bash
claude setup-token          # in ra token sk-ant-oat01-...
# đặt vào .env: CLAUDE_CODE_OAUTH_TOKEN=...
```
Kiểm tra auth: `python scripts/check_auth.py`.

### GitHub
- Ưu tiên `gh auth login` (đang dùng account `khuongvh1-dotcom`).
- Hoặc `GITHUB_TOKEN` trong `.env` (scope `repo` + `workflow`).

### `.env`
Copy từ `.env.example`, điền giá trị cần. **Không commit `.env`** (đã có trong `.gitignore`; thêm `secret_scanner` chặn lớp 2).
