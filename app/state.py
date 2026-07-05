"""Shared LangGraph state for the AI Agent Learning Coach."""
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


def append_items(left: list | None, right: list | None) -> list:
    """Append reducer used by parallel graph branches for telemetry-like fields."""
    return [*(left or []), *(right or [])]


def pick_latest(left: Any | None, right: Any | None) -> Any | None:
    """Reducer for scalar routing fields; the newest explicit branch value wins."""
    return right if right not in (None, "") else left


def merge_status(left: str | None, right: str | None) -> str | None:
    """Reducer for statuses produced by parallel learning branches."""
    if right in (None, ""):
        return left
    if left in (None, "", "learning_parallel_dispatched"):
        return right
    if "failed" in {left, right}:
        return "failed"
    branch_statuses = {"tutoring_completed", "resources_and_project_completed"}
    if "remediation_completed" in {left, right}:
        return "remediation_completed"
    if left in branch_statuses and right in branch_statuses and left != right:
        return "parallel_learning_completed"
    return right


def append_unique(left: list | None, right: list | None) -> list:
    """Append reducer that preserves order and removes duplicate scalar values."""
    values: list = []
    for item in [*(left or []), *(right or [])]:
        if item not in values:
            values.append(item)
    return values


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

    next_action: Annotated[str, pick_latest]
    route_target: Annotated[str, pick_latest]
    messages: Annotated[list, add_messages]

    session_id: str
    current_task_id: str
    pause_requested: bool
    last_checkpoint_node: str
    checkpoint_step: int
    tutor_content: str
    tutor_task: dict[str, Any]
    remediation_done: bool
    completed_agents: Annotated[list[str], append_unique]
    status: Annotated[str, merge_status]
    errors: Annotated[list[dict[str, Any]], append_items]
    failed_node: str | None
    retryable: bool
    agent_metrics: Annotated[list[dict[str, Any]], append_items]
    agent_trace: Annotated[list[dict[str, Any]], append_items]

__all__ = ["LearningCoachState", "append_items", "append_unique", "merge_status", "pick_latest"]
