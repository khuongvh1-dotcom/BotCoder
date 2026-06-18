# 06 — Roadmap & Extension Points

Tài liệu này là **bản đồ nâng cấp**: làm gì tiếp theo và cắm vào đâu.

## Trạng thái

- ✅ **v0.1.1 (MVP)** — hoàn thành, e2e pass. 1 task tuần tự, 1 plan, 1 repo,
  workspace cô lập, không auto-merge, classifier rule-based, policy_reviewer,
  path_guard + secret_scanner + audit.

## Roadmap

### v0.2 — Nhiều plan + cloud, vẫn tuần tự
Mục tiêu: scale đầu vào và bắt đầu chạy không cần máy local.

| Việc | File | Ghi chú |
|------|------|---------|
| Đọc nhiều plan | `src/plan_loader.py` (stub có sẵn) | Hiện thực `load_all(glob)`; gán `plan_id` theo tên file; main lặp qua tất cả |
| State nhiều plan | `state_store.py` | Đã sẵn `plans{}` + `plan_id` trong schema v2 — chỉ cần dùng |
| Backend cloud | `dispatcher/action_dispatcher.py` (stub) | Comment `@claude ...` qua `github_client`, poll PR mới; đổi `rules.dispatch.backend=action` |
| Chạy định kỳ | `.github/workflows/orchestrator.yml` | Cron gọi bot; state đọc/ghi qua artifact hoặc commit |
| LLM classifier | `task_classifier.py` | Thêm hàm LLM-based; giữ signature `classify(task, rules)` |

Vẫn `execution.max_parallel_tasks=1`.

### v0.3 — Song song an toàn
Mục tiêu: chạy nhiều task cùng lúc không xung đột.

| Việc | File (stub) | Ghi chú |
|------|-------------|---------|
| Pool worker | `scheduling/worker_pool.py` | Chạy đồng thời tới `execution.max_parallel_tasks` |
| Lập lịch | `scheduling/scheduler.py` | Chọn task theo execution rules + risk (`max_parallel_high_risk=0`) |
| Phụ thuộc | `scheduling/dependency_graph.py` | Topo-sort theo `task.depends_on` |
| Khóa | `scheduling/lock_manager.py` | Path-lock + `conflict_group`-lock (đã có cờ trong `rules.locks`) |

Đã sẵn nền: `Task.parallel/depends_on/conflict_group`, `workspace/task-NNN` cô lập,
branch riêng/task, `rules.execution` + `rules.locks`. Đổi `execution.mode=parallel`.

### v0.4 — Subagent chuyên môn
Mục tiêu: mỗi loại việc một agent.

| Agent | File | Vai trò |
|-------|------|---------|
| coder | `agents/coder_agent.py` | Sửa code (hiện là sdk_dispatcher) |
| tester | `agents/tester_agent.py` | Viết/chạy test |
| reviewer | `agents/reviewer_agent.py` | Kích hoạt `reviewers/ai_reviewer.py` (đọc diff, góp ý) |
| doc | `agents/doc_agent.py` | Cập nhật tài liệu |
| security | `agents/security_agent.py` | Quét secret/risk sâu hơn rule-based |

Dispatch theo `task.agent_type` (đã có trong model + plan format).

### Việc khác (không gắn milestone cụ thể)
- Auto-merge khi CI pass (bật `rules.merge.auto_merge`).
- SQLite thay `state.json` khi số task lớn.
- UI/dashboard.
- Webhook thay polling CI.
- Retry/backoff + xử lý rate-limit nâng cao.
- OpenHands Resolver làm dispatcher backend thứ 3.

---

## Extension Points (điểm cắm)

Nơi để thêm tính năng mà **không phá** core.

### Thêm dispatcher backend (cách trigger coder mới)
1. Tạo class implement `Dispatcher` ([`dispatcher/base.py`](../src/dispatcher/base.py)):
   `dispatch(task, workspace, feedback) -> DispatchResult`.
2. Đăng ký trong `dispatcher/__init__.py::get_dispatcher`.
3. Đặt `rules.dispatch.backend = <tên>`.
→ Core loop (`main.py`) không đổi.

### Thêm reviewer / gate
- Rule-based: bổ sung vào `reviewers/policy_reviewer.py::review` (trả thêm reason).
- AI-based: hiện thực `reviewers/ai_reviewer.py::review_diff`, gọi trong `main.process_task` ở bước POLICY_REVIEW.

### Thêm secret pattern / path rule
- Secret: thêm tuple vào `_PATTERNS` trong `security/secret_scanner.py`.
- Path: glob đã hỗ trợ `**/*/?`; chỉ cần khai trong plan `Allowed/Forbidden paths` hoặc `profile.paths.danger`.

### Thêm field cho Task / config
- Thêm field vào `models.Task` (có default → không phá state cũ).
- Thêm khóa config vào model trong `config.py` + cập nhật YAML mẫu.
- Nếu cần parse từ plan: thêm vào `_SCALAR_FIELDS`/`_LIST_FIELDS` trong `plan_parser.py`.

### Thêm state machine transition
- Thêm giá trị vào `models.TaskStatus` (enum đã thiết kế mở rộng).
- Xử lý transition trong `main.process_task` + `reviewer.decide_next`.

### Đổi backend lưu trữ state
- Giữ interface `StateStore.load/save` + `State.get_task/upsert_task`.
- Thay phần đọc/ghi JSON bằng SQLite/DB.

---

## Nguyên tắc khi nâng cấp

1. **Giữ idempotent + resumable** — mọi bước mới phải an toàn khi chạy lại.
2. **Giữ workspace cô lập** — không để task dùng chung thư mục.
3. **Không bỏ qua security gate** — path_guard + secret_scanner chạy trước mọi commit.
4. **Không auto-merge mặc định** — chỉ bật có chủ đích qua config.
5. **Mở rộng qua interface, không sửa core loop** khi có thể.
6. **Thêm test** cho mỗi module logic mới (mẫu: inject time/today/rules để tất định).
