"""AI reviewer (v0.2 stub): read the PR diff and comment on out-of-scope edits,
missing tests, hardcoded values, or leaked secrets. Kept as a stub in the MVP;
only policy_reviewer (rule-based) runs now.
"""

from __future__ import annotations

from ..models import Task


def review_diff(task: Task, diff: str) -> list[str]:
    """Return a list of review comments. v0.2 will call Claude here."""
    raise NotImplementedError("ai_reviewer is a v0.2 stub.")
