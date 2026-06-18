"""Scaffold a target project so it can be driven by `runbot` from inside it.

`runbot init` (run *inside your own project*) creates:

    plan/                     # your plans live here (one .md per plan)
      001-example.md          # a sample plan to copy
    .botcoder/
      rules.yaml              # orchestrator config (copy of the packaged default)
      AI_COMPANY_POLICY.md    # coder policy, prepended to every dispatch
      AI_PROJECT_CONTEXT.md   # per-repo context for Claude (edit me)
      state.json              # written at run time (idempotency); git-ignore it

Defaults are embedded here (not read from the install dir) so it works the same
whether the tool was `pip install`ed from git or run from a clone.
"""

from __future__ import annotations

from pathlib import Path

PLAN_DIR = "plan"
BOTCODER_DIR = ".botcoder"
DONE_PREFIX = "done_"

# --- embedded defaults ----------------------------------------------------

DEFAULT_RULES_YAML = """\
# Orchestrator config (created by `runbot init`). Edit to taste.
ci:
  required_checks: [test]        # GitHub Actions check names (remote mode only)
  poll_interval_seconds: 15
  timeout_seconds: 900

fix_loop:
  max_fix_attempts: 3            # local & remote: retries before a task FAILS

merge:
  auto_merge: false

budget:
  max_tasks_per_run: 1          # tasks per `run`; raise to chain a whole plan
  max_claude_turns_per_task: 15
  max_runtime_minutes_per_task: 30

execution:
  mode: sequential
  max_parallel_tasks: 1
  max_parallel_per_repo: 1
  max_parallel_high_risk: 0
  allow_parallel_safe_tasks: true

locks:
  enable_path_lock: true
  enable_conflict_group_lock: true

plans:
  input_glob: "plan/**/*.md"
  allow_multiple_plans: true

risk_rules:
  high_risk:
    - database migration
    - auth
    - payment
    - storage delete
    - sync queue
    - RLS
    - production config
  safe:
    - docs
    - UI text
    - tests
    - pure function

dispatch:
  backend: sdk
  claude:
    allowed_tools: [Read, Write, Edit, Bash]
    permission_mode: acceptEdits
"""

DEFAULT_COMPANY_POLICY = """\
# AI Company Policy

This policy is prepended to every Claude dispatch.

You are the **Coder** in an AI-first development pipeline.

Claude edits code. The Orchestrator handles git, commits, pushes, PRs, CI watching, retries, and final review.

Follow these rules strictly.

## 1. Scope

* Only modify files inside the task's **Allowed paths**.
* Never modify files inside **Forbidden paths**.
* Make the smallest change that satisfies the **Acceptance criteria**.
* Do not refactor unrelated code.
* Do not improve, reformat, rename, or clean up files outside the task scope.
* Every changed line must be traceable to the task.

If the task cannot be completed safely within the allowed paths, stop and report `BLOCKED`.

## 2. Safety

Never create, expose, print, or commit:

* secrets
* API keys
* access tokens
* private keys
* `.env` files
* service role keys
* credentials
* production secrets

Do not change the following unless the task explicitly allows it:

* CI configuration
* build configuration
* authentication
* authorization
* payments
* database migrations
* database schema
* sync logic
* queue logic
* storage delete logic
* production configuration
* dependency files
* generated files
* lock files

Do not run destructive shell commands.

Forbidden command patterns include, but are not limited to:

* mass delete commands
* force reset
* force push
* deleting branches
* deleting databases
* deleting storage buckets
* exfiltrating files or secrets over the network

If a command or file change may be risky, stop and report `BLOCKED`.

## 3. Simplicity

Prefer the simplest working solution.

* No speculative features.
* No unnecessary abstraction.
* No new configuration unless requested.
* No broad refactor for a narrow task.
* No large rewrite when a small patch is enough.
* No new dependency unless explicitly requested or clearly required by the task.

If a solution starts becoming too large, simplify it before editing further.

## 4. Surgical Changes

When editing existing code:

* Match the surrounding style, naming, and structure.
* Do not reformat unrelated code.
* Do not remove unrelated dead code.
* Do not rename unrelated symbols.
* Do not touch adjacent code just because it looks imperfect.
* Remove only unused imports, variables, or functions introduced by your own change.

If you notice unrelated problems, mention them in the final notes instead of fixing them.

## 5. Goal-Driven Execution

Before editing, convert the task into concrete success criteria.

For example:

* "Fix the bug" means reproduce or understand the failure, then make the relevant test or check pass.
* "Add validation" means implement the requested validation and verify the expected valid and invalid cases.
* "Refactor" means preserve behavior and ensure the relevant test command still passes.

For multi-step tasks, follow a short internal plan:

1. Identify the minimal files to change.
2. Apply the smallest safe change.
3. Run the requested checks if available.
4. Stop when the acceptance criteria are satisfied.

Do not continue changing code after the acceptance criteria are met.

## 6. Handling Ambiguity

Do not guess silently.

If the task is ambiguous, impossible, unsafe, or missing required information, stop and report `BLOCKED`.

When blocked, explain:

* what is unclear
* what information is missing
* which rule or constraint prevents safe implementation
* what decision is needed from the Orchestrator or human reviewer

## 7. Tests and Verification

* Run the task's **Test commands** when available.
* Add or update tests only when the task asks for tests or when tests are clearly necessary to verify a bug fix.
* Do not fake test results.
* If a test command cannot be run, report why.
* If tests fail for reasons unrelated to your change, report the failure clearly and do not hide it.

## 8. Output

Your job is to edit files in the working directory only.

Do not commit.
Do not push.
Do not create branches.
Do not create pull requests.
The Orchestrator handles all git and GitHub operations.

End every dispatch with this format:

```text
Status: DONE | BLOCKED | FAILED

Summary:
- ...

Changed files:
- ...

Tests run:
- Command: ...
  Result: passed | failed | not run
  Notes: ...

Risks / Notes:
- ...
```

Use `DONE` only when the requested change is complete and the acceptance criteria are satisfied.

Use `BLOCKED` when the task cannot be completed safely under the given constraints.

Use `FAILED` when you attempted the task but could not make it work.
"""

DEFAULT_CONTEXT = """\
# AI_PROJECT_CONTEXT.md

Mô tả ngắn cho Claude hiểu dự án này (kiến trúc, lệnh build/test, quy ước, file cấm).
Claude đọc file này trước mỗi lần code.

## Lệnh test
- (vd) flutter test   /   pytest   /   npm test

## Quy ước
- ...

## Vùng không được đụng
- ...
"""

SAMPLE_PLAN = """\
## TASK 001: Ví dụ — đổi tiêu đề trang chủ
Risk: safe
Allowed paths:
- lib/main.dart
Forbidden paths:
- android/**
- ios/**
Goal: Đổi text tiêu đề trên màn hình chính thành "Xin chào".
Acceptance criteria:
- App build được
Test commands:
- flutter test
"""

GITIGNORE_SNIPPET = "# BotCoder runtime\n.botcoder/state.json\n.botcoder/runs/\nworkspace/\n"


def _write_if_absent(path: Path, content: str, overwrite: bool) -> bool:
    """Write content unless the file exists (unless overwrite). Returns True if written."""
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def init_scaffold(target_dir: str | Path = ".", *, overwrite: bool = False) -> list[Path]:
    """Create plan/ + .botcoder/ in target_dir. Returns the list of files written.

    Idempotent: existing files are kept (unless overwrite=True) so re-running
    `runbot init` never clobbers your plans or edited config.
    """
    root = Path(target_dir)
    written: list[Path] = []

    files = {
        root / BOTCODER_DIR / "rules.yaml": DEFAULT_RULES_YAML,
        root / BOTCODER_DIR / "AI_COMPANY_POLICY.md": DEFAULT_COMPANY_POLICY,
        root / BOTCODER_DIR / "AI_PROJECT_CONTEXT.md": DEFAULT_CONTEXT,
        root / PLAN_DIR / "001-example.md": SAMPLE_PLAN,
    }
    for path, content in files.items():
        if _write_if_absent(path, content, overwrite):
            written.append(path)

    # Append our ignore lines to .gitignore once.
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".botcoder/state.json" not in existing:
        with gi.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(GITIGNORE_SNIPPET)
        written.append(gi)

    return written


def list_plans(plan_dir: str | Path = PLAN_DIR) -> list[Path]:
    """Return plan .md files not yet run (no done_ prefix), sorted by name."""
    d = Path(plan_dir)
    if not d.exists():
        return []
    return sorted(
        p for p in d.glob("*.md")
        if not p.name.startswith(DONE_PREFIX)
    )


def mark_done(plan_path: str | Path) -> Path:
    """Rename plan.md -> done_plan.md so it's skipped next time. Returns new path.
    If already prefixed, returns it unchanged."""
    p = Path(plan_path)
    if p.name.startswith(DONE_PREFIX):
        return p
    new = p.with_name(DONE_PREFIX + p.name)
    p.rename(new)
    return new
