"""Load and validate the project profile (projects/*.yaml) and rules (config/rules.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# --- Profile (per-repo) ---------------------------------------------------

class ProjectMeta(BaseModel):
    id: str
    name: str = ""
    type: str = ""


class RepoMeta(BaseModel):
    owner: str
    name: str
    url: str
    base_branch: str = "main"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class Labels(BaseModel):
    task: str = "ai-task"
    pending: str = "pending"


class PathRules(BaseModel):
    danger: list[str] = Field(default_factory=list)
    readonly: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    project: ProjectMeta
    repo: RepoMeta
    branch_prefix: str = "ai-task/"
    labels: Labels = Field(default_factory=Labels)
    commands: dict[str, str] = Field(default_factory=dict)
    paths: PathRules = Field(default_factory=PathRules)
    context_file: str = "AI_PROJECT_CONTEXT.md"
    workspace_dir: str = "workspace"


# --- Rules (shared) -------------------------------------------------------

class CIRules(BaseModel):
    required_checks: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = 15
    timeout_seconds: int = 900


class FixLoopRules(BaseModel):
    max_fix_attempts: int = 3


class MergeRules(BaseModel):
    auto_merge: bool = False


class BudgetRules(BaseModel):
    max_tasks_per_run: int = 1
    max_claude_turns_per_task: int = 5
    max_runtime_minutes_per_task: int = 30
    # Khi coder chạm max_claude_turns_per_task mà chưa xong, gọi tiếp tối đa bấy
    # nhiêu lần để hoàn tất phần dở dang (mỗi lần lại được max_claude_turns lượt).
    max_continue_attempts: int = 3


class ExecutionRules(BaseModel):
    mode: str = "sequential"          # sequential | parallel
    max_parallel_tasks: int = 1
    max_parallel_per_repo: int = 1
    max_parallel_high_risk: int = 0
    allow_parallel_safe_tasks: bool = True


class LockRules(BaseModel):
    enable_path_lock: bool = True
    enable_conflict_group_lock: bool = True


class PlansRules(BaseModel):
    input_glob: str = "plans/**/*.md"
    allow_multiple_plans: bool = True


class RiskRules(BaseModel):
    high_risk: list[str] = Field(default_factory=list)
    safe: list[str] = Field(default_factory=list)


class ClaudeDispatchRules(BaseModel):
    allowed_tools: list[str] = Field(default_factory=lambda: ["Read", "Write", "Edit", "Bash"])
    permission_mode: str = "acceptEdits"


class DispatchRules(BaseModel):
    backend: str = "sdk"              # sdk | action | openhands
    claude: ClaudeDispatchRules = Field(default_factory=ClaudeDispatchRules)


class Rules(BaseModel):
    ci: CIRules = Field(default_factory=CIRules)
    fix_loop: FixLoopRules = Field(default_factory=FixLoopRules)
    merge: MergeRules = Field(default_factory=MergeRules)
    budget: BudgetRules = Field(default_factory=BudgetRules)
    execution: ExecutionRules = Field(default_factory=ExecutionRules)
    locks: LockRules = Field(default_factory=LockRules)
    plans: PlansRules = Field(default_factory=PlansRules)
    risk_rules: RiskRules = Field(default_factory=RiskRules)
    dispatch: DispatchRules = Field(default_factory=DispatchRules)


# --- Loaders --------------------------------------------------------------

def _read_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping at top of {p}, got {type(data).__name__}")
    return data


def load_profile(path: str | Path) -> Profile:
    return Profile.model_validate(_read_yaml(path))


def load_rules(path: str | Path = "config/rules.yaml") -> Rules:
    return Rules.model_validate(_read_yaml(path))
