from pathlib import Path

from src.models import AgentType, RiskLevel
from src.plan_parser import parse_plan, write_task_files

STRUCTURED = """# Sandbox Plan

## TASK 001: Implement add function
Risk: safe
Repo: ai-sandbox
Parallel: true
Depends on:
- none
Conflict group: core
Estimated size: small
Agent type: coder
Allowed paths:
- calc.py
- tests/test_calc.py
Forbidden paths:
- .github/**
- pyproject.toml
Goal: Hoan thien ham add.
Acceptance criteria:
- add(2, 3) == 5
- pytest pass
Test commands:
- pytest
Rollback note: revert branch.

## TASK 002: Update docs
Risk: safe
Allowed paths:
- docs/**
Goal: Update README.
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_structured_fields(tmp_path):
    tasks = parse_plan(_write(tmp_path, STRUCTURED))
    assert len(tasks) == 2

    t = tasks[0]
    assert t.id == "001"
    assert t.title == "Implement add function"
    assert t.risk_declared == RiskLevel.SAFE
    assert t.parallel is True
    assert t.depends_on == []                       # "none" is dropped
    assert t.conflict_group == "core"
    assert t.agent_type == AgentType.CODER
    assert t.allowed_paths == ["calc.py", "tests/test_calc.py"]
    assert t.forbidden_paths == [".github/**", "pyproject.toml"]
    assert t.acceptance_criteria == ["add(2, 3) == 5", "pytest pass"]
    assert t.test_commands == ["pytest"]
    assert "Hoan thien ham add" in t.goal


def test_second_task_defaults(tmp_path):
    tasks = parse_plan(_write(tmp_path, STRUCTURED))
    t = tasks[1]
    assert t.id == "002"
    assert t.parallel is False                       # default
    assert t.depends_on == []
    assert t.conflict_group is None
    assert t.allowed_paths == ["docs/**"]


def test_plain_heading_fallback(tmp_path):
    text = "## Just do a thing\nSome description without fields.\n"
    tasks = parse_plan(_write(tmp_path, text))
    assert len(tasks) == 1
    assert tasks[0].id == "001"
    assert tasks[0].title == "Just do a thing"


def test_write_task_files_idempotent(tmp_path):
    tasks = parse_plan(_write(tmp_path, STRUCTURED))
    out = tmp_path / "tasks"
    write_task_files(tasks, out)
    f = out / "001_task.md"
    assert f.exists()
    first_mtime = f.stat().st_mtime_ns
    write_task_files(tasks, out)                      # second run, no change
    assert f.stat().st_mtime_ns == first_mtime
    assert tasks[0].file.endswith("tasks/001_task.md")
