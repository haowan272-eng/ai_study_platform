from app.services.storage import LearningRecordStore


class FakeFiles:
    def __init__(self, state):
        self.state = state

    def read_json(self, path, default=None):
        return self.state

    def write_json(self, path, state):
        self.state = state

    def list_json(self, relative_dir):
        return [{"content": self.state}]


def test_filesystem_fallback_respects_user_id(monkeypatch):
    state = {
        "session_id": "session-a",
        "user_id": 1,
        "learner_id": "user-a",
        "user_goal": "learn agent",
    }
    store = LearningRecordStore()
    store.files = FakeFiles(state)
    monkeypatch.setattr("app.services.storage.SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))

    assert store.get("session-a", user_id=1)["session_id"] == "session-a"
    assert store.get("session-a", user_id=2) is None
