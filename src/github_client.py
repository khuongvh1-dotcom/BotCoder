"""GitHub API access via PyGithub: labels, issues (idempotent via marker),
PR check runs, and comments.

Auth: prefer GITHUB_TOKEN from the environment; if absent, fall back to the
token from `gh auth token` so a single `gh auth login` is enough.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from github import Github, Auth
from github.Repository import Repository

from .models import Task


def _resolve_token() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        proc = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except FileNotFoundError:
        pass
    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN or run `gh auth login`."
    )


def task_marker(task: Task) -> str:
    return f"<!-- ai-task:{task.plan_id}:{task.id} -->"


class GitHubClient:
    def __init__(self, repo_full_name: str, token: Optional[str] = None):
        self._gh = Github(auth=Auth.Token(token or _resolve_token()))
        self.repo: Repository = self._gh.get_repo(repo_full_name)

    # --- labels ---
    def ensure_label(self, name: str, color: str = "ededed", description: str = "") -> None:
        try:
            self.repo.get_label(name)
        except Exception:
            self.repo.create_label(name=name, color=color, description=description)

    # --- issues (idempotent) ---
    def find_issue_by_marker(self, task: Task) -> Optional[int]:
        marker = task_marker(task)
        # search open + closed issues created by us; marker lives in the body
        for issue in self.repo.get_issues(state="all"):
            if issue.pull_request is not None:
                continue
            if issue.body and marker in issue.body:
                return issue.number
        return None

    def create_issue(self, task: Task, labels: list[str]) -> int:
        existing = self.find_issue_by_marker(task)
        if existing is not None:
            return existing
        body = f"{task.body}\n\n{task_marker(task)}"
        issue = self.repo.create_issue(title=task.title or f"AI task {task.id}",
                                       body=body, labels=labels)
        return issue.number

    def comment_on_issue(self, issue_number: int, body: str) -> None:
        self.repo.get_issue(issue_number).create_comment(body)

    # --- PR / checks ---
    def comment_on_pr(self, pr_number: int, body: str) -> None:
        self.repo.get_pull(pr_number).create_issue_comment(body)

    def get_check_runs(self, ref: str) -> list[dict]:
        """Return a normalized list of check runs for a git ref (commit SHA)."""
        commit = self.repo.get_commit(ref)
        runs = []
        for cr in commit.get_check_runs():
            runs.append({
                "name": cr.name,
                "status": cr.status,            # queued | in_progress | completed
                "conclusion": cr.conclusion,    # success | failure | ... (when completed)
            })
        return runs
