# 01 — Architecture

## Triết lý

**AI-first development pipeline**, KHÔNG phải "thuần AI code 100%":

> AI viết code · Bot điều phối quy trình · CI kiểm tra kỹ thuật · Policy + Con người duyệt vùng rủi ro.

Hệ quả thiết kế:
- Bot **không tự merge** — luôn dừng ở `HUMAN_REVIEW`.
- Mọi thay đổi của AI đi qua **path_guard** (chỉ sửa file được phép) và **secret_scanner** (không lộ secret) trước khi commit.
- Task `high_risk` (auth, payment, DB migration…) bị **BLOCKED** chờ người duyệt.

## Vai trò các thành phần

| Thành phần | Vai trò |
|------------|---------|
| **Orchestrator** (bot Python này) | Điều phối: đọc plan, tạo issue, dispatch coder, đọc CI, quyết định transition |
| **Claude (coder)** | Sửa code trong workspace, qua `claude-agent-sdk` headless |
| **GitHub Issues** | Hàng đợi task (mỗi task = 1 issue, idempotent qua marker) |
| **GitHub PR** | Kết quả của mỗi task |
| **GitHub Actions CI** | Cổng kiểm tra kỹ thuật (required checks) |
| **Con người** | Duyệt + merge PR (cuối pipeline) |

## Sơ đồ thành phần

```
                         ┌─────────────────────────────────────────────┐
                         │              Orchestrator (src/)             │
                         │                                              │
  plans/plan.md ───────► │  plan_parser ──► task_classifier            │
  projects/*.yaml ─────► │  config        (rule-based risk)            │
  config/rules.yaml ───► │                                              │
                         │  main.py (state machine loop)                │
                         │    ├─ github_client ──────┐                  │
                         │    ├─ git_ops             │                  │
                         │    ├─ dispatcher/sdk ─────┼──► Claude (SDK)   │
                         │    ├─ security/path_guard │                  │
                         │    ├─ security/secret     │                  │
                         │    ├─ reviewers/policy    │                  │
                         │    ├─ ci_watcher          │                  │
                         │    ├─ reviewer (decide)   │                  │
                         │    ├─ state_store ──► state.json              │
                         │    └─ audit_logger ──► runs/<date>/task-NNN/  │
                         └───────────────┬──────────────────────────────┘
                                         │ git + gh CLI / GitHub API
                                         ▼
              ┌──────────────────────────────────────────────┐
              │  Target repo (sandbox / BTS / …) on GitHub    │
              │   Issues ─ Branch ─ PR ─ Actions CI           │
              └──────────────────────────────────────────────┘
```

## Luồng orchestration (MVP, tuần tự)

`main.py::Orchestrator.process_task` lái mỗi task qua các bước (mỗi bước lưu state):

```
PENDING        ── task_classifier.classify ──►  CLASSIFIED   (high_risk? ► BLOCKED)
CLASSIFIED     ── github_client.create_issue ─►  ISSUE_CREATED
ISSUE_CREATED  ── git_ops.ensure_clone+branch ►  DISPATCHED
DISPATCHED     ── dispatcher.dispatch (Claude) ► CHANGES_READY
CHANGES_READY  ── path_guard + secret_scanner ─► SECURITY_CHECK  (vi phạm ► BLOCKED)
SECURITY_CHECK ── git commit+push + gh pr ─────► PR_OPEN
PR_OPEN        ── ci_watcher.wait_for_ci ──────► CI_RUNNING ─► CI_PASSED / CI_FAILED
CI_FAILED      ── reviewer.decide_next ─────────► (còn lượt: re-dispatch feedback ► CI_RUNNING)
                                                  (hết lượt: FAILED)
CI_PASSED      ── policy_reviewer.review ───────► POLICY_REVIEW ─► HUMAN_REVIEW  (DỪNG)
```

Điểm mấu chốt:
- **Fix loop**: khi CI fail, bot gửi tóm tắt lỗi (`ci_watcher.summarize_failures`) làm feedback cho Claude, lặp tối đa `rules.fix_loop.max_fix_attempts` (mặc định 3).
- **Dừng ở HUMAN_REVIEW**: PR để mở, mergeable, con người merge thủ công.

## State machine (đầy đủ)

```
PENDING → CLASSIFIED → ISSUE_CREATED → DISPATCHED → CHANGES_READY
   → SECURITY_CHECK → PR_OPEN → CI_RUNNING → {CI_PASSED | CI_FAILED}
   → POLICY_REVIEW → HUMAN_REVIEW → DONE

Terminal lỗi: FAILED, BLOCKED
```

- `DONE`: MVP không tự đạt (người merge). Để sau (auto-merge v0.2+).
- `FAILED`: hết lượt fix, hoặc CI timeout, hoặc coder không tạo thay đổi.
- `BLOCKED`: high_risk, hoặc vi phạm path/secret — chờ người.
- Enum khai **đầy đủ từ đầu** (kể cả các state v0.3+ chưa dùng nhiều) để không phải migrate sau. Định nghĩa: [`src/models.py`](../src/models.py) `TaskStatus`.

## Nguyên tắc nền tảng

1. **Idempotent + resumable**: `state.json` là nguồn sự thật. Mỗi bước kiểm tra state trước khi hành động → chạy lại an toàn, không tạo issue/PR trùng. Đây là nền để v0.2 chạy trên cron.
2. **Workspace cô lập**: mỗi task clone riêng `workspace/task-NNN/` → nền cho song song v0.3.
3. **Dispatcher sau interface**: core loop độc lập với cách trigger coder (SDK / GitHub Action / OpenHands) — chỉ `dispatcher/*` biết chi tiết.
4. **Forward-compatible**: config/format/models khai đủ field cho song song + multi-agent, MVP chỉ dùng một phần.

Xem thêm: [02-modules](02-modules.md), [07-decisions](07-decisions.md).
