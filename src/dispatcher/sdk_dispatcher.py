"""SDK backend (MVP): run Claude headless via claude-agent-sdk in the task's
workspace. Claude edits files in place; git is the orchestrator's job.

Needs ANTHROPIC_API_KEY in the environment. The summary returned is Claude's
final result text; changed files are computed by the caller via git status.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from ..models import DispatchResult, Task
from .base import Dispatcher, build_prompt


class SdkDispatcher(Dispatcher):
    def __init__(
        self,
        allowed_tools: Optional[list[str]] = None,
        permission_mode: str = "acceptEdits",
        max_turns: int = 5,
        model: Optional[str] = None,
        company_policy_path: str = "company/AI_COMPANY_POLICY.md",
        context_file: str = "AI_PROJECT_CONTEXT.md",
    ):
        self.allowed_tools = allowed_tools or ["Read", "Write", "Edit", "Bash"]
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        self.model = model
        self.company_policy_path = company_policy_path
        self.context_file = context_file
        self.last_prompt: str = ""

    def dispatch(
        self,
        task: Task,
        workspace: str | Path,
        feedback: Optional[str] = None,
    ) -> DispatchResult:
        prompt = build_prompt(
            task,
            workspace,
            company_policy_path=self.company_policy_path,
            context_file=self.context_file,
            feedback=feedback,
        )
        self.last_prompt = prompt
        try:
            summary, error = asyncio.run(self._run(prompt, workspace))
        except Exception as exc:  # surface SDK/runtime errors to the orchestrator
            return DispatchResult(summary="", error=f"{type(exc).__name__}: {exc}")
        return DispatchResult(summary=summary, error=error)

    async def _run(self, prompt: str, workspace: str | Path) -> tuple[str, Optional[str]]:
        """Run the query to completion. Returns (summary, error). We never raise
        from inside the async generator (that corrupts aclose); instead we record
        the error and let the caller decide — the coder may have edited files even
        when the final result is flagged an error."""
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            allowed_tools=self.allowed_tools,
            permission_mode=self.permission_mode,
            max_turns=self.max_turns,
            model=self.model,
        )
        final_text = ""
        error: Optional[str] = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                if message.is_error:
                    detail = message.result or getattr(message, "subtype", "") or "unknown"
                    errs = getattr(message, "errors", None)
                    error = f"Claude result error ({detail})" + (f": {errs}" if errs else "")
                else:
                    final_text = message.result or final_text
            elif isinstance(message, AssistantMessage):
                texts = [b.text for b in message.content if isinstance(b, TextBlock)]
                if texts:
                    final_text = "\n".join(texts)
        return final_text.strip(), error
