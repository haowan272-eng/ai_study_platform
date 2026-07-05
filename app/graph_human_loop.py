"""Human-in-the-loop primitives backed by LangGraph Command and interrupt."""
from __future__ import annotations

from typing import Any

from langgraph.types import Command, interrupt


def apply_command_update(state: dict[str, Any], command: Command) -> dict[str, Any]:
    """Apply a LangGraph Command update to a plain persisted state dict."""
    updated = dict(state)
    if isinstance(command.update, dict):
        updated.update(command.update)
    return updated


def resume_task_command() -> Command:
    return Command(
        update={
            "pause_requested": False,
            "status": "queued",
            "next_action": "wait_for_result",
        },
        goto="supervisor",
    )


def quiz_submission_command(answers: list[str]) -> Command:
    return Command(
        update={
            "user_answers": answers,
            "score": None,
            "weak_points": [],
            "interview_questions": [],
            "interview_answers": [],
            "interview_evaluations": [],
            "interview_score": None,
            "remediation_done": False,
            "next_action": "wait_for_result",
            "status": "queued",
            "pause_requested": False,
            "last_checkpoint_node": "",
            "checkpoint_step": 0,
        },
        goto="supervisor",
    )


def interview_submission_command(answers: list[str], evaluations: list[dict[str, Any]], average_score: float) -> Command:
    return Command(
        update={
            "interview_answers": answers,
            "interview_evaluations": evaluations,
            "interview_score": average_score,
            "status": "interview_reviewed",
        },
        goto="supervisor",
    )


def request_human_input(kind: str, state: dict[str, Any], prompt: str) -> Any:
    """Reusable graph-level interrupt payload for future in-graph approval nodes."""
    return interrupt(
        {
            "kind": kind,
            "prompt": prompt,
            "session_id": state.get("session_id"),
            "current_task_id": state.get("current_task_id"),
            "status": state.get("status"),
            "next_action": state.get("next_action"),
        }
    )


__all__ = [
    "apply_command_update",
    "interview_submission_command",
    "quiz_submission_command",
    "request_human_input",
    "resume_task_command",
]
