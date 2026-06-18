"""Rule-based policy review: combine path_guard, secret_scanner, and the risk gate
into a single pass/block decision. Runs on the coder's changes before commit
(security gate) and again after CI passes (final policy check before human review).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..models import RiskLevel, Task
from ..security import path_guard, secret_scanner


class PolicyResult(BaseModel):
    ok: bool
    reasons: list[str] = Field(default_factory=list)
    path_violations: list[dict] = Field(default_factory=list)
    secret_hits: list[dict] = Field(default_factory=list)


def review(
    task: Task,
    changed_files: list[str],
    workspace: str | Path,
    danger_paths: list[str] | None = None,
    block_high_risk: bool = True,
) -> PolicyResult:
    reasons: list[str] = []

    # Risk gate
    if block_high_risk and task.risk == RiskLevel.HIGH_RISK:
        reasons.append("Task classified high_risk; requires human approval before coding.")

    # Path guard (task forbidden + profile danger paths)
    forbidden = list(task.forbidden_paths) + list(danger_paths or [])
    pviol = path_guard.check(changed_files, task.allowed_paths, forbidden)
    if pviol:
        for v in pviol:
            reasons.append(f"Path violation ({v.reason}): {v.file}")

    # Secret scan
    shits = secret_scanner.scan(changed_files, workspace=workspace)
    if shits:
        for h in shits:
            reasons.append(f"Possible secret ({h.rule}) in {h.file}")

    return PolicyResult(
        ok=not reasons,
        reasons=reasons,
        path_violations=[v.model_dump() for v in pviol],
        secret_hits=[h.model_dump() for h in shits],
    )
