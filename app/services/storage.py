"""PostgreSQL-primary Coach store with Filesystem MCP archive fallback."""
from __future__ import annotations

import json

from app.database import SessionLocal
from app.mcp.filesystem_client import FilesystemMCPClient
from app.models import CoachArtifact, CoachAssessment, CoachSession
from app.schemas.contracts import dump_state
from app.services.coach_memory import consolidate_learning_memory, load_learner_memories
from app.services.observability import ErrorEvent, get_logger, record_error_event


logger = get_logger(__name__)


class LearningRecordStore:
    def __init__(self):
        self.files = FilesystemMCPClient()

    def save(self, session_id: str, state: dict) -> None:
        state = dump_state(state)
        encoded = json.dumps(state, ensure_ascii=False)
        db = None
        state_user_id = None
        saved_to_db = False
        try:
            db = SessionLocal()
            try:
                state_user_id = int(state["user_id"]) if state.get("user_id") is not None else None
            except (TypeError, ValueError):
                state_user_id = None
            row = db.query(CoachSession).filter(CoachSession.id == session_id).first()
            if row is None:
                row = CoachSession(
                    id=session_id,
                    user_id=state_user_id,
                    learner_id=str(state.get("learner_id") or "anonymous"),
                    user_goal=str(state.get("user_goal") or ""),
                    state_json=encoded,
                )
                db.add(row)
            row.user_id = state_user_id
            row.learner_id = str(state.get("learner_id") or row.learner_id or "anonymous")
            row.current_topic = state.get("current_topic")
            row.status = str(state.get("status") or "started")
            row.score = state.get("score")
            row.state_json = encoded
            db.flush()
            for kind, key in (
                ("learning_plan", "learning_plan"),
                ("repo_analysis", "repo_analysis"),
                ("project_task", "project_task"),
                ("learning_report", "learning_report"),
                ("interview", "interview_questions"),
            ):
                content = state.get(key)
                if not content:
                    continue
                artifact = db.query(CoachArtifact).filter(
                    CoachArtifact.session_id == session_id,
                    CoachArtifact.artifact_type == kind,
                ).first()
                if artifact is None:
                    artifact = CoachArtifact(session_id=session_id, artifact_type=kind, content_json="")
                    db.add(artifact)
                artifact.content_json = json.dumps(content, ensure_ascii=False)
            if state.get("score") is not None and state.get("user_answers"):
                db.add(CoachAssessment(
                    session_id=session_id,
                    answers_json=json.dumps(state["user_answers"], ensure_ascii=False),
                    score=float(state["score"]),
                    weak_points_json=json.dumps(state.get("weak_points", []), ensure_ascii=False),
                ))
                consolidate_learning_memory(db, state)
            db.commit()
            saved_to_db = True
        except Exception as exc:
            if db is not None:
                db.rollback()
            record_error_event(ErrorEvent(
                component="storage",
                operation="save",
                error_type=type(exc).__name__,
                error_message=str(exc),
                fallback_used=True,
                severity="warning",
                session_id=session_id,
                user_id=state_user_id,
            ))
            logger.warning("Database save unavailable, archived to filesystem")
        finally:
            if db is not None:
                db.close()
        if not saved_to_db:
            self.files.write_json(f"sessions/{session_id}.json", state)

    def get(self, session_id: str, user_id: int | None = None) -> dict | None:
        db = None
        try:
            db = SessionLocal()
            query = db.query(CoachSession).filter(CoachSession.id == session_id)
            if user_id is not None:
                query = query.filter(CoachSession.user_id == user_id)
            row = query.first()
            if row:
                return dump_state(json.loads(row.state_json))
        except Exception as exc:
            record_error_event(ErrorEvent(
                component="storage",
                operation="get",
                error_type=type(exc).__name__,
                error_message=str(exc),
                fallback_used=True,
                severity="warning",
                session_id=session_id,
                user_id=user_id,
            ))
            logger.warning("Database read unavailable, using filesystem")
        finally:
            if db is not None:
                db.close()
        state = self.files.read_json(f"sessions/{session_id}.json", default=None)
        if user_id is not None and state:
            try:
                state_user_id = int(state.get("user_id"))
            except (TypeError, ValueError):
                state_user_id = None
            if state_user_id != user_id:
                return None
        if user_id is not None and state is None:
            return None
        return dump_state(state) if state is not None else None

    def list_sessions(self, user_id: int, limit: int = 10) -> list[dict]:
        db = None
        try:
            db = SessionLocal()
            rows = (
                db.query(CoachSession)
                .filter(CoachSession.user_id == user_id)
                .order_by(CoachSession.updated_at.desc(), CoachSession.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "session_id": row.id,
                    "user_goal": row.user_goal,
                    "current_topic": row.current_topic,
                    "status": row.status,
                    "score": row.score,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]
        except Exception as exc:
            record_error_event(ErrorEvent(
                component="storage",
                operation="list_sessions",
                error_type=type(exc).__name__,
                error_message=str(exc),
                fallback_used=True,
                severity="warning",
                user_id=user_id,
            ))
            logger.warning("Session list unavailable, using filesystem")
            sessions = []
            for item in self.files.list_json("sessions"):
                state = item.get("content")
                if not isinstance(state, dict):
                    continue
                try:
                    state_user_id = int(state.get("user_id"))
                except (TypeError, ValueError):
                    state_user_id = None
                if state_user_id != user_id:
                    continue
                sessions.append({
                    "session_id": str(state.get("session_id") or "").strip(),
                    "user_goal": state.get("user_goal"),
                    "current_topic": state.get("current_topic"),
                    "status": state.get("status"),
                    "score": state.get("score"),
                    "created_at": None,
                    "updated_at": None,
                })
            return [item for item in sessions if item["session_id"]][:limit]
        finally:
            if db is not None:
                db.close()

    def memories(self, user_id: int) -> list[dict]:
        db = None
        try:
            db = SessionLocal()
            return load_learner_memories(db, user_id)
        except Exception:
            return []
        finally:
            if db is not None:
                db.close()


_store = None


def get_record_store() -> LearningRecordStore:
    global _store
    if _store is None:
        _store = LearningRecordStore()
    return _store
