# Changelog

## v0.2.0 — Local mode + scaffold (2026-06-18)

Đổi mô hình sử dụng: cài tool vào dự án của bạn rồi điều khiển từ bên trong.

### Đã thêm
- **Lệnh tắt `runbot`** = `python -m src.main` (console script trong `pyproject.toml`).
- **`runbot init`** — sinh scaffold `plan/` + `.botcoder/` (rules/policy/context mặc định nhúng trong code) ngay trong thư mục dự án. [`src/scaffold.py`]
- **Chế độ local** (`runbot run` không tham số) — liệt kê plan trong `plan/`, cho chọn số hoặc `a`; Claude sửa code **trực tiếp** trong thư mục (không clone/PR); chạy test; **fix-loop** khi fail; xong đổi tên plan thành `done_…`. [`src/main.py` `process_task_local`]
- **`run <đường-dẫn>` thông minh** (chế độ GitHub, nâng cao) — nhận thư mục local, repo `owner/name`, hoặc `profile.yaml`; tự tìm/tạo profile. [`src/init_project.py` `resolve_profile`]
- Lệnh **`help`** tiếng Việt; output UTF-8 an toàn trên console Windows.

### Đổi
- `init-project` → **`init`** (giữ alias `init-project`).
- Plan mặc định đọc từ `plan/` (số ít) thay vì `plans/`.

## v0.1.1 — MVP (2026-06-18)

Phiên bản đầu tiên. Vòng end-to-end đã chạy thật và verify trên repo sandbox
`khuongvh1-dotcom/ai-sandbox` (PR có CI `SUCCESS`, mergeable, dừng ở human review).

### Đã thêm

**Core orchestration**
- State machine tuần tự đầy đủ: `PENDING → CLASSIFIED → ISSUE_CREATED → DISPATCHED → CHANGES_READY → SECURITY_CHECK → PR_OPEN → CI_RUNNING → CI_PASSED/CI_FAILED → POLICY_REVIEW → HUMAN_REVIEW` (+ `FAILED`/`BLOCKED`). [`src/main.py`]
- Idempotent + resumable qua `state.json` (atomic, schema v2). [`src/state_store.py`]
- Fix-loop: gửi tóm tắt lỗi CI cho Claude, retry tới `max_fix_attempts` rồi FAILED.

**Đầu vào**
- Plan parser format chuẩn (TASK heading + field), fallback heading thường. [`src/plan_parser.py`]
- Risk classifier rule-based (ưu tiên Risk khai, upgrade declared-safe nếu chạm high-risk). [`src/task_classifier.py`]

**Trigger coder**
- Dispatcher interface + prompt builder 5 tầng (company policy → project context → task → rules → CI feedback). [`src/dispatcher/base.py`]
- SDK backend qua `claude-agent-sdk` headless; auth kế thừa login Claude Code CLI (gói Pro/Max), hoặc OAuth token, hoặc API key. [`src/dispatcher/sdk_dispatcher.py`]

**Git & GitHub**
- git_ops (clone/branch/commit/push/PR qua git+gh), lọc artifact `__pycache__`/`.pyc`. [`src/git_ops.py`]
- github_client (label, issue idempotent qua marker, check runs, comment) qua PyGithub. [`src/github_client.py`]

**Kiểm soát**
- path_guard (glob gitignore-style, chặn ngoài allowed/forbidden). [`src/security/path_guard.py`]
- secret_scanner (regex key/token/private-key/.env, redact). [`src/security/secret_scanner.py`]
- policy_reviewer (gộp path + secret + risk gate). [`src/reviewers/policy_reviewer.py`]
- ci_watcher (poll checks, summarize failures; time injectable). [`src/ci_watcher.py`]
- reviewer.decide_next (transition thuần). [`src/reviewer.py`]

**Audit & config**
- audit_logger ghi `runs/<date>/task-NNN/` (prompt/summary/diff/ci/policy/decision). [`src/audit_logger.py`]
- Project profiles (`projects/sandbox.yaml`, `projects/bts.yaml`), `config/rules.yaml`, `company/AI_COMPANY_POLICY.md`.
- `scripts/check_auth.py` kiểm tra auth Claude.

**Forward-compatible (khai sẵn, chưa dùng đầy đủ)**
- `Task` fields: parallel/depends_on/conflict_group/agent_type/estimated_size.
- `rules.execution/locks/plans`; state `plans{}` + `plan_id`.
- Stub: `plan_loader` (v0.2), `dispatcher/action_dispatcher` (cloud), `reviewers/ai_reviewer` (v0.4), `scheduling/*` (v0.3), `agents/*` (v0.4).

**CLI**
- Subcommand `run` (mặc định) + `init-project` (tạo `projects/<id>.yaml` cho repo đích, tự lấy thông tin qua `gh`, preset theo `--stack`). [`src/init_project.py`, `src/main.py`]

**Test & docs**
- 50 unit test (offline + git_ops + init_project). [`tests/`]
- Tài liệu đầy đủ trong [`docs/`](docs/README.md) + [HDSD tiếng Việt `docs/USAGE.md`](docs/USAGE.md).

### Quyết định chính
Xem [docs/07-decisions.md](docs/07-decisions.md). Nổi bật: bot điều phối (không tự viết
agent), SDK backend cho MVP, không auto-merge, security gate trước commit, forward-compatible.

### Lỗi đã xử lý
Python/winget setup, SDK async-gen error, artifact filter, pytest pythonpath, BOM trong
file seed, idempotency eventual-consistency, UTF-8 đọc state. Chi tiết: [docs/05-development.md](docs/05-development.md).

### Chưa làm (theo lộ trình)
Nhiều plan, cloud/cron, song song, subagent chuyên môn, auto-merge, SQLite, UI.
Xem [docs/06-roadmap.md](docs/06-roadmap.md).
