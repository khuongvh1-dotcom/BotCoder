# 02 — Modules

Chi tiết từng module trong `src/`. Mỗi mục: **trách nhiệm**, **hàm/lớp chính**,
**phụ thuộc**, và **gợi ý mở rộng**.

> Quy ước: module "online" cần mạng (GitHub/Claude); module "offline" thuần logic,
> được unit-test không cần mạng.

---

## Lõi dữ liệu

### `models.py` (offline)
**Trách nhiệm**: định nghĩa toàn bộ kiểu dữ liệu trung tâm (pydantic).
- `TaskStatus` — enum vòng đời task (đầy đủ, gồm cả state v0.3+).
- `RiskLevel` — `safe | medium_risk | high_risk | blocked`.
- `AgentType` — `coder | tester | reviewer | doc | security` (MVP chỉ dùng `coder`).
- `Task` — model task. **Khai đủ field forward-compatible** ngay từ đầu: `id, plan_id, title, file, body, status, risk, risk_declared, agent_type, parallel, depends_on, conflict_group, estimated_size, allowed_paths, forbidden_paths, goal, acceptance_criteria, test_commands, rollback_note` + bookkeeping (`issue_number, branch, pr_number, fix_attempts, last_ci_conclusion, run_dir, updated_at`).
- `DispatchResult`, `CIResult`, `CIConclusion`, `EstimatedSize`.

**Mở rộng**: thêm field vào `Task` an toàn (pydantic có default) — không phá state cũ.

### `config.py` (offline)
**Trách nhiệm**: load + validate `projects/*.yaml` (Profile) và `config/rules.yaml` (Rules) bằng pydantic, fail sớm nếu sai.
- `load_profile(path) -> Profile`, `load_rules(path) -> Rules`.
- Sub-models: `Profile, RepoMeta, Labels, PathRules`; `Rules, CIRules, FixLoopRules, MergeRules, BudgetRules, ExecutionRules, LockRules, PlansRules, RiskRules, DispatchRules`.
- `RepoMeta.full_name` = `owner/name`.

**Mở rộng**: thêm khóa cấu hình = thêm field vào model tương ứng + cập nhật YAML mẫu.

### `state_store.py` (offline)
**Trách nhiệm**: persist `state.json` atomic, idempotency, resumable.
- `State` (pydantic): `version=2, repo, updated_at, plans{plan_id: PlanRef}, tasks{id: Task}`.
- `StateStore.load() / .save()` — save ghi `.tmp` rồi `os.replace` + `fsync` (atomic).
- `State.get_task / .upsert_task` (upsert tự stamp `updated_at`).
- `utcnow_iso()` helper.

**Mở rộng v0.2+**: khi số task lớn → thay JSON bằng SQLite, giữ nguyên interface `load/save/upsert`.

---

## Đầu vào: plan → task

### `plan_parser.py` (offline) — *file lớn nhất sau main, parsing là trọng tâm*
**Trách nhiệm**: đọc `plan.md` (format chuẩn) → `list[Task]`; ghi `tasks/NNN_task.md`.
- `parse_plan(path, plan_id) -> list[Task]` — tách theo heading `## `, đọc field `Risk/Repo/Parallel/Depends on/Conflict group/Estimated size/Agent type/Allowed paths/Forbidden paths/Goal/Acceptance criteria/Test commands/Rollback note`. Field thiếu → default. Heading `## TASK 001: title` → id `001`; heading thường → fallback id tự tăng.
- `write_task_files(tasks, dir)` — idempotent (skip nếu nội dung trùng).
- `plan_hash(path)` — sha256 để phát hiện plan đổi.
- Nội bộ: `_split_blocks, _parse_fields, _build_task` (xử lý scalar field + list field `- item`).

**Mở rộng v0.2**: phân rã plan bằng LLM thay vì tách heading cơ học.

### `plan_loader.py` (offline) — **stub v0.2**
**Trách nhiệm (tương lai)**: gom `plans/**/*.md`, gán `plan_id` theo tên file.
- `load_all(input_glob) -> list[Task]`. MVP chưa dùng (main đọc 1 file `--plan`).

### `task_classifier.py` (offline)
**Trách nhiệm**: gán `RiskLevel` rule-based (không LLM).
- `classify(task, risk_rules) -> RiskLevel`.
- Logic: ưu tiên `Risk` khai trong plan; nhưng declared-`safe` mà chạm keyword/path high-risk → **upgrade lên high_risk**. Không khai → suy ra từ `risk_rules.high_risk`/`safe` match trên title+goal+body+paths; không match → `medium_risk`.

**Mở rộng v0.2**: LLM classifier (đọc task, gán risk thông minh hơn) — giữ cùng signature.

---

## Trigger coder (dispatcher)

### `dispatcher/base.py` (offline cho prompt-builder)
**Trách nhiệm**: interface `Dispatcher(ABC)` + **prompt builder 5 tầng**.
- `Dispatcher.dispatch(task, workspace, feedback=None) -> DispatchResult` (abstract).
- `build_prompt(task, workspace, company_policy_path, context_file, feedback)` — ghép theo thứ tự:
  1. `company/AI_COMPANY_POLICY.md` (policy công ty)
  2. `<workspace>/AI_PROJECT_CONTEXT.md` (context repo đích)
  3. task body
  4. RULES (allowed/forbidden paths, test commands)
  5. CI feedback (chỉ khi fix-loop)

### `dispatcher/sdk_dispatcher.py` (online) — **backend MVP**
**Trách nhiệm**: chạy Claude headless qua `claude-agent-sdk`.
- `SdkDispatcher(allowed_tools, permission_mode, max_turns, model, ...)`.
- `dispatch()` → `asyncio.run(_run())`; gọi `query(prompt, ClaudeAgentOptions(cwd, allowed_tools, permission_mode, max_turns, model))`.
- **Quan trọng**: KHÔNG raise trong async generator (gây lỗi `aclose`). Trả `(summary, error)`; lỗi `is_error` được ghi nhận, để `main` quyết định (coder có thể đã sửa file dù result báo lỗi — vd "max turns").
- Auth: kế thừa login Claude Code CLI (gói Pro/Max), hoặc `CLAUDE_CODE_OAUTH_TOKEN`, hoặc `ANTHROPIC_API_KEY`. Xem [03-configuration](03-configuration.md).

### `dispatcher/action_dispatcher.py` (stub)
**Trách nhiệm (tương lai)**: backend GitHub Action — comment `@claude ...` → Action chạy cloud. Hiện `raise NotImplementedError`.

### `dispatcher/__init__.py`
- `get_dispatcher(backend, **kwargs) -> Dispatcher` — factory chọn `sdk | action` theo `rules.dispatch.backend`.

**Mở rộng**: thêm backend (vd OpenHands) = thêm class implement `Dispatcher` + nhánh trong factory. Core loop không đổi.

---

## Git & GitHub

### `git_ops.py` (online — git/gh CLI)
**Trách nhiệm**: thao tác cây mã local + tạo PR.
- `ensure_clone(url, dest, base_branch)` — clone hoặc fetch+reset.
- `create_branch(cwd, branch, base)` — checkout base, xóa+tạo lại branch (idempotent).
- `changed_files(cwd)` — parse `git status --porcelain`, **lọc artifact** (`__pycache__/`, `.pyc`, `.pytest_cache/`…) qua `_is_artifact`.
- `commit_all(cwd, msg) -> bool` (False nếu không có gì commit), `push`, `open_pr(...) -> int` (qua `gh pr create`, idempotent qua `find_pr_for_branch`), `head_sha`.
- `GitError` cho lỗi lệnh.

### `github_client.py` (online — PyGithub)
**Trách nhiệm**: GitHub API: label, issue, PR, check runs, comment.
- `GitHubClient(repo_full_name, token=None)` — auth qua `GITHUB_TOKEN` hoặc fallback `gh auth token`.
- `ensure_label`, `create_issue` (idempotent qua marker `<!-- ai-task:plan:001 -->` + `find_issue_by_marker`), `comment_on_issue`, `comment_on_pr`, `get_check_runs(ref)`.
- `task_marker(task)` — sinh marker.
- **Lưu ý idempotency**: `find_issue_by_marker` dựa trên list API có **độ trễ index** → nguồn idempotency chính vẫn là `state.json` (main chỉ tạo issue khi status=`CLASSIFIED`).

---

## Kiểm soát & quyết định

### `security/path_guard.py` (offline)
**Trách nhiệm**: chặn file ngoài `allowed_paths` / trong `forbidden_paths`.
- `check(changed_files, allowed_paths, forbidden_paths) -> list[PathViolation]`.
- `matches(path, pattern)` — glob kiểu gitignore (hỗ trợ `**`, `*`, `?`). `_glob_to_regex` translate glob → regex.
- Quy tắc: không khai allowed_paths → cho phép tất cả TRỪ forbidden; forbidden luôn thắng.

### `security/secret_scanner.py` (offline)
**Trách nhiệm**: quét secret trong file thay đổi trước commit.
- `scan(changed_files, workspace) -> list[SecretHit]`, `scan_text(text, file)`.
- Pattern: `ANTHROPIC_API_KEY=`, `SUPABASE_SERVICE_ROLE_KEY=`, private key block, `ghp_`, `sk-`, AWS `AKIA`, generic `secret/token/password=...`. File `.env` bị chặn theo tên.
- `_redact` che giá trị trong snippet.

### `reviewers/policy_reviewer.py` (offline)
**Trách nhiệm**: gộp path_guard + secret_scanner + risk gate → 1 quyết định pass/block.
- `review(task, changed_files, workspace, danger_paths, block_high_risk) -> PolicyResult`.
- `PolicyResult{ok, reasons, path_violations, secret_hits}`.

### `reviewers/ai_reviewer.py` (stub)
**Trách nhiệm (tương lai)**: đọc diff PR, comment góp ý (ngoài-phạm-vi/thiếu-test/hardcode/secret). Hiện `raise NotImplementedError`.

### `ci_watcher.py` (online — đọc qua github_client)
**Trách nhiệm**: poll check runs tới khi xong + tóm tắt lỗi.
- `wait_for_ci(provider, ref, rules, time_fn, sleep_fn) -> CIResult` — `time_fn/sleep_fn` inject được để test không chờ thật.
- `evaluate_checks(runs, required) -> CIResult` — quyết định passed/failed/pending từ 1 snapshot.
- `summarize_failures(failed) -> str` — feedback cho fix-loop.

### `reviewer.py` (offline)
**Trách nhiệm**: transition sau CI (hàm thuần, dễ test).
- `decide_next(task, ci, rules) -> TaskStatus`: passed→POLICY_REVIEW; failed & còn lượt→CI_FAILED; hết lượt/timeout→FAILED.

---

## Điều phối & ghi log

### `main.py` (online) — **module chính, ráp tất cả**
**Trách nhiệm**: CLI + orchestration loop.
- `Orchestrator(profile, rules, state_store, github, audit)` — khởi tạo dispatcher qua factory.
  - `run(plan_path)` — load plan, ensure label, lặp task (giới hạn `budget.max_tasks_per_run`).
  - `process_task(task)` — chạy state machine (xem [01-architecture](01-architecture.md)); đệ quy khi vào fix-loop.
  - `_set(task, status, reason)` — đổi status + save state + audit `decision.json`.
- `main(argv)` — `load_dotenv`, parse args (lệnh `run`/`init`/`help`), check auth, chạy `Orchestrator`.
  - `run <path>` lấy positional `path` (thư mục local | `owner/name` | `*.yaml`) → `resolve_profile` (trong `init_project.py`) ra `projects/<id>.yaml`; tham số: `--plan/--rules/--state/--stack`.
  - `init <repo>` (alias `init-project`) → tạo profile; `help`/`-h` in hướng dẫn tiếng Việt.
- Helper: `slugify`, `branch_name`, `_force_utf8_stdout` (để in tiếng Việt trên console Windows).

### `audit_logger.py` (offline)
**Trách nhiệm**: audit trail `runs/<date>/task-NNN/`.
- `AuditLogger(root, today)` — `today` inject được cho test.
- `run_dir(task)`, `write_text`, `write_json`, `append_line`.
- File ghi: `task.md, prompt.md, claude_summary.md, changed_files.txt, ci_result.json, policy.json, decision.json`.

---

## Stub cho tương lai (chưa code logic)

| Module | Milestone | Vai trò |
|--------|-----------|---------|
| `scheduling/worker_pool.py` | v0.3 | Pool chạy task song song |
| `scheduling/scheduler.py` | v0.3 | Chọn task theo execution rules + risk |
| `scheduling/dependency_graph.py` | v0.3 | Sắp xếp theo `depends_on` |
| `scheduling/lock_manager.py` | v0.3 | Path-lock + conflict_group-lock |
| `agents/` (README) | v0.4 | Subagent chuyên môn theo `agent_type` |

Xem [06-roadmap](06-roadmap.md) để biết cách hiện thực các stub này.
