"""Rule-based risk classification (no LLM).

Precedence:
  1. If the task declares a Risk in the plan, trust it (but a declared safe task
     that touches high-risk keywords/paths is upgraded to high_risk for safety).
  2. Otherwise infer from high_risk / safe keyword lists in rules, matched against
     the task title, goal, body, and allowed paths.

A high_risk task is returned as RiskLevel.HIGH_RISK; the orchestrator decides
(based on policy) whether high_risk means BLOCKED (wait for a human).
"""

from __future__ import annotations

from .config import RiskRules
from .models import RiskLevel, Task


def _haystack(task: Task) -> str:
    parts = [task.title, task.goal, task.body, *task.allowed_paths, *task.forbidden_paths]
    return "\n".join(p for p in parts if p).lower()


def _matches_any(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in text]


def classify(task: Task, risk_rules: RiskRules) -> RiskLevel:
    text = _haystack(task)
    high_hits = _matches_any(text, risk_rules.high_risk)

    declared = task.risk_declared
    if declared is not None:
        # Trust the declaration, but never let a declared-safe task that clearly
        # touches high-risk territory slip through.
        if declared == RiskLevel.SAFE and high_hits:
            return RiskLevel.HIGH_RISK
        return declared

    if high_hits:
        return RiskLevel.HIGH_RISK
    if _matches_any(text, risk_rules.safe):
        return RiskLevel.SAFE
    return RiskLevel.MEDIUM_RISK
