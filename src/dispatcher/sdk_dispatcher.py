"""SDK backend (MVP): run Claude headless via claude-agent-sdk in the task's
workspace. Claude edits files in place; git is the orchestrator's job.

Needs ANTHROPIC_API_KEY in the environment. The summary returned is Claude's
final result text; changed files are computed by the caller via git status.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from typing import Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    query,
)

from ..models import DispatchResult, Task
from .base import Dispatcher, build_prompt


def _summarize_tool_use(block: "ToolUseBlock") -> str:
    """Tóm tắt một lần Claude gọi tool thành 1 câu tiếng Việt ngắn để in ra terminal.
    Trả về chuỗi kiểu 'Đang sửa map_view.dart' hoặc 'Đang chạy: fvm flutter analyze'."""
    name = getattr(block, "name", "tool")
    inp = getattr(block, "input", {}) or {}

    def _ten_file(val: str) -> str:
        # Chỉ giữ tên file (bỏ đường dẫn dài) cho gọn.
        return (val or "").replace("\\", "/").rsplit("/", 1)[-1]

    # Mỗi tool quy ra một câu tiếng Việt cho người dùng dễ hiểu.
    if name == "Read":
        return f"Đang đọc {_ten_file(inp.get('file_path') or inp.get('path'))}".strip()
    if name == "Edit":
        return f"Đang sửa {_ten_file(inp.get('file_path'))}".strip()
    if name in ("Write", "NotebookEdit"):
        return f"Đang ghi {_ten_file(inp.get('file_path') or inp.get('path'))}".strip()
    if name == "Bash":
        cmd = (inp.get("command") or "").strip().replace("\n", " ")
        return f"Đang chạy lệnh: {cmd[:80]}"
    if name == "Grep":
        return f"Đang tìm '{inp.get('pattern', '')}'"
    if name == "Glob":
        return f"Đang quét file '{inp.get('pattern', '')}'"
    if name in ("TodoWrite",):
        return "Đang lập danh sách việc cần làm"
    # Tool khác: hiển thị tên gốc cho minh bạch.
    return f"Đang dùng công cụ {name}"


class SdkDispatcher(Dispatcher):
    def __init__(
        self,
        allowed_tools: Optional[list[str]] = None,
        permission_mode: str = "acceptEdits",
        max_turns: int = 5,
        model: Optional[str] = None,
        company_policy_path: str = "company/AI_COMPANY_POLICY.md",
        context_file: str = "AI_PROJECT_CONTEXT.md",
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        self.allowed_tools = allowed_tools or ["Read", "Write", "Edit", "Bash"]
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        self.model = model
        self.company_policy_path = company_policy_path
        self.context_file = context_file
        # Callback in tiến trình từng bước (tool Claude gọi). None = im lặng như cũ.
        self.on_progress = on_progress
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
        # Hàm in tiến trình (no-op nếu không có callback) — để biết Claude đang làm gì.
        emit = self.on_progress or (lambda _msg: None)

        from ..spinner import Spinner
        # Spinner chạy nền: dấu chấm nhảy + nhãn 'Claude đang làm gì' để biết còn sống.
        spin = Spinner("Claude đang suy nghĩ").start()

        def _emit(msg: str) -> None:
            """In 1 dòng log cố định, tạm dừng spinner để không bị đè ký tự."""
            spin.stop()
            emit(msg)
            spin.set_label(msg)
            spin.start()

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    if message.is_error:
                        detail = message.result or getattr(message, "subtype", "") or "unknown"
                        errs = getattr(message, "errors", None)
                        error = f"Claude result error ({detail})" + (f": {errs}" if errs else "")
                    else:
                        final_text = message.result or final_text
                elif isinstance(message, AssistantMessage):
                    # Duyệt từng block: tool-use -> 'đang sửa file X'; text -> tóm tắt.
                    for b in message.content:
                        if isinstance(b, ToolUseBlock):
                            _emit(_summarize_tool_use(b))
                        elif isinstance(b, ThinkingBlock):
                            # Claude đang suy luận -> chỉ đổi nhãn spinner, không in log dài.
                            spin.set_label("Claude đang suy nghĩ")
                        elif isinstance(b, TextBlock) and b.text.strip():
                            final_text = b.text
                            # in 1 dòng đầu của đoạn Claude nói cho người dùng theo dõi
                            first = b.text.strip().splitlines()[0]
                            _emit(f"💬 {first[:100]}")
        finally:
            spin.stop()
        return final_text.strip(), error
