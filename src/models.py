"""Core data models for the orchestrator.

Enums and the Task model declare every field needed for parallel/multi-agent
operation up front (forward-compatible), even though the MVP only uses a subset
and runs strictly sequential.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Full task lifecycle. The MVP walks the whole chain except DONE
    (a human merges the PR) and only reaches BLOCKED/FAILED on errors."""

    PENDING = "pending"
    CLASSIFIED = "classified"
    ISSUE_CREATED = "issue_created"
    DISPATCHED = "dispatched"
    CHANGES_READY = "changes_ready"
    SECURITY_CHECK = "security_check"
    PR_OPEN = "pr_open"
    CI_RUNNING = "ci_running"
    CI_FAILED = "ci_failed"
    CI_PASSED = "ci_passed"
    POLICY_REVIEW = "policy_review"
    HUMAN_REVIEW = "human_review"
    DONE = "done"
    # terminal error states
    FAILED = "failed"
    BLOCKED = "blocked"


TERMINAL_STATUSES = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.BLOCKED}

# Statuses where the task is parked waiting for a human (not an error, not done).
PARKED_STATUSES = {TaskStatus.HUMAN_REVIEW}


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class AgentType(str, Enum):
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DOC = "doc"
    SECURITY = "security"


class EstimatedSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Task(BaseModel):
    """A unit of work derived from a plan.

    MVP-used fields: id, title, file, body, status, risk, allowed_paths,
    forbidden_paths, issue_number, branch, pr_number, fix_attempts,
    last_ci_conclusion, run_dir. The rest are stored for v0.3+ (parallelism).
    """

    id: str                                  # "001"
    plan_id: str = "plan"
    title: str = ""
    file: str = ""                           # tasks/001_task.md
    body: str = ""                           # full task text sent to the coder

    status: TaskStatus = TaskStatus.PENDING
    risk: Optional[RiskLevel] = None
    risk_declared: Optional[RiskLevel] = None  # risk explicitly written in the plan

    agent_type: AgentType = AgentType.CODER
    parallel: bool = False                   # v0.3 honors this; MVP ignores
    depends_on: list[str] = Field(default_factory=list)
    conflict_group: Optional[str] = None
    estimated_size: Optional[EstimatedSize] = None

    allowed_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)
    goal: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    rollback_note: str = ""

    # runtime bookkeeping
    issue_number: Optional[int] = None
    branch: Optional[str] = None
    pr_number: Optional[int] = None
    fix_attempts: int = 0
    last_ci_conclusion: Optional[str] = None
    run_dir: Optional[str] = None
    updated_at: str = ""


class DispatchResult(BaseModel):
    """Returned by a Dispatcher after the coder runs."""

    changed_files: list[str] = Field(default_factory=list)
    summary: str = ""
    branch: Optional[str] = None
    error: Optional[str] = None
    # True khi coder bị cắt giữa chừng vì chạm giới hạn lượt (max_turns), KHÔNG
    # phải lỗi thật — code có thể đang dở dang. Orchestrator nên gọi tiếp để hoàn
    # tất thay vì đẩy thẳng sang review/commit.
    truncated: bool = False


class CIConclusion(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PENDING = "pending"


class CIResult(BaseModel):
    conclusion: CIConclusion
    summary: str = ""                        # human-readable failure summary for feedback
    checks: list[dict] = Field(default_factory=list)
