import pytest
import yaml

from src.config import Profile
from src.init_project import build_profile_yaml, init_project


def test_build_yaml_python_preset_is_valid_profile():
    text = build_profile_yaml(
        project_id="myapp", owner="me", name="myapp",
        url="https://github.com/me/myapp.git", base_branch="main", stack="python",
    )
    data = yaml.safe_load(text)
    profile = Profile.model_validate(data)          # must validate
    assert profile.repo.full_name == "me/myapp"
    assert profile.commands["test"] == "pytest"
    assert ".github/**" in profile.paths.danger


def test_build_yaml_flutter_preset():
    text = build_profile_yaml(
        project_id="bts", owner="me", name="bts",
        url="https://github.com/me/bts.git", base_branch="main", stack="flutter",
    )
    profile = Profile.model_validate(yaml.safe_load(text))
    assert profile.commands["test"] == "flutter test"
    assert any("migrations" in p for p in profile.paths.danger)


def test_init_project_writes_file(tmp_path, monkeypatch):
    # Force the gh lookup to fail so it uses fallback values (no network).
    monkeypatch.setattr("src.init_project._gh_repo_info", lambda full: None)
    out = init_project("owner/repo", stack="python", out_dir=tmp_path / "projects")
    assert out.exists()
    profile = Profile.model_validate(yaml.safe_load(out.read_text(encoding="utf-8")))
    assert profile.repo.owner == "owner"
    assert profile.repo.name == "repo"


def test_init_project_rejects_bad_repo(tmp_path, monkeypatch):
    monkeypatch.setattr("src.init_project._gh_repo_info", lambda full: None)
    with pytest.raises(ValueError):
        init_project("noslash", out_dir=tmp_path)


def test_init_project_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr("src.init_project._gh_repo_info", lambda full: None)
    init_project("owner/repo", out_dir=tmp_path)
    with pytest.raises(FileExistsError):
        init_project("owner/repo", out_dir=tmp_path)
