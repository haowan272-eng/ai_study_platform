"""Relational models for learning sessions, assessments, artifacts and memory."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CoachSession(Base):
    __tablename__ = "coach_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    learner_id: Mapped[str] = mapped_column(String(128), index=True, default="anonymous")
    user_goal: Mapped[str] = mapped_column(Text)
    current_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), index=True, default="started")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assessments = relationship("CoachAssessment", cascade="all, delete-orphan")
    artifacts = relationship("CoachArtifact", cascade="all, delete-orphan")


class CoachAssessment(Base):
    __tablename__ = "coach_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("coach_sessions.id", ondelete="CASCADE"), index=True)
    answers_json: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    weak_points_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoachArtifact(Base):
    __tablename__ = "coach_artifacts"
    __table_args__ = (UniqueConstraint("session_id", "artifact_type", name="uq_coach_artifact_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("coach_sessions.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    content_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoachMemory(Base):
    __tablename__ = "coach_memories"
    __table_args__ = (UniqueConstraint("learner_id", "memory_key", "category", name="uq_coach_memory"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    learner_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_key: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
