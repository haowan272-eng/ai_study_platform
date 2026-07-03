"""Deterministic routing for the Learning Coach workflow."""
from app.state import LearningCoachState


def _has_project_task(state: LearningCoachState) -> bool:
    project = state.get("project_task")
    if not isinstance(project, dict):
        return bool(project)
    meaningful_fields = (
        "title",
        "objective",
        "github_references",
        "milestones",
        "technical_requirements",
        "deliverables",
        "acceptance_criteria",
    )
    return any(bool(project.get(field)) for field in meaningful_fields)


def supervisor_agent(state: LearningCoachState) -> dict:
    """Route the graph according to the current state."""
    has_project_task = _has_project_task(state)
    if state.get("status") == "failed_report_completed":
        action = "end"
    elif state.get("status") == "failed":
        action = (
            "reporter"
            if state.get("failed_node") != "reporter" and not state.get("learning_report")
            else "end"
        )
    elif not state.get("learning_plan"):
        action = "planner"
    elif state.get("plan_only"):
        action = "end"
    elif not state.get("tutor_content") and not has_project_task:
        action = "learning_parallel"
    elif not state.get("tutor_content"):
        action = "tutor"
    elif not has_project_task:
        action = "opensource_mentor"
    elif not state.get("learning_report") and not state.get("quiz"):
        action = "reporter"
    elif not state.get("quiz"):
        action = "assessment"
    elif state.get("score") is None and state.get("user_answers"):
        action = "assessment"
    elif state.get("score") is None:
        action = "end"
    elif float(state.get("score") or 0) < 60 and not state.get("remediation_done"):
        action = "tutor"
    elif float(state.get("score") or 0) >= 60 and not state.get("interview_questions"):
        action = "interview"
    else:
        action = "end"

    if state.get("status") == "failed_report_completed":
        suggestion = "inspect_failure"
    elif state.get("status") == "failed" and action == "reporter":
        suggestion = "generate_failure_report"
    elif state.get("status") == "failed":
        suggestion = "inspect_failure"
    elif state.get("plan_only") and state.get("learning_plan"):
        suggestion = "select_week"
    elif action != "end":
        suggestion = action
    elif state.get("score") is None:
        suggestion = "submit_quiz"
    elif float(state.get("score") or 0) < 60:
        suggestion = "review_weak_points_and_retry"
    else:
        suggestion = "interview_and_build_project"

    return {"route_target": action, "next_action": suggestion}


def route_from_supervisor(state: LearningCoachState) -> str:
    """Return the next graph node selected by supervisor_agent."""
    return str(state.get("route_target", "end"))


__all__ = ["route_from_supervisor", "supervisor_agent"]
