from src.security.path_guard import check, matches


def test_glob_double_star():
    assert matches(".github/workflows/ci.yml", ".github/**")
    assert matches("lib/features/sync/queue.dart", "lib/**/sync/**")
    assert not matches("calc.py", ".github/**")


def test_exact_and_single_star():
    assert matches("pyproject.toml", "pyproject.toml")
    assert matches("src/a.py", "src/*.py")
    assert not matches("src/sub/a.py", "src/*.py")


def test_forbidden_wins():
    v = check(
        changed_files=[".github/workflows/ci.yml"],
        allowed_paths=[".github/**"],          # even if allowed, forbidden wins
        forbidden_paths=[".github/**"],
    )
    assert len(v) == 1
    assert v[0].reason == "forbidden"


def test_outside_allowed():
    v = check(
        changed_files=["calc.py", "secrets.py"],
        allowed_paths=["calc.py"],
        forbidden_paths=[],
    )
    assert len(v) == 1
    assert v[0].file == "secrets.py"
    assert v[0].reason == "outside_allowed"


def test_no_allowed_means_allow_all_except_forbidden():
    v = check(
        changed_files=["anything.py", "deep/nested/file.txt"],
        allowed_paths=[],
        forbidden_paths=["deep/**"],
    )
    assert [x.file for x in v] == ["deep/nested/file.txt"]


def test_clean_change_passes():
    v = check(
        changed_files=["calc.py", "tests/test_calc.py"],
        allowed_paths=["calc.py", "tests/test_calc.py"],
        forbidden_paths=[".github/**", "pyproject.toml"],
    )
    assert v == []
