"""LLM gateway with retry, structured error events and deterministic fallback."""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from app.config import (
    COACH_LLM_API_KEY,
    COACH_LLM_BASE_URL,
    COACH_LLM_MODEL,
    COACH_LLM_RETRY_ATTEMPTS,
    COACH_LLM_TEMPERATURE,
)
from app.services.observability import ErrorEvent, get_logger, record_error_event, retry_with_backoff

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _model():
    if not COACH_LLM_API_KEY:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=COACH_LLM_API_KEY,
        base_url=COACH_LLM_BASE_URL,
        model=COACH_LLM_MODEL,
        temperature=COACH_LLM_TEMPERATURE,
        max_tokens=3000,
    )


def _extract_json(text: str) -> Any:
    cleaned = (text or "").replace("```json", "").replace("```", "").strip()
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.S)
    return json.loads(match.group(1) if match else cleaned)


def _record_missing_key(operation: str) -> None:
    record_error_event(ErrorEvent(
        component="llm",
        operation=operation,
        error_type="MissingApiKey",
        error_message="COACH_LLM_API_KEY is not configured",
        fallback_used=True,
        severity="info",
        metadata={"model": COACH_LLM_MODEL},
    ))


def invoke_json(system_prompt: str, payload: dict, fallback: Any) -> Any:
    """Return parsed JSON; failures retry first and then degrade to fallback data."""
    model = _model()
    if model is None:
        _record_missing_key("invoke_json")
        return copy.deepcopy(fallback)
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        response = retry_with_backoff(
            lambda: model.invoke([
                SystemMessage(content=system_prompt + "\nOnly output valid JSON. Do not use Markdown code fences."),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]),
            component="llm",
            operation_name="invoke_json",
            attempts=COACH_LLM_RETRY_ATTEMPTS,
            metadata={"model": COACH_LLM_MODEL},
        )
        return _extract_json(str(response.content))
    except Exception as exc:
        record_error_event(ErrorEvent(
            component="llm",
            operation="invoke_json",
            error_type=type(exc).__name__,
            error_message=str(exc),
            retry_count=max(0, COACH_LLM_RETRY_ATTEMPTS - 1),
            fallback_used=True,
            severity="warning",
            metadata={"model": COACH_LLM_MODEL},
        ))
        logger.warning("LLM JSON invocation failed, using fallback")
        return copy.deepcopy(fallback)


def invoke_text(system_prompt: str, payload: dict, fallback: str) -> str:
    """Return text; failures retry first and then degrade to fallback text."""
    model = _model()
    if model is None:
        _record_missing_key("invoke_text")
        return str(fallback)
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        response = retry_with_backoff(
            lambda: model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]),
            component="llm",
            operation_name="invoke_text",
            attempts=COACH_LLM_RETRY_ATTEMPTS,
            metadata={"model": COACH_LLM_MODEL},
        )
        return str(response.content).strip() or str(fallback)
    except Exception as exc:
        record_error_event(ErrorEvent(
            component="llm",
            operation="invoke_text",
            error_type=type(exc).__name__,
            error_message=str(exc),
            retry_count=max(0, COACH_LLM_RETRY_ATTEMPTS - 1),
            fallback_used=True,
            severity="warning",
            metadata={"model": COACH_LLM_MODEL},
        ))
        logger.warning("LLM text invocation failed, using fallback")
        return str(fallback)


__all__ = ["invoke_json", "invoke_text"]
