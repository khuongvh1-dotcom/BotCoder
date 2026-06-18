# 04 — State & Data

## `state.json` — nguồn sự thật

Lưu tiến độ mọi task. Atomic write (`.tmp` → `os.replace` + `fsync`) trong
[`src/state_store.py`](../src/state_store.py). **Schema version 2** (khai `plans{}`
+ `plan_id` từ đầu để v0.2 không phải migrate).

```json
{
  "version": 2,
  "repo": "khuongvh1-dotcom/ai-sandbox",
  "updated_at": "2026-06-18T11:46:30+00:00",
  "plans": {
    "plan": { "file": "plans/plan.md", "hash": "sha256:..." }
  },
  "tasks": {
    "001": {
      "id": "001",
      "plan_id": "plan",
      "title": "Implement add function",
      "file": "tasks/001_task.md",
      "status": "human_review",
      "risk": "safe",
      "agent_type": "coder",
      "parallel": false,
      "depends_on": [],
      "conflict_group": "core",
      "issue_number": 2,
      "branch": "ai-task/001-implement-add-function",
      "pr_number": 5,
      "fix_attempts": 0,
      "last_ci_conclusion": null,
      "run_dir": null,
      "updated_at": "2026-06-18T11:46:30+00:00"
    }
  }
}
```

### Vai trò các field then chốt
- `status` — vị trí trong state machine; quyết định bước tiếp theo khi resume.
- `issue_number / branch / pr_number` — **khóa idempotency** (không tạo trùng).
- `fix_attempts` — đếm vòng fix; ghi **trước** khi re-dispatch để crash không reset.
- `plans[*].hash` — phát hiện plan thay đổi (re-parse).
- `parallel / depends_on / conflict_group` — chưa dùng ở MVP, sẵn cho v0.3.

### Resume & idempotency
- Chạy lại bot → đọc `state.json`, mỗi task tiếp đúng từ `status` hiện tại.
- Task ở `HUMAN_REVIEW / DONE / BLOCKED` → **skip**.
- Tạo issue/PR luôn kiểm tra state trước → an toàn chạy lại nhiều lần.
- `state.json` trong `.gitignore` (runtime artifact, không commit).

> ⚠️ Lưu ý đọc file: `state.json` là **UTF-8**. Trên Windows, đọc bằng Python phải
> `open(..., encoding='utf-8')` (mặc định cp1252 sẽ lỗi với ký tự non-ASCII).

---

## Models (pydantic) — `src/models.py`

| Model | Mục đích |
|-------|----------|
| `Task` | Đơn vị công việc (đầy đủ field, xem [02-modules](02-modules.md)) |
| `TaskStatus` | Enum state machine |
| `RiskLevel` | safe / medium_risk / high_risk / blocked |
| `AgentType` | coder / tester / reviewer / doc / security |
| `DispatchResult` | Kết quả dispatcher: `changed_files, summary, branch, error` |
| `CIResult` / `CIConclusion` | Kết quả CI: passed / failed / timeout / pending + summary |

Hằng: `TERMINAL_STATUSES = {DONE, FAILED, BLOCKED}`, `PARKED_STATUSES = {HUMAN_REVIEW}`.

---

## Audit trail — `runs/<date>/task-NNN/`

Truy vết đầy đủ mỗi task (không cần DB). Ghi bởi [`src/audit_logger.py`](../src/audit_logger.py).

| File | Nội dung |
|------|----------|
| `task.md` | Nội dung task gốc |
| `prompt.md` | Prompt 5 tầng đã gửi Claude (lần dispatch gần nhất) |
| `claude_summary.md` | Tóm tắt Claude trả về (hoặc error) |
| `changed_files.txt` | Danh sách file thay đổi (đã lọc artifact) |
| `policy.json` | Kết quả policy_reviewer (path/secret/risk) |
| `ci_result.json` | Kết quả CI (conclusion + summary + checks) |
| `decision.json` | Mỗi transition: `{status, reason, fix_attempts}` |

Dùng để trả lời: task từ plan nào, Claude sửa gì, prompt là gì, CI fail vì sao,
retry mấy lần, ai/bước nào quyết định gì.

`runs/*` trong `.gitignore` (giữ `.gitkeep`).

---

## Thư mục runtime (gitignored)

| Thư mục | Vai trò |
|---------|---------|
| `workspace/task-NNN/` | Checkout cô lập của repo đích cho từng task |
| `runs/<date>/task-NNN/` | Audit trail |
| `tasks/` | File task sinh từ plan (`NNN_task.md`) |
| `state.json` | State machine |
