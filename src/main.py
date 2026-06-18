"""Orchestration loop (MVP v0.1.1).

Reads a plan, then drives each task sequentially through the state machine:

  PENDING -> CLASSIFIED -> ISSUE_CREATED -> DISPATCHED -> CHANGES_READY
  -> SECURITY_CHECK -> PR_OPEN -> CI_RUNNING -> CI_PASSED/CI_FAILED
  -> POLICY_REVIEW -> HUMAN_REVIEW   (stop; no auto-merge)

State is saved after every transition; everything is idempotent so a crashed run
can be resumed. The MVP runs one task (budget.max_tasks_per_run) and never merges.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import git_ops, plan_parser, task_classifier
from .audit_logger import AuditLogger
from .ci_watcher import wait_for_ci
from .config import Profile, Rules, load_profile, load_rules
from .dispatcher import get_dispatcher
from .github_client import GitHubClient
from .models import CIConclusion, RiskLevel, Task, TaskStatus
from .reviewer import decide_next
from .reviewers import policy_reviewer
from .state_store import State, StateStore


def log(msg: str) -> None:
    print(f"[orchestrator] {msg}", flush=True)


def slugify(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen] or "task"


def branch_name(profile: Profile, task: Task) -> str:
    return f"{profile.branch_prefix}{task.id}-{slugify(task.title)}"


class Orchestrator:
    def __init__(self, profile: Profile, rules: Rules, state_store: StateStore,
                 github: GitHubClient | None = None, audit: AuditLogger | None = None,
                 local_dir: str | Path | None = None,
                 company_policy_path: str = "company/AI_COMPANY_POLICY.md"):
        self.profile = profile
        self.rules = rules
        self.store = state_store
        self.state: State = state_store.load()
        self.state.repo = profile.repo.full_name
        # local_dir set => edit that directory in place; no clone, no issue/PR/CI.
        self.local_dir = Path(local_dir) if local_dir else None
        # GitHub is only needed in remote (PR) mode; skip the client in local mode.
        self.github = github or (None if self.local_dir else GitHubClient(profile.repo.full_name))
        self.audit = audit or AuditLogger()
        self.dispatcher = get_dispatcher(
            rules.dispatch.backend,
            allowed_tools=rules.dispatch.claude.allowed_tools,
            permission_mode=rules.dispatch.claude.permission_mode,
            max_turns=rules.budget.max_claude_turns_per_task,
            context_file=profile.context_file,
            company_policy_path=company_policy_path,
        )

    def _save(self, task: Task) -> None:
        self.state.upsert_task(task)
        self.store.save(self.state)

    def _set(self, task: Task, status: TaskStatus, reason: str = "") -> None:
        task.status = status
        self._save(task)
        self.audit.write_json(task, "decision.json",
                              {"status": status.value, "reason": reason,
                               "fix_attempts": task.fix_attempts})
        log(f"task {task.id}: -> {status.value}" + (f" ({reason})" if reason else ""))

    def load_plan(self, plan_path: str) -> list[Task]:
        tasks = plan_parser.parse_plan(plan_path)
        plan_parser.write_task_files(tasks)
        from .state_store import PlanRef
        self.state.plans["plan"] = PlanRef(file=plan_path, hash=plan_parser.plan_hash(plan_path))
        # merge into state, preserving prior progress for the same task id
        merged: list[Task] = []
        for t in tasks:
            prior = self.state.get_task(t.id)
            if prior is not None and prior.status not in (TaskStatus.PENDING,):
                merged.append(prior)              # resume existing task
            else:
                self.state.upsert_task(t)
                merged.append(t)
        self.store.save(self.state)
        return merged

    def run(self, plan_path: str) -> None:
        tasks = self.load_plan(plan_path)

        # ensure labels exist once (remote/PR mode only)
        if self.github is not None:
            self.github.ensure_label(self.profile.labels.task, color="5319e7",
                                     description="Task handled by the AI orchestrator")

        processed = 0
        for task in tasks:
            if processed >= self.rules.budget.max_tasks_per_run:
                log(f"budget: max_tasks_per_run={self.rules.budget.max_tasks_per_run} reached; stopping.")
                break
            if task.status in (TaskStatus.DONE, TaskStatus.HUMAN_REVIEW, TaskStatus.BLOCKED):
                log(f"task {task.id}: already at {task.status.value}; skipping.")
                continue
            if self.local_dir is not None:
                self.process_task_local(task)
            else:
                self.process_task(task)
            processed += 1

    def process_task(self, task: Task) -> None:
        log(f"=== task {task.id}: {task.title} (status={task.status.value}) ===")
        self.audit.write_text(task, "task.md", task.body)

        # 1. CLASSIFY
        if task.status == TaskStatus.PENDING:
            task.risk = task_classifier.classify(task, self.rules.risk_rules)
            self._set(task, TaskStatus.CLASSIFIED, reason=f"risk={task.risk.value}")
            if task.risk == RiskLevel.HIGH_RISK:
                self._set(task, TaskStatus.BLOCKED, reason="high_risk requires human approval")
                return

        # 2. ISSUE
        if task.status == TaskStatus.CLASSIFIED:
            task.issue_number = self.github.create_issue(task, labels=[self.profile.labels.task])
            self._set(task, TaskStatus.ISSUE_CREATED, reason=f"issue #{task.issue_number}")

        # 3. CHECKOUT + BRANCH
        ws = Path(self.profile.workspace_dir) / f"task-{task.id}"
        if task.status == TaskStatus.ISSUE_CREATED:
            git_ops.ensure_clone(self.profile.repo.url, ws, self.profile.repo.base_branch)
            task.branch = branch_name(self.profile, task)
            git_ops.create_branch(ws, task.branch, self.profile.repo.base_branch)
            self._set(task, TaskStatus.DISPATCHED, reason=f"branch {task.branch}")

        # 4. DISPATCH (+ fix loop re-entry)
        if task.status in (TaskStatus.DISPATCHED, TaskStatus.CI_FAILED):
            feedback = task.last_ci_conclusion if task.status == TaskStatus.CI_FAILED else None
            if task.status == TaskStatus.CI_FAILED:
                task.fix_attempts += 1
                self._save(task)                 # persist attempt count BEFORE dispatch
                # fresh checkout of the branch to re-apply on top of pushed state
                git_ops.ensure_clone(self.profile.repo.url, ws, self.profile.repo.base_branch)
                git_ops.create_branch(ws, task.branch, self.profile.repo.base_branch)

            result = self.dispatcher.dispatch(task, ws, feedback=feedback)
            self.audit.write_text(task, "prompt.md", getattr(self.dispatcher, "last_prompt", ""))
            self.audit.write_text(task, "claude_summary.md", result.summary or result.error or "")

            files = git_ops.changed_files(ws)
            # An error with no file changes is a hard failure. An error *with*
            # changes is treated as a soft warning — the coder did edit files.
            if result.error and not files:
                self._set(task, TaskStatus.FAILED, reason=f"dispatch error: {result.error}")
                return
            if result.error:
                log(f"task {task.id}: dispatch warning (continuing, {len(files)} files changed): {result.error}")

            self.audit.write_text(task, "changed_files.txt", "\n".join(files))
            self._set(task, TaskStatus.CHANGES_READY, reason=f"{len(files)} files changed")

            # 5. SECURITY CHECK
            policy = policy_reviewer.review(
                task, files, workspace=ws,
                danger_paths=self.profile.paths.danger, block_high_risk=False,
            )
            self.audit.write_json(task, "policy.json", policy.model_dump())
            if not policy.ok:
                self._set(task, TaskStatus.BLOCKED,
                          reason="security/policy: " + "; ".join(policy.reasons))
                return
            self._set(task, TaskStatus.SECURITY_CHECK, reason="policy passed")

            if not files:
                self._set(task, TaskStatus.FAILED, reason="coder produced no changes")
                return

            # 6. COMMIT + PR
            commit_msg = f"AI task {task.id}: {task.title}\n\nCloses #{task.issue_number}"
            git_ops.commit_all(ws, commit_msg)
            git_ops.push(ws, task.branch)
            pr_body = (f"Automated by the AI Dev Orchestrator.\n\n"
                       f"Closes #{task.issue_number}\n\n"
                       f"## Summary\n{result.summary}")
            task.pr_number = git_ops.open_pr(
                ws, title=f"AI task {task.id}: {task.title}",
                body=pr_body, base=self.profile.repo.base_branch, head=task.branch,
            )
            self._set(task, TaskStatus.PR_OPEN, reason=f"PR #{task.pr_number}")

        # 7. CI
        if task.status == TaskStatus.PR_OPEN:
            sha = git_ops.head_sha(ws)
            self._set(task, TaskStatus.CI_RUNNING, reason=f"head {sha[:7]}")
            ci = wait_for_ci(self.github, sha, self.rules.ci)
            self.audit.write_json(task, "ci_result.json", ci.model_dump())
            next_status = decide_next(task, ci, self.rules)

            if ci.conclusion == CIConclusion.PASSED:
                self._set(task, TaskStatus.CI_PASSED, reason=ci.summary)
            elif next_status == TaskStatus.CI_FAILED:
                task.last_ci_conclusion = ci.summary
                self._set(task, TaskStatus.CI_FAILED,
                          reason=f"CI failed (attempt {task.fix_attempts})")
                if self.github and task.pr_number:
                    self.github.comment_on_pr(task.pr_number,
                                              f"@orchestrator CI failed:\n\n{ci.summary}")
                return self.process_task(task)   # re-enter fix loop
            else:
                self._set(task, next_status, reason=ci.summary)
                return

        # 8. POLICY REVIEW -> HUMAN REVIEW (stop)
        if task.status == TaskStatus.CI_PASSED:
            self._set(task, TaskStatus.POLICY_REVIEW)
            files = git_ops.changed_files(ws) if ws.exists() else []
            policy = policy_reviewer.review(
                task, files, workspace=ws,
                danger_paths=self.profile.paths.danger, block_high_risk=False,
            )
            if not policy.ok:
                self._set(task, TaskStatus.BLOCKED,
                          reason="post-CI policy: " + "; ".join(policy.reasons))
                return
            self._set(task, TaskStatus.HUMAN_REVIEW,
                      reason=f"PR #{task.pr_number} ready for human review")

    # --- LOCAL MODE -------------------------------------------------------
    # Edit the project directory in place. No issue, no clone, no PR, no CI:
    # dispatch -> security check -> run tests -> fix-loop on failure -> stop so
    # the human commits. The PR-mode state machine above is left untouched.
    def process_task_local(self, task: Task) -> None:
        ws = self.local_dir
        log(f"=== task {task.id}: {task.title} (LOCAL, status={task.status.value}) ===")
        self.audit.write_text(task, "task.md", task.body)

        if task.status == TaskStatus.PENDING:
            task.risk = task_classifier.classify(task, self.rules.risk_rules)
            self._set(task, TaskStatus.CLASSIFIED, reason=f"risk={task.risk.value}")
            if task.risk == RiskLevel.HIGH_RISK:
                self._set(task, TaskStatus.BLOCKED, reason="high_risk requires human approval")
                return

        max_attempts = self.rules.fix_loop.max_fix_attempts
        feedback: str | None = None
        while True:
            result = self.dispatcher.dispatch(task, ws, feedback=feedback)
            self.audit.write_text(task, "prompt.md", getattr(self.dispatcher, "last_prompt", ""))
            self.audit.write_text(task, "claude_summary.md", result.summary or result.error or "")

            files = git_ops.changed_files(ws)
            if result.error and not files:
                self._set(task, TaskStatus.FAILED, reason=f"dispatch error: {result.error}")
                return
            if result.error:
                log(f"task {task.id}: dispatch warning (continuing, {len(files)} files changed): {result.error}")
            self.audit.write_text(task, "changed_files.txt", "\n".join(files))
            self._set(task, TaskStatus.CHANGES_READY, reason=f"{len(files)} files changed")

            # security / policy check on the edited files
            policy = policy_reviewer.review(
                task, files, workspace=ws,
                danger_paths=self.profile.paths.danger, block_high_risk=False,
            )
            self.audit.write_json(task, "policy.json", policy.model_dump())
            if not policy.ok:
                self._set(task, TaskStatus.BLOCKED,
                          reason="security/policy: " + "; ".join(policy.reasons))
                return
            if not files:
                self._set(task, TaskStatus.FAILED, reason="coder produced no changes")
                return
            self._set(task, TaskStatus.SECURITY_CHECK, reason="policy passed")

            # run the task's test commands locally
            ok, out = self._run_local_tests(task, ws)
            self.audit.write_text(task, f"test_attempt_{task.fix_attempts}.txt", out)
            if ok:
                self._set(task, TaskStatus.HUMAN_REVIEW,
                          reason="local tests passed — review & commit yourself")
                log(f"task {task.id}: {len(files)} file(s) changed in {ws}. "
                    f"Review with `git diff`, then commit when happy.")
                return

            # test failed -> fix loop
            if task.fix_attempts >= max_attempts:
                self._set(task, TaskStatus.FAILED,
                          reason=f"tests still failing after {max_attempts} attempts")
                return
            task.fix_attempts += 1
            self._save(task)
            feedback = out
            self._set(task, TaskStatus.CI_FAILED,
                      reason=f"local tests failed (attempt {task.fix_attempts})")

    def _run_local_tests(self, task: Task, ws: Path) -> tuple[bool, str]:
        """Run the task's test commands (or the profile's) in ws. Returns (ok, output).
        No test command configured => treated as pass (nothing to verify)."""
        import subprocess
        cmds = task.test_commands or (
            [self.profile.commands["test"]] if "test" in self.profile.commands else []
        )
        if not cmds:
            return True, "(no test command configured; skipping)"
        chunks: list[str] = []
        for cmd in cmds:
            log(f"task {task.id}: running tests: {cmd}")
            proc = subprocess.run(cmd, cwd=str(ws), shell=True,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            chunks.append(f"$ {cmd}\n{proc.stdout}\n{proc.stderr}".strip())
            if proc.returncode != 0:
                return False, "\n\n".join(chunks)
        return True, "\n\n".join(chunks)


HELP_TEXT = """\
BotCoder — cho Claude tự code theo plan, ngay trong dự án của bạn.

CÀI (1 lần, trong dự án của bạn)
  pip install git+https://github.com/khuongvh1-dotcom/BotCoder.git
  runbot init                  # tạo thư mục plan/ + .botcoder/ trong dự án

CÁCH DÙNG
  runbot <lệnh> [tham số]

LỆNH
  init                  Tạo scaffold (plan/ + .botcoder/) trong THƯ MỤC HIỆN TẠI.
  init <repo>           (nâng cao) Tạo profile projects/<id>.yaml cho repo owner/name.
  run                   Liệt kê plan trong plan/, cho chọn, rồi chạy:
                          • Sửa code TRỰC TIẾP trong thư mục này (không clone/PR).
                          • Chạy test; fail thì Claude tự sửa lại (fix loop).
                          • Xong → đổi tên plan thành done_… để lần sau bỏ qua.
  run <repo|đường-dẫn>  (nâng cao) Chế độ GitHub: clone → tạo PR → chờ CI.
                          <…> là owner/name, thư mục có remote, hoặc profile.yaml.
  help                  Hiện hướng dẫn này.

CHỌN PLAN (khi gõ `run`)
  Hiện danh sách plan chưa chạy; gõ SỐ để chọn 1, hoặc 'a' để chạy tất cả.

THAM SỐ CHO `run`
  --plan FILE       Chạy thẳng 1 file plan (bỏ qua bước chọn).
  --rules FILE      File luật (mặc định .botcoder/rules.yaml nếu có).
  --state FILE      File state (mặc định .botcoder/state.json nếu có).
  --stack STACK     Preset khi phải TẠO profile mới (chế độ GitHub).

VÍ DỤ
  runbot init                       # trong dự án -> tạo plan/ + .botcoder/
  runbot run                        # chọn plan, sửa code tại chỗ, chạy test
  runbot run --plan plan/001-x.md   # chạy thẳng 1 plan
  runbot run owner/my-app           # chế độ GitHub: clone + PR
"""

# Conventional locations created by `runbot init` (scaffold mode).
from .scaffold import BOTCODER_DIR, PLAN_DIR


def _default(path_in_botcoder: str, fallback: str) -> str:
    """Prefer .botcoder/<file> when a scaffolded project exists, else the old path."""
    cand = Path(BOTCODER_DIR) / path_in_botcoder
    return str(cand) if cand.exists() else fallback


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="runbot", description="BotCoder", add_help=False)
    sub = p.add_subparsers(dest="command")

    # `run` — default command. No positional => local mode (edit current dir).
    # A positional (owner/name, dir with remote, or profile.yaml) => GitHub mode.
    run_p = sub.add_parser("run", help="Pick a plan and run it (local edits by default)")
    run_p.add_argument("path", nargs="?", default=None,
                       help="(GitHub mode) owner/name, a repo dir, or a profile.yaml")
    run_p.add_argument("--plan", default=None, help="Run this plan file directly (skip the picker)")
    run_p.add_argument("--rules", default=None, help="Path to rules.yaml")
    run_p.add_argument("--state", default=None, help="Path to state.json")
    run_p.add_argument("--stack", default="python",
                       choices=["python", "node", "flutter", "generic"],
                       help="Preset used only when a new profile must be created")
    run_p.add_argument("--all", action="store_true", help="Run all pending plans without asking")

    # `init` — no repo => scaffold the current dir; with repo => create a profile.
    init_p = sub.add_parser("init", aliases=["init-project"],
                            help="Scaffold current dir (or create a profile for owner/name)")
    init_p.add_argument("repo", nargs="?", default=None, help="(optional) owner/name -> profile")
    init_p.add_argument("--id", dest="project_id", default=None, help="Profile id (default: repo name)")
    init_p.add_argument("--stack", default="python",
                        choices=["python", "node", "flutter", "generic"],
                        help="Tech stack preset (commands + danger paths)")
    init_p.add_argument("--base-branch", default=None, help="Override base branch")
    init_p.add_argument("--overwrite", action="store_true", help="Replace existing files")

    sub.add_parser("help", help="Show usage help")

    known = {"run", "init", "init-project", "help", "-h", "--help"}
    if not argv or argv[0] in {"-h", "--help"}:
        argv = ["help"]
    elif argv[0] not in known:
        argv = ["run", *argv]
    return p.parse_args(argv)


def _cmd_init(args: argparse.Namespace) -> int:
    # `init <repo>` -> create a project profile (advanced / GitHub mode).
    if args.repo:
        from .init_project import init_project
        try:
            out = init_project(
                args.repo, project_id=args.project_id, stack=args.stack,
                base_branch=args.base_branch, overwrite=args.overwrite,
            )
        except (ValueError, FileExistsError) as exc:
            log(f"init failed: {exc}")
            return 1
        log(f"created {out}")
        log(f"next: review {out}, then: runbot run {out}")
        return 0

    # `init` (no repo) -> scaffold the current directory.
    from .scaffold import init_scaffold
    written = init_scaffold(".", overwrite=args.overwrite)
    if written:
        for path in written:
            log(f"created {path}")
    else:
        log("scaffold already present (nothing to do; use --overwrite to reset).")
    log("next: viết plan trong plan/, rồi gõ:  runbot run")
    return 0


def _log_auth() -> None:
    # Auth resolution for the SDK dispatcher:
    #   ANTHROPIC_API_KEY > CLAUDE_CODE_OAUTH_TOKEN > existing `claude` CLI login.
    has_oauth = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if has_oauth and has_api_key:
        log("NOTE: both CLAUDE_CODE_OAUTH_TOKEN and ANTHROPIC_API_KEY are set; "
            "ANTHROPIC_API_KEY takes precedence (uses API credits, not your plan).")
    elif not (has_oauth or has_api_key):
        log("auth: using the Claude Code CLI's existing login (subscription). "
            "Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN to override.")


def _select_plans(args: argparse.Namespace) -> list[Path] | None:
    """Resolve which plan file(s) to run. Returns a list, or None to abort.
    --plan picks one directly; otherwise list plan/ and prompt (number | 'a')."""
    from .scaffold import list_plans
    if args.plan:
        pp = Path(args.plan)
        if not pp.exists():
            log(f"plan not found: {pp}")
            return None
        return [pp]

    plans = list_plans()
    if not plans:
        log("Không có plan nào trong plan/ (đã chạy hết hoặc chưa tạo). "
            "Gõ `runbot init` để tạo, hoặc thêm file .md vào plan/.")
        return None
    if args.all:
        return plans

    print("\nPlan chưa chạy:")
    for i, p in enumerate(plans, 1):
        print(f"  [{i}] {p.name}")
    try:
        choice = input("Chọn (số để chạy 1, 'a' = tất cả, Enter để hủy): ")
    except EOFError:
        choice = ""
    # Tolerate a leading BOM, whether decoded as U+FEFF or as cp1252 bytes (ï»¿).
    choice = choice.lstrip("﻿\xef\xbb\xbf").strip().lower()
    if not choice:
        log("đã hủy.")
        return None
    if choice in ("a", "all"):
        return plans
    if choice.isdigit() and 1 <= int(choice) <= len(plans):
        return [plans[int(choice) - 1]]
    log(f"lựa chọn không hợp lệ: {choice!r}")
    return None


def _cmd_run(args: argparse.Namespace) -> int:
    _log_auth()

    # GitHub mode: a positional path was given (owner/name | repo dir | profile.yaml).
    if args.path is not None:
        return _run_github_mode(args)
    # Local mode (default): edit the current directory in place.
    return _run_local_mode(args)


def _run_github_mode(args: argparse.Namespace) -> int:
    from .init_project import resolve_profile
    try:
        profile_path = resolve_profile(args.path, stack=args.stack)
    except (ValueError, FileExistsError) as exc:
        log(f"run failed: {exc}")
        return 1
    if str(profile_path) != args.path:
        log(f"using profile {profile_path}")

    profile = load_profile(profile_path)
    rules = load_rules(args.rules or _default("rules.yaml", "config/rules.yaml"))
    store = StateStore(args.state or _default("state.json", "state.json"))

    plans = _select_plans(args)
    if plans is None:
        return 1

    log(f"repo={profile.repo.full_name} backend={rules.dispatch.backend} mode=github")
    policy = _default("AI_COMPANY_POLICY.md", "company/AI_COMPANY_POLICY.md")
    for plan in plans:
        orch = Orchestrator(profile, rules, store, company_policy_path=policy)
        orch.run(str(plan))
    log("done.")
    return 0


def _run_local_mode(args: argparse.Namespace) -> int:
    from .scaffold import mark_done
    from .init_project import _git_remote_full_name

    cwd = Path(".").resolve()
    # Local mode diffs the working tree to find what Claude edited -> needs git.
    if not (cwd / ".git").exists():
        log(f"{cwd} chưa phải git repo. Chạy `git init` (và commit code hiện có) "
            f"để bot biết file nào vừa đổi và bạn xem được `git diff`.")
        return 1
    rules_path = args.rules or _default("rules.yaml", "config/rules.yaml")
    if not Path(rules_path).exists():
        log(f"chưa có {rules_path}. Gõ `runbot init` trong dự án này trước.")
        return 1
    rules = load_rules(rules_path)
    store = StateStore(args.state or _default("state.json", "state.json"))

    plans = _select_plans(args)
    if plans is None:
        return 1

    profile = _local_profile(cwd, _git_remote_full_name(cwd))
    policy = _default("AI_COMPANY_POLICY.md", "company/AI_COMPANY_POLICY.md")

    log(f"mode=local dir={cwd}")
    for plan in plans:
        log(f"--- plan {plan.name} ---")
        orch = Orchestrator(profile, rules, store, local_dir=cwd,
                            company_policy_path=policy)
        orch.run(str(plan))
        new = mark_done(plan)
        log(f"đánh dấu xong: {plan.name} -> {new.name}")
    log("done. Xem `git diff`, rồi commit khi ưng.")
    return 0


def _local_profile(cwd: Path, full_name: str | None) -> Profile:
    """Build an in-memory profile for local mode from the current directory.
    Uses the git remote (owner/name) if present, else a placeholder."""
    from .config import ProjectMeta, RepoMeta
    if full_name and "/" in full_name:
        owner, name = full_name.split("/", 1)
    else:
        owner, name = "local", cwd.name
    return Profile(
        project=ProjectMeta(id=name, name=name, type="local"),
        repo=RepoMeta(owner=owner, name=name,
                      url=f"https://github.com/{owner}/{name}.git"),
        context_file=str(Path(BOTCODER_DIR) / "AI_PROJECT_CONTEXT.md"),
        workspace_dir="workspace",
    )


def _force_utf8_stdout() -> None:
    """Windows consoles default to cp1252 and choke on the Vietnamese help text.
    Switch stdout/stderr to UTF-8 (with replacement) so output never crashes."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    load_dotenv()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.command == "help":
        print(HELP_TEXT)
        return 0
    if args.command in ("init", "init-project"):
        return _cmd_init(args)
    # default (and explicit `run`)
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
