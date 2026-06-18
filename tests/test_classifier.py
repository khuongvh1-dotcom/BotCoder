from src.config import RiskRules
from src.models import RiskLevel, Task
from src.task_classifier import classify

RULES = RiskRules(
    high_risk=["database migration", "auth", "payment", "RLS"],
    safe=["docs", "tests", "pure function"],
)


def test_declared_risk_trusted():
    t = Task(id="001", title="Tweak label", risk_declared=RiskLevel.SAFE)
    assert classify(t, RULES) == RiskLevel.SAFE


def test_declared_safe_upgraded_when_touches_high_risk():
    t = Task(id="001", title="Update auth flow", risk_declared=RiskLevel.SAFE,
             goal="change auth token handling")
    assert classify(t, RULES) == RiskLevel.HIGH_RISK


def test_inferred_high_risk_from_keyword():
    t = Task(id="001", title="Add payment webhook", goal="handle payment")
    assert classify(t, RULES) == RiskLevel.HIGH_RISK


def test_inferred_safe():
    t = Task(id="001", title="Improve docs", goal="update docs and tests")
    assert classify(t, RULES) == RiskLevel.SAFE


def test_unknown_defaults_medium():
    t = Task(id="001", title="Refactor widget layout", goal="move a button")
    assert classify(t, RULES) == RiskLevel.MEDIUM_RISK


def test_high_risk_path_in_allowed_paths():
    t = Task(id="001", title="Edit RLS", allowed_paths=["supabase/RLS/policy.sql"])
    assert classify(t, RULES) == RiskLevel.HIGH_RISK
