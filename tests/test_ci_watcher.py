from src.ci_watcher import evaluate_checks, wait_for_ci
from src.config import CIRules
from src.models import CIConclusion


def test_pending_when_required_check_missing():
    res = evaluate_checks([], required=["test"])
    assert res.conclusion == CIConclusion.PENDING


def test_pending_when_in_progress():
    runs = [{"name": "test", "status": "in_progress", "conclusion": None}]
    assert evaluate_checks(runs, ["test"]).conclusion == CIConclusion.PENDING


def test_passed():
    runs = [{"name": "test", "status": "completed", "conclusion": "success"}]
    assert evaluate_checks(runs, ["test"]).conclusion == CIConclusion.PASSED


def test_failed_with_summary():
    runs = [{"name": "test", "status": "completed", "conclusion": "failure"}]
    res = evaluate_checks(runs, ["test"])
    assert res.conclusion == CIConclusion.FAILED
    assert "test" in res.summary


class FakeProvider:
    """Returns a scripted sequence of check-run snapshots."""
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.i = 0

    def get_check_runs(self, ref):
        snap = self.snapshots[min(self.i, len(self.snapshots) - 1)]
        self.i += 1
        return snap


def test_wait_for_ci_polls_until_passed():
    provider = FakeProvider([
        [{"name": "test", "status": "in_progress", "conclusion": None}],
        [{"name": "test", "status": "completed", "conclusion": "success"}],
    ])
    fake_time = {"t": 0.0}
    rules = CIRules(required_checks=["test"], poll_interval_seconds=5, timeout_seconds=100)
    res = wait_for_ci(
        provider, "sha", rules,
        time_fn=lambda: fake_time["t"],
        sleep_fn=lambda s: fake_time.__setitem__("t", fake_time["t"] + s),
    )
    assert res.conclusion == CIConclusion.PASSED


def test_wait_for_ci_times_out():
    provider = FakeProvider([
        [{"name": "test", "status": "in_progress", "conclusion": None}],
    ])
    fake_time = {"t": 0.0}
    rules = CIRules(required_checks=["test"], poll_interval_seconds=20, timeout_seconds=30)
    res = wait_for_ci(
        provider, "sha", rules,
        time_fn=lambda: fake_time["t"],
        sleep_fn=lambda s: fake_time.__setitem__("t", fake_time["t"] + s),
    )
    assert res.conclusion == CIConclusion.TIMEOUT
