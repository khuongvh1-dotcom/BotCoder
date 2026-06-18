from src.config import Rules
from src.models import CIConclusion, CIResult, Task, TaskStatus
from src.reviewer import decide_next

RULES = Rules()  # defaults: max_fix_attempts=3


def _ci(conclusion):
    return CIResult(conclusion=conclusion)


def test_passed_goes_to_policy_review():
    t = Task(id="001")
    assert decide_next(t, _ci(CIConclusion.PASSED), RULES) == TaskStatus.POLICY_REVIEW


def test_failed_with_attempts_left_retries():
    t = Task(id="001", fix_attempts=1)
    assert decide_next(t, _ci(CIConclusion.FAILED), RULES) == TaskStatus.CI_FAILED


def test_failed_at_max_attempts_fails():
    t = Task(id="001", fix_attempts=3)
    assert decide_next(t, _ci(CIConclusion.FAILED), RULES) == TaskStatus.FAILED


def test_timeout_fails():
    t = Task(id="001")
    assert decide_next(t, _ci(CIConclusion.TIMEOUT), RULES) == TaskStatus.FAILED
