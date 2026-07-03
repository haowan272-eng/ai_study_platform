"""Initial relational schema.

Revision ID: 20260625_0001
Revises:
Create Date: 2026-06-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260625_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "coach_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("learner_id", sa.String(length=128), nullable=False),
        sa.Column("user_goal", sa.Text(), nullable=False),
        sa.Column("current_topic", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coach_sessions_learner_id", "coach_sessions", ["learner_id"], unique=False)
    op.create_index("ix_coach_sessions_status", "coach_sessions", ["status"], unique=False)
    op.create_index("ix_coach_sessions_user_id", "coach_sessions", ["user_id"], unique=False)

    op.create_table(
        "coach_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("answers_json", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("weak_points_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coach_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coach_assessments_session_id", "coach_assessments", ["session_id"], unique=False)

    op.create_table(
        "coach_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coach_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "artifact_type", name="uq_coach_artifact_type"),
    )
    op.create_index("ix_coach_artifacts_session_id", "coach_artifacts", ["session_id"], unique=False)

    op.create_table(
        "coach_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("learner_id", sa.String(length=128), nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("source_session_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "memory_key", "category", name="uq_coach_memory"),
    )
    op.create_index("ix_coach_memories_category", "coach_memories", ["category"], unique=False)
    op.create_index("ix_coach_memories_learner_id", "coach_memories", ["learner_id"], unique=False)
    op.create_index("ix_coach_memories_user_id", "coach_memories", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_coach_memories_user_id", table_name="coach_memories")
    op.drop_index("ix_coach_memories_learner_id", table_name="coach_memories")
    op.drop_index("ix_coach_memories_category", table_name="coach_memories")
    op.drop_table("coach_memories")

    op.drop_index("ix_coach_artifacts_session_id", table_name="coach_artifacts")
    op.drop_table("coach_artifacts")

    op.drop_index("ix_coach_assessments_session_id", table_name="coach_assessments")
    op.drop_table("coach_assessments")

    op.drop_index("ix_coach_sessions_user_id", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_status", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_learner_id", table_name="coach_sessions")
    op.drop_table("coach_sessions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
