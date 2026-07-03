"""Shared LangGraph state for the AI Agent Learning Coach."""
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class LearningCoachState(TypedDict, total=False):
    """All fields are optional because LangGraph nodes return partial updates."""

    user_id: int
    user_goal: str
    learner_id: str
    learner_memories: list[dict[str, Any]]

    current_topic: str
    current_week: int
    completed_weeks: list[int]
    plan_only: bool
    learning_plan: list[dict[str, Any]]

    resources: list[dict[str, Any]]
    repo_analysis: list[dict[str, Any]]

    project_task: dict[str, Any]
    learning_report: str

    quiz: list[dict[str, Any]]
    user_answers: list[str]
    score: float | None
    weak_points: list[str]
    interview_questions: list[dict[str, Any]]
    interview_answers: list[str]
    interview_evaluations: list[dict[str, Any]]
    interview_score: float | None

    next_action: str
    route_target: str
    messages: Annotated[list, add_messages]

    session_id: str
    current_task_id: str
    pause_requested: bool
    last_checkpoint_node: str
    checkpoint_step: int
    tutor_content: str
    tutor_task: dict[str, Any]
    remediation_done: bool
    completed_agents: list[str]
    status: str
    errors: list[dict[str, Any]]
    failed_node: str | None
    retryable: bool
    agent_metrics: list[dict[str, Any]]


__all__ = ["LearningCoachState"]
