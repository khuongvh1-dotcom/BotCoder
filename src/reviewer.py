"""Transition logic for a task after CI runs. Pure function — easy to test.

- CI passed  -> POLICY_REVIEW (the loop then runs policy_reviewer -> HUMAN_REVIEW)
- CI failed  -> if fix attempts remain: CI_FAILED (re-dispatch with feedback)
               else: FAILED
- CI timeout -> FAILED (don't pretend it passed)
"""

from __future__ import annotations

from .config import Rules
from .models import CIConclusion, CIResult, Task, TaskStatus


def decide_next(task: Task, ci: CIResult, rules: Rules) -> TaskStatus:
    if ci.conclusion == CIConclusion.PASSED:
        return TaskStatus.POLICY_REVIEW
    if ci.conclusion == CIConclusion.TIMEOUT:
        return TaskStatus.FAILED
    if ci.conclusion == CIConclusion.FAILED:
        if task.fix_attempts < rules.fix_loop.max_fix_attempts:
            return TaskStatus.CI_FAILED
        return TaskStatus.FAILED
    # PENDING shouldn't reach here (wait_for_ci resolves it), but be safe.
    return TaskStatus.CI_RUNNING
