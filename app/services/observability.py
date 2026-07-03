"""Logging, retry and error-event helpers for external dependencies."""
from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

from app.config import LOG_LEVEL

T = TypeVar("T")


class ErrorEvent(BaseModel):
    component: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    error_type: str = ""
    error_message: str = ""
    retry_count: int = Field(default=0, ge=0)
    fallback_used: bool = False
    severity: Literal["info", "warning", "error", "critical"] = "error"
    session_id: str | None = None
    user_id: int | None = None
    agent: str | None = None
    tool: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def record_error_event(event: ErrorEvent) -> None:
    logger = logging.getLogger("app.error_events")
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    if event.severity == "critical":
        logger.critical(payload)
    elif event.severity == "error":
        logger.error(payload)
    elif event.severity == "warning":
        logger.warning(payload)
    else:
        logger.info(payload)


def retry_with_backoff(
    operation: Callable[[], T],
    *,
    component: str,
    operation_name: str,
    attempts: int = 3,
    retryable: Callable[[Exception], bool] | None = None,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 4.0,
    metadata: dict[str, Any] | None = None,
) -> T:
    last_error: Exception | None = None
    total_attempts = max(1, attempts)
    for attempt_index in range(total_attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            retry_count = attempt_index
            can_retry = attempt_index < total_attempts - 1 and (retryable(exc) if retryable else True)
            record_error_event(ErrorEvent(
                component=component,
                operation=operation_name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                retry_count=retry_count,
                fallback_used=False,
                severity="warning" if can_retry else "error",
                metadata=metadata or {},
            ))
            if not can_retry:
                break
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** attempt_index))
            delay += random.uniform(0, delay * 0.2)
            time.sleep(delay)
    assert last_error is not None
    raise last_error


__all__ = [
    "ErrorEvent",
    "configure_logging",
    "get_logger",
    "record_error_event",
    "retry_with_backoff",
]
