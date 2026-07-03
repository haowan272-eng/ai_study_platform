from app.services import coach_memory


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.pending = []

    def pipeline(self):
        return self

    def rpush(self, key, value):
        self.values.setdefault(key, []).append(value)
        return self

    def ltrim(self, key, start, end):
        self.values[key] = self.values.get(key, [])[start:]
        return self

    def expire(self, key, ttl):
        self.ttl = ttl
        return self

    def execute(self):
        return []

    def lrange(self, key, start, end):
        return self.values.get(key, [])


def test_short_term_learning_event_round_trip(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(coach_memory, "get_redis", lambda: client)
    coach_memory.append_short_term_event("learner", "session", {"event": "quiz", "score": 80})
    assert coach_memory.load_short_term_events("learner", "session") == [
        {"event": "quiz", "score": 80}
    ]
    assert client.ttl == coach_memory.SHORT_TERM_MEMORY_TTL_SECONDS


def test_short_term_memory_degrades_without_redis(monkeypatch):
    monkeypatch.setattr(coach_memory, "get_redis", lambda: None)
    coach_memory.append_short_term_event("learner", "session", {"event": "start"})
    assert coach_memory.load_short_term_events("learner", "session") == []
