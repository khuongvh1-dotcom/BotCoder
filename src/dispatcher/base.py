"""Dispatcher interface + the shared 5-layer prompt builder.

Prompt order (most general to most specific):
  1. company/AI_COMPANY_POLICY.md   — company-wide rules
  2. workspace/AI_PROJECT_CONTEXT.md — per-repo context (architecture, commands)
  3. the task body                   — what to do
  4. rules                           — allowed/forbidden paths, test commands
  5. CI feedback (fix loop only)     — why the last attempt failed
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models import DispatchResult, Task


def _read_if_exists(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(
    task: Task,
    workspace: str | Path,
    company_policy_path: str | Path = "company/AI_COMPANY_POLICY.md",
    context_file: str = "AI_PROJECT_CONTEXT.md",
    feedback: Optional[str] = None,
) -> str:
    company = _read_if_exists(company_policy_path)
    context = _read_if_exists(Path(workspace) / context_file)

    parts: list[str] = []
    if company:
        parts.append("# COMPANY POLICY\n" + company.strip())
    if context:
        parts.append("# PROJECT CONTEXT\n" + context.strip())

    parts.append("# TASK\n" + task.body.strip())

    rules_lines = []
    if task.allowed_paths:
        rules_lines.append("Allowed paths (only edit these):")
        rules_lines += [f"- {p}" for p in task.allowed_paths]
    if task.forbidden_paths:
        rules_lines.append("Forbidden paths (never touch):")
        rules_lines += [f"- {p}" for p in task.forbidden_paths]
    if task.test_commands:
        rules_lines.append("Make these pass:")
        rules_lines += [f"- {c}" for c in task.test_commands]
    if rules_lines:
        parts.append("# RULES\n" + "\n".join(rules_lines))

    if feedback:
        parts.append(
            "# CI FEEDBACK (previous attempt failed — fix it)\n" + feedback.strip()
        )

    parts.append(
        "# INSTRUCTIONS\n"
        "Edit files in the working directory to satisfy the task. Do not commit or "
        "push. When done, end with a one-paragraph summary of what you changed."
    )
    return "\n\n".join(parts)


class Dispatcher(ABC):
    @abstractmethod
    def dispatch(
        self,
        task: Task,
        workspace: str | Path,
        feedback: Optional[str] = None,
    ) -> DispatchResult:
        """Run the coder against the workspace. Edits files in place; the caller
        handles git. Returns changed files + a summary (or an error)."""
        raise NotImplementedError
