"""Parse a plan.md into Task objects and write per-task files.

Structured format (preferred), one block per task:

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
    Forbidden paths:
    - .github/**
    Goal: ...
    Acceptance criteria:
    - ...
    Test commands:
    - pytest
    Rollback note: ...

Missing fields fall back to defaults. A plain `## Heading` block (no fields)
is still parsed: its title + body become the task, everything else defaults.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import AgentType, EstimatedSize, RiskLevel, Task

# A task block starts at a level-2 heading.
_HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)
# "TASK 001: title" or "TASK 1 - title" etc.
_TASK_TITLE_RE = re.compile(r"^TASK\s+(\w+)\s*[:\-]?\s*(.*)$", re.IGNORECASE)

# Single-value "Key: value" fields.
_SCALAR_FIELDS = {
    "risk": "risk",
    "repo": "repo",
    "conflict group": "conflict_group",
    "estimated size": "estimated_size",
    "agent type": "agent_type",
    "parallel": "parallel",
    "goal": "goal",
    "rollback note": "rollback_note",
}
# List fields: "Key:" followed by "- item" lines.
_LIST_FIELDS = {
    "depends on": "depends_on",
    "allowed paths": "allowed_paths",
    "forbidden paths": "forbidden_paths",
    "acceptance criteria": "acceptance_criteria",
    "test commands": "test_commands",
}
_ALL_FIELD_KEYS = set(_SCALAR_FIELDS) | set(_LIST_FIELDS)


def plan_hash(plan_path: str | Path) -> str:
    data = Path(plan_path).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """Return list of (heading, body) for each level-2 heading block."""
    blocks: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        blocks.append((heading, body))
    return blocks


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "y"}


def _coerce_enum(enum_cls, value: str, default):
    try:
        return enum_cls(value.strip().lower())
    except ValueError:
        return default


def _parse_fields(body: str) -> dict:
    """Parse 'Key: value' scalars and 'Key:' + '- item' lists from a block body."""
    fields: dict = {}
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        m = re.match(r"^([A-Za-z][\w ]*?)\s*:\s*(.*)$", stripped)
        if not m:
            i += 1
            continue

        key = m.group(1).strip().lower()
        inline = m.group(2).strip()

        if key in _LIST_FIELDS:
            items: list[str] = []
            if inline:                       # allow "Key: a, b" on one line
                items.extend(p.strip() for p in inline.split(",") if p.strip())
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt.startswith("- "):
                    item = nxt[2:].strip()
                    if item.lower() != "none":
                        items.append(item)
                    j += 1
                elif nxt == "":
                    j += 1
                    # stop list only if the following non-empty line is a field
                    look = j
                    while look < len(lines) and not lines[look].strip():
                        look += 1
                    if look < len(lines) and not lines[look].strip().startswith("- "):
                        break
                else:
                    break
            fields[_LIST_FIELDS[key]] = items
            i = j
            continue

        if key in _SCALAR_FIELDS:
            fields[_SCALAR_FIELDS[key]] = inline
        i += 1
    return fields


def _build_task(heading: str, body: str, index: int) -> Task:
    title_match = _TASK_TITLE_RE.match(heading)
    if title_match:
        raw_id = title_match.group(1)
        title = title_match.group(2).strip() or heading
        task_id = raw_id.zfill(3) if raw_id.isdigit() else raw_id
    else:
        title = heading
        task_id = str(index + 1).zfill(3)

    fields = _parse_fields(body)

    risk_declared = None
    if "risk" in fields:
        risk_declared = _coerce_enum(RiskLevel, fields["risk"], None)

    task = Task(
        id=task_id,
        title=title,
        body=f"## {heading}\n\n{body}".strip(),
        risk_declared=risk_declared,
        agent_type=_coerce_enum(AgentType, fields.get("agent_type", "coder"), AgentType.CODER),
        parallel=_parse_bool(fields.get("parallel", "false")),
        depends_on=fields.get("depends_on", []),
        conflict_group=(fields.get("conflict_group") or None),
        estimated_size=_coerce_enum(EstimatedSize, fields.get("estimated_size", ""), None),
        allowed_paths=fields.get("allowed_paths", []),
        forbidden_paths=fields.get("forbidden_paths", []),
        goal=fields.get("goal", ""),
        acceptance_criteria=fields.get("acceptance_criteria", []),
        test_commands=fields.get("test_commands", []),
        rollback_note=fields.get("rollback_note", ""),
    )
    return task


def parse_plan(plan_path: str | Path, plan_id: str = "plan") -> list[Task]:
    text = Path(plan_path).read_text(encoding="utf-8")
    blocks = _split_blocks(text)
    tasks: list[Task] = []
    for index, (heading, body) in enumerate(blocks):
        # Skip a top-of-file title heading that has no field-like content and
        # is not a TASK heading (e.g. "# Sandbox Plan" rendered as "##"? no).
        task = _build_task(heading, body, index)
        task.plan_id = plan_id
        tasks.append(task)
    return tasks


def write_task_files(tasks: list[Task], tasks_dir: str | Path = "tasks") -> None:
    """Write tasks/NNN_task.md. Idempotent: skip if identical content exists."""
    d = Path(tasks_dir)
    d.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        path = d / f"{task.id}_task.md"
        task.file = str(path).replace("\\", "/")
        content = task.body.rstrip() + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
