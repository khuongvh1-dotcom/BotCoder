"""Tests for git_ops logic that doesn't need a real remote: a local repo on disk."""
import shutil
import subprocess

import pytest

from src import git_ops

HAS_GIT = shutil.which("git") is not None
pytestmark = pytest.mark.skipif(not HAS_GIT, reason="git not available")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "t@e.st")
    _git(path, "config", "user.name", "Test")
    (path / "calc.py").write_text("x = 1\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "init")


def test_changed_files_detects_modified_and_untracked(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "calc.py").write_text("x = 2\n", encoding="utf-8")    # modified
    (tmp_path / "new.py").write_text("y = 3\n", encoding="utf-8")     # untracked
    files = set(git_ops.changed_files(tmp_path))
    assert "calc.py" in files
    assert "new.py" in files


def test_commit_all_returns_false_when_clean(tmp_path):
    _init_repo(tmp_path)
    assert git_ops.commit_all(tmp_path, "noop") is False


def test_commit_all_commits_changes(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "calc.py").write_text("x = 99\n", encoding="utf-8")
    assert git_ops.commit_all(tmp_path, "update") is True
    assert git_ops.changed_files(tmp_path) == []


def test_changed_files_filters_build_artifacts(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "calc.py").write_text("x = 2\n", encoding="utf-8")
    pyc_dir = tmp_path / "__pycache__"
    pyc_dir.mkdir()
    (pyc_dir / "calc.cpython-312.pyc").write_bytes(b"\x00\x01")
    files = git_ops.changed_files(tmp_path)
    assert "calc.py" in files
    assert all("__pycache__" not in f and not f.endswith(".pyc") for f in files)


def test_is_artifact():
    assert git_ops._is_artifact("__pycache__/x.pyc")
    assert git_ops._is_artifact("tests/__pycache__/y.cpython-312.pyc")
    assert git_ops._is_artifact("a/b.pyc")
    assert not git_ops._is_artifact("calc.py")
