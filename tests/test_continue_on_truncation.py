"""Khi coder hết lượt (max_turns) mà chưa xong, orchestrator phải GỌI TIẾP để
hoàn tất, không đẩy code dở dang sang test/commit. Đây là regression test cho
hành vi đó — chỉ chạy logic vòng lặp, không đụng SDK hay mạng."""

from pathlib import Path

from src.config import Rules
from src.main import Orchestrator
from src.models import DispatchResult, Task


class _FakeDispatcher:
    """Trả về 'truncated' cho `truncate_first` lần đầu, rồi trả kết quả xong.
    Ghi lại feedback của mỗi lần gọi để kiểm tra prompt 'làm tiếp'."""

    def __init__(self, truncate_first: int):
        self.truncate_first = truncate_first
        self.calls: list[str | None] = []
        self.last_prompt = ""

    def dispatch(self, task, workspace, feedback=None):
        self.calls.append(feedback)
        if len(self.calls) <= self.truncate_first:
            return DispatchResult(summary="dở dang", truncated=True)
        return DispatchResult(summary="xong", truncated=False)


def _orch(dispatcher, max_continue: int) -> Orchestrator:
    """Orchestrator tối thiểu: chỉ cần .rules.budget và .dispatcher cho hàm này."""
    orch = Orchestrator.__new__(Orchestrator)
    orch.rules = Rules()
    orch.rules.budget.max_continue_attempts = max_continue
    orch.dispatcher = dispatcher
    return orch


def test_continues_until_finished():
    fake = _FakeDispatcher(truncate_first=2)
    orch = _orch(fake, max_continue=3)
    result = orch._dispatch_to_completion(Task(id="001"), Path("."), feedback=None)
    assert result.truncated is False          # cuối cùng đã xong
    assert len(fake.calls) == 3               # 1 lần đầu + 2 lần nối tiếp
    # Các lần nối tiếp phải mang feedback 'CONTINUE' để Claude làm nốt, không làm lại.
    assert fake.calls[0] is None
    assert "CONTINUE" in (fake.calls[1] or "")
    assert "CONTINUE" in (fake.calls[2] or "")


def test_stops_at_max_continue_and_returns_truncated():
    fake = _FakeDispatcher(truncate_first=99)   # không bao giờ xong
    orch = _orch(fake, max_continue=3)
    result = orch._dispatch_to_completion(Task(id="001"), Path("."), feedback=None)
    assert result.truncated is True             # vẫn dở sau khi nối hết lượt
    assert len(fake.calls) == 4                 # 1 lần đầu + đúng 3 lần nối tiếp


def test_no_continue_when_first_run_finishes():
    fake = _FakeDispatcher(truncate_first=0)
    orch = _orch(fake, max_continue=3)
    result = orch._dispatch_to_completion(Task(id="001"), Path("."), feedback=None)
    assert result.truncated is False
    assert len(fake.calls) == 1                 # không gọi tiếp khi đã xong ngay


def test_existing_feedback_is_preserved_in_continue():
    fake = _FakeDispatcher(truncate_first=1)
    orch = _orch(fake, max_continue=3)
    orch._dispatch_to_completion(Task(id="001"), Path("."), feedback="LỖI TEST CŨ")
    # Lần nối tiếp phải giữ lại feedback gốc + thêm hướng dẫn CONTINUE.
    assert "LỖI TEST CŨ" in (fake.calls[1] or "")
    assert "CONTINUE" in (fake.calls[1] or "")
