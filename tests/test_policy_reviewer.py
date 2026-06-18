"""Integration of path_guard + secret_scanner + risk gate via policy_reviewer."""
from src.models import RiskLevel, Task
from src.reviewers.policy_reviewer import review


def test_clean_change_passes(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    task = Task(id="001", allowed_paths=["calc.py"], forbidden_paths=[".github/**"],
                risk=RiskLevel.SAFE)
    res = review(task, ["calc.py"], workspace=tmp_path)
    assert res.ok
    assert res.reasons == []


def test_path_violation_blocks(tmp_path):
    (tmp_path / "calc.py").write_text("x=1\n", encoding="utf-8")
    task = Task(id="001", allowed_paths=["calc.py"], forbidden_paths=[".github/**"])
    res = review(task, ["calc.py", ".github/workflows/ci.yml"], workspace=tmp_path,
                 danger_paths=[".github/**"])
    assert not res.ok
    assert any("Path violation" in r for r in res.reasons)


def test_secret_blocks(tmp_path):
    (tmp_path / "calc.py").write_text("ANTHROPIC_API_KEY=sk-ant-leakedsecret123\n", encoding="utf-8")
    task = Task(id="001", allowed_paths=["calc.py"])
    res = review(task, ["calc.py"], workspace=tmp_path)
    assert not res.ok
    assert any("secret" in r.lower() for r in res.reasons)


def test_high_risk_blocks_when_enabled(tmp_path):
    task = Task(id="001", allowed_paths=["calc.py"], risk=RiskLevel.HIGH_RISK)
    res = review(task, ["calc.py"], workspace=tmp_path, block_high_risk=True)
    assert not res.ok
    assert any("high_risk" in r for r in res.reasons)


def test_danger_path_from_profile_blocks(tmp_path):
    (tmp_path / "x.py").write_text("x=1\n", encoding="utf-8")
    task = Task(id="001")          # no allowed_paths -> allow all except forbidden/danger
    res = review(task, ["pyproject.toml"], workspace=tmp_path, danger_paths=["pyproject.toml"])
    assert not res.ok
