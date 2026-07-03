import pytest

from app.services.observability import retry_with_backoff


def test_retry_with_backoff_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr("app.services.observability.time.sleep", lambda _: None)

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("temporary")
        return "ok"

    assert retry_with_backoff(
        flaky,
        component="test",
        operation_name="flaky",
        attempts=3,
        retryable=lambda exc: isinstance(exc, TimeoutError),
    ) == "ok"
    assert calls["count"] == 3


def test_retry_with_backoff_stops_on_non_retryable(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr("app.services.observability.time.sleep", lambda _: None)

    def invalid():
        calls["count"] += 1
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        retry_with_backoff(
            invalid,
            component="test",
            operation_name="invalid",
            attempts=3,
            retryable=lambda exc: isinstance(exc, TimeoutError),
        )
    assert calls["count"] == 1
