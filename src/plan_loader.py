"""plan_loader (v0.2 stub): gather plans/**/*.md into tasks with per-plan plan_id.

The MVP reads a single --plan file in main.py. This module will, at v0.2, glob
multiple plan files (rules.plans.input_glob) and assign each a stable plan_id.
"""

from __future__ import annotations

from pathlib import Path

from .models import Task
from .plan_parser import parse_plan


def load_all(input_glob: str = "plans/**/*.md") -> list[Task]:
    tasks: list[Task] = []
    for path in sorted(Path().glob(input_glob)):
        plan_id = path.stem
        tasks.extend(parse_plan(path, plan_id=plan_id))
    return tasks
