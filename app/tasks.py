"""Celery tasks for the Learning Coach."""
from __future__ import annotations

from app.celery_app import celery_app
from app.config import CELERY_TASK_MAX_RETRIES
from app.redis_client import init_redis
from app.services.observability import ErrorEvent, configure_logging, record_error_event


@celery_app.task(
    bind=True,
    name="learning_coach.run_learning_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=CELERY_TASK_MAX_RETRIES,
)
def run_learning_task(self, session_id: str, state: dict, event: dict | None = None) -> None:
    configure_logging()
    try:
        init_redis()
    except Exception as exc:
        record_error_event(ErrorEvent(
            component="celery",
            operation="init_redis",
            error_type=type(exc).__name__,
            error_message=str(exc),
            fallback_used=True,
            severity="warning",
            session_id=session_id,
        ))

    from app.api.learning_coach import _run_learning_task

    state = dict(state)
    state["current_task_id"] = self.request.id or state.get("current_task_id", "")
    _run_learning_task(session_id, state, event)


__all__ = ["run_learning_task"]
