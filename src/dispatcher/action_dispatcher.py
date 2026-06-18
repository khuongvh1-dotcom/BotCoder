"""Action backend (v0.2 stub): trigger the Claude Code GitHub Action by posting
an "@claude ..." comment on the issue/PR, then let the orchestrator poll for the
resulting PR. Asynchronous by nature — kept as a stub so the Dispatcher interface
stays swappable for the cloud/cron deployment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import DispatchResult, Task
from .base import Dispatcher


class ActionDispatcher(Dispatcher):
    def __init__(self, *args, **kwargs):
        # Will hold a GitHubClient + trigger phrase in v0.2.
        pass

    def dispatch(
        self,
        task: Task,
        workspace: str | Path,
        feedback: Optional[str] = None,
    ) -> DispatchResult:
        raise NotImplementedError(
            "ActionDispatcher is a v0.2 stub. Use dispatch.backend=sdk for the MVP."
        )
