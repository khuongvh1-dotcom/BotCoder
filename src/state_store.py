"""Persistent orchestrator state in state.json.

Atomic writes (write to .tmp then os.replace) so a crash never leaves a
half-written file. state.json is the source of truth for resume/idempotency.
Schema version 2 + plans{} + per-task plan_id are present from the start so
v0.2 (multiple plans) needs no migration.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .models import Task

STATE_VERSION = 2


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PlanRef(BaseModel):
    file: str
    hash: str = ""


class State(BaseModel):
    version: int = STATE_VERSION
    repo: str = ""
    updated_at: str = ""
    plans: dict[str, PlanRef] = Field(default_factory=dict)
    tasks: dict[str, Task] = Field(default_factory=dict)

    # --- task helpers ---
    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def upsert_task(self, task: Task) -> None:
        task.updated_at = utcnow_iso()
        self.tasks[task.id] = task


class StateStore:
    def __init__(self, path: str | Path = "state.json"):
        self.path = Path(path)

    def load(self) -> State:
        if not self.path.exists():
            return State()
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return State.model_validate(data)

    def save(self, state: State) -> None:
        state.updated_at = utcnow_iso()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = state.model_dump(mode="json")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
