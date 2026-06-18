# 05 — Development

## Yêu cầu hệ thống

| Công cụ | Phiên bản (đã test) | Ghi chú |
|---------|---------------------|---------|
| Python | 3.10+ (dùng 3.12.10) | SDK yêu cầu 3.10+ |
| git | 2.54 | trên PATH |
| gh (GitHub CLI) | 2.63 | đã `gh auth login` |
| Claude Code CLI | 2.1.165 | để SDK kế thừa login (gói Pro/Max) |
| Node.js | có sẵn | đi kèm Claude Code |

> **Trên máy hiện tại**: Python ở `C:\Users\DELL\AppData\Local\Programs\Python\Python312\python.exe`
> (có thể chưa trên PATH ở shell cũ — dùng đường dẫn đầy đủ hoặc mở terminal mới).

## Cài đặt

```bash
cd f:/CongTy/ToolAI/BotCoder
pip install -e .[dev]        # cài deps + pytest

# GitHub auth
gh auth login               # hoặc đặt GITHUB_TOKEN trong .env

# Claude auth — chọn 1 (xem 03-configuration):
#  A) gói Pro/Max: chỉ cần `claude` CLI đã login (không cần env var)
#  B) hoặc: claude setup-token  → CLAUDE_CODE_OAUTH_TOKEN trong .env
#  C) hoặc: ANTHROPIC_API_KEY trong .env

cp .env.example .env        # điền giá trị nếu dùng B/C
python scripts/check_auth.py   # xác nhận auth Claude OK
```

Dependencies (`pyproject.toml`): `PyGithub`, `claude-agent-sdk`, `pydantic`,
`pyyaml`, `python-dotenv`; dev: `pytest`.

## Chạy

```bash
runbot run <đường-dẫn> --plan plans/plan.md
# <đường-dẫn>: thư mục local | repo GitHub owner/name | projects/x.yaml
runbot help        # xem toàn bộ lệnh
# runbot = python -m src.main (có sau pip install -e .)
```

Lệnh:
- `run <đường-dẫn>` (mặc định) — chạy bot; `<đường-dẫn>` tự nhận biết là thư mục
  local, repo GitHub `owner/name`, hoặc file profile. Thiếu profile thì tự tạo.
- `init <repo>` — chỉ tạo `projects/<id>.yaml` (alias cũ: `init-project`).
- `help` / `-h` / `--help` — hướng dẫn.

Tham số `run`:
- `path` (positional, mặc định `projects/sandbox.yaml`)
- `--plan` (mặc định `plans/plan.md`)
- `--rules` (mặc định `config/rules.yaml`)
- `--state` (mặc định `state.json`)
- `--stack` (chỉ dùng khi phải tạo profile mới)

Chạy lại an toàn (idempotent): bot tiếp tục từ state hiện tại, không tạo trùng.
Reset để chạy mới: xóa `state.json` + `workspace/task-NNN/`, đóng PR/branch/issue cũ.

## Test

```bash
python -m pytest -q          # 45 tests (offline + git_ops cần git)
```

Phân loại test:
- **Offline thuần**: `test_plan_parser, test_classifier, test_state_store, test_path_guard, test_secret_scanner, test_ci_watcher, test_reviewer, test_policy_reviewer`.
- **Cần git**: `test_git_ops` (tạo repo local tạm; tự skip nếu thiếu git).
- Test CI watcher dùng `time_fn/sleep_fn` inject → không chờ thật.
- Audit/classifier dùng `today`/rules inject → tất định.

## Verify end-to-end (đã làm)

1. Repo sandbox `khuongvh1-dotcom/ai-sandbox` (public): `calc.py` (chưa implement),
   `tests/test_calc.py`, `.github/workflows/ci.yml` (job `test` chạy `pytest`),
   `pytest.ini` (`pythonpath = .`), `.gitignore`, `AI_PROJECT_CONTEXT.md`.
2. Chạy `runbot ...` (hoặc `python -m src.main ...`) → quan sát log đi hết state tới `human_review`.
3. Kiểm chứng: PR có checks `SUCCESS`, mergeable, **OPEN** (không auto-merge);
   `state.json` đủ chuỗi; `runs/<date>/task-001/` đủ file.

Đã verify thật: e2e pass · idempotency (chạy lại skip) · path_guard (chặn `.pyc`) ·
secret_scanner · fix-loop (retry tới max rồi FAILED).

---

## Lỗi đã gặp & cách xử lý (lessons learned)

Ghi lại để khỏi vấp lại khi mở rộng:

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| `python: command not found` | Python chưa cài / chưa trên PATH | Cài qua winget (`Python.Python.3.12`); dùng đường dẫn đầy đủ ở shell cũ |
| `winget` không có dù đã cài App Installer | Stub không trên PATH | Gọi qua `...\WindowsApps\winget.exe` |
| SDK báo `is_error` nhưng file đã sửa | result error transient (vd "max turns") | Dispatcher trả `(summary, error)`, KHÔNG raise trong async-gen; main chỉ FAILED khi error **và** không có file đổi |
| `aclose(): async generator already running` | raise bên trong `async for` của SDK | Thu lỗi rồi return, không raise trong loop |
| path_guard chặn `__pycache__/*.pyc` | Claude chạy pytest sinh artifact | `git_ops.changed_files` lọc artifact + repo nên có `.gitignore` |
| CI fail `ModuleNotFoundError: No module named 'calc'` | pytest thiếu root trên sys.path | Thêm `pytest.ini` với `pythonpath = .` trong repo đích |
| CI fail `unexpected line '﻿[pytest]'` | BOM do PowerShell `-Encoding utf8` | Ghi file UTF-8 **không BOM** (`UTF8Encoding($false)` / `WriteAllText`) |
| Tạo 2 issue trùng | List API trễ index (eventual consistency) | Idempotency chính dựa `state.json`, không chỉ marker; main tạo issue chỉ ở state CLASSIFIED |
| Đọc `state.json` lỗi `charmap codec` | Windows mặc định cp1252 | `open(..., encoding='utf-8')` |

---

## Mẹo vận hành

- **PowerShell + gh**: `gh` in ra stderr khiến PowerShell tô đỏ dù lệnh OK — không phải lỗi. Tránh `2>&1` với native exe trong PS 5.1.
- **Dọn nhanh để chạy lại sạch**:
  ```
  Remove-Item state.json, workspace\task-001 -Recurse -Force
  gh pr close <n> --repo <repo> --delete-branch
  ```
- **Xem PR/CI**: `gh pr view <n> --json state,mergeable,statusCheckRollup`,
  `gh run view <id> --log-failed`.
