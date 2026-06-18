"""Local git operations + PR creation via the `git` and `gh` CLIs.

Each task gets its own checkout under workspace/task-NNN so tasks never share a
working tree (foundation for v0.3 parallelism). The orchestrator owns git; the
coder only edits files.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: str | Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise GitError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc


def ensure_clone(repo_url: str, dest: str | Path, base_branch: str = "main") -> Path:
    """Clone repo_url into dest if absent; otherwise fetch + reset to base."""
    dest = Path(dest)
    if (dest / ".git").exists():
        _run(["git", "fetch", "origin"], cwd=dest)
        _run(["git", "checkout", base_branch], cwd=dest)
        _run(["git", "reset", "--hard", f"origin/{base_branch}"], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", repo_url, str(dest)])
        _run(["git", "checkout", base_branch], cwd=dest)
    return dest


def create_branch(cwd: str | Path, branch: str, base_branch: str = "main") -> None:
    """Create (or reset) a branch off base_branch."""
    _run(["git", "checkout", base_branch], cwd=cwd)
    # delete local branch if it exists, then recreate, to keep dispatch idempotent
    _run(["git", "branch", "-D", branch], cwd=cwd, check=False)
    _run(["git", "checkout", "-b", branch], cwd=cwd)


# Build artifacts that aren't meaningful "changes" even if the repo lacks a
# .gitignore. Filtered out so path_guard doesn't flag them.
_ARTIFACT_MARKERS = ("__pycache__/", ".pytest_cache/", ".mypy_cache/")
_ARTIFACT_SUFFIXES = (".pyc", ".pyo")


def _is_artifact(path: str) -> bool:
    p = path.replace("\\", "/")
    return p.endswith(_ARTIFACT_SUFFIXES) or any(m in p + "/" for m in _ARTIFACT_MARKERS)


def changed_files(cwd: str | Path) -> list[str]:
    """Files changed vs HEAD (staged, unstaged, untracked), as repo-relative paths.
    Common build artifacts are filtered out."""
    proc = _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=cwd)
    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # porcelain: "XY path" or "XY orig -> path"
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if _is_artifact(path):
            continue
        files.append(path)
    return files


def commit_all(cwd: str | Path, message: str) -> bool:
    """Stage everything and commit. Returns False if there was nothing to commit."""
    _run(["git", "add", "-A"], cwd=cwd)
    status = _run(["git", "status", "--porcelain"], cwd=cwd)
    if not status.stdout.strip():
        return False
    _run(["git", "commit", "-m", message], cwd=cwd)
    return True


def push(cwd: str | Path, branch: str) -> None:
    _run(["git", "push", "-u", "origin", branch, "--force"], cwd=cwd)


def open_pr(
    cwd: str | Path,
    title: str,
    body: str,
    base: str,
    head: str,
) -> int:
    """Create a PR with gh and return its number. If one already exists for the
    head branch, return that instead (idempotent)."""
    existing = find_pr_for_branch(cwd, head)
    if existing is not None:
        return existing
    _run(
        ["gh", "pr", "create", "--base", base, "--head", head,
         "--title", title, "--body", body],
        cwd=cwd,
    )
    num = find_pr_for_branch(cwd, head)
    if num is None:
        raise GitError(f"PR created but could not resolve number for branch {head}")
    return num


def find_pr_for_branch(cwd: str | Path, head: str) -> Optional[int]:
    proc = _run(
        ["gh", "pr", "list", "--head", head, "--state", "open",
         "--json", "number", "--limit", "1"],
        cwd=cwd,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if data:
        return int(data[0]["number"])
    return None


def head_sha(cwd: str | Path) -> str:
    return _run(["git", "rev-parse", "HEAD"], cwd=cwd).stdout.strip()
