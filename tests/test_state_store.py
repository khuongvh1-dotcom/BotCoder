from src.models import Task, TaskStatus
from src.state_store import State, StateStore, STATE_VERSION


def test_save_and_load_roundtrip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = State(repo="owner/repo")
    state.upsert_task(Task(id="001", title="t", status=TaskStatus.PR_OPEN, pr_number=7))
    store.save(state)

    loaded = store.load()
    assert loaded.version == STATE_VERSION
    assert loaded.repo == "owner/repo"
    t = loaded.get_task("001")
    assert t is not None
    assert t.status == TaskStatus.PR_OPEN
    assert t.pr_number == 7
    assert t.updated_at != ""


def test_load_missing_returns_empty(tmp_path):
    store = StateStore(tmp_path / "nope.json")
    state = store.load()
    assert state.tasks == {}
    assert state.version == STATE_VERSION


def test_save_is_atomic_no_tmp_left(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save(State(repo="a/b"))
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
