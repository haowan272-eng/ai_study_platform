"""Three-tier Coach memory: Redis hot events, PostgreSQL durable facts, Filesystem export."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import SHORT_TERM_MEMORY_EVENTS, SHORT_TERM_MEMORY_TTL_SECONDS
from app.models import CoachMemory
from app.redis_client import get_redis


def _key(user_id: int | str, session_id: str) -> str:
    return f"coach:short_term:user:{user_id}:{session_id}"


def append_short_term_event(user_id: int | str, session_id: str, event: dict) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        key = _key(user_id, session_id)
        pipe = client.pipeline()
        pipe.rpush(key, json.dumps(event, ensure_ascii=False))
        pipe.ltrim(key, -SHORT_TERM_MEMORY_EVENTS, -1)
        pipe.expire(key, SHORT_TERM_MEMORY_TTL_SECONDS)
        pipe.execute()
    except Exception:
        return


def load_short_term_events(user_id: int | str, session_id: str) -> list[dict]:
    client = get_redis()
    if client is None:
        return []
    try:
        return [json.loads(item) for item in client.lrange(_key(user_id, session_id), 0, -1)]
    except Exception:
        return []


def _upsert_memory(
    db: Session,
    user_id: int,
    learner_id: str,
    key: str,
    category: str,
    value: str,
    session_id: str,
    weight: float = 1.0,
):
    row = db.query(CoachMemory).filter(
        CoachMemory.user_id == user_id,
        CoachMemory.memory_key == key,
        CoachMemory.category == category,
    ).first()
    if row:
        row.learner_id = learner_id
        row.value = value
        row.weight += weight
        row.source_session_id = session_id
    else:
        db.add(CoachMemory(
            user_id=user_id,
            learner_id=learner_id,
            memory_key=key,
            category=category,
            value=value,
            weight=weight,
            source_session_id=session_id,
        ))


def consolidate_learning_memory(db: Session, state: dict) -> None:
    """Turn session outcomes into structured long-term learner memory."""
    user_id = state.get("user_id")
    if user_id is None:
        return
    user_id = int(user_id)
    learner_id = str(state.get("learner_id") or user_id)
    session_id = str(state.get("session_id") or "")
    goal = str(state.get("user_goal") or "").strip()
    if goal:
        _upsert_memory(db, user_id, learner_id, "learning_goal", "goal", goal, session_id)
    for point in state.get("weak_points", []):
        point = str(point)[:255]
        _upsert_memory(db, user_id, learner_id, point, "weak_point", point, session_id, 1.5)
    if float(state.get("score") or 0) >= 60 and state.get("current_topic"):
        topic = str(state["current_topic"])[:255]
        _upsert_memory(db, user_id, learner_id, topic, "mastered_topic", topic, session_id)


def load_learner_memories(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    rows = db.query(CoachMemory).filter(CoachMemory.user_id == user_id).order_by(
        CoachMemory.weight.desc(), CoachMemory.updated_at.desc()
    ).limit(limit).all()
    return [{"key": r.memory_key, "category": r.category, "value": r.value, "weight": r.weight} for r in rows]
