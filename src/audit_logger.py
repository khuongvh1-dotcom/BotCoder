"""Audit trail per task under runs/<date>/task-NNN/.

Writes: prompt.md, claude_summary.md, changed_files.txt, ci_result.json,
decision.json, policy.json. Enough to trace who/what/why without a database.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .models import Task


class AuditLogger:
    def __init__(self, root: str | Path = "runs", today: str | None = None):
        self.root = Path(root)
        # today is injectable for tests; default to the real date.
        self.date = today or date.today().isoformat()

    def run_dir(self, task: Task) -> Path:
        d = self.root / self.date / f"task-{task.id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_text(self, task: Task, name: str, content: str) -> Path:
        path = self.run_dir(task) / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, task: Task, name: str, data: Any) -> Path:
        path = self.run_dir(task) / name
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        return path

    def append_line(self, task: Task, name: str, line: str) -> None:
        path = self.run_dir(task) / name
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line.rstrip("\n") + "\n")
