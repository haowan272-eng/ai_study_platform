"""LangGraph workflow for the AI Agent Learning Coach."""
from collections.abc import Callable
from functools import lru_cache
from time import perf_counter
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents import (
    assessment_agent,
    interview_agent,
    opensource_mentor_agent,
    planner_agent,
    reporter_agent,
    supervisor_agent,
    tutor_agent,
)
from app.agents.supervisor import route_from_supervisor
from app.state import LearningCoachState


AgentNode = Callable[[LearningCoachState], dict[str, Any]]
CheckpointCallback = Callable[[dict[str, Any]], bool]


TRACE_KEYS = (
    "session_id",
    "current_task_id",
    "status",
    "next_action",
    "route_target",
    "current_week",
    "current_topic",
    "completed_agents",
    "score",
    "weak_points",
    "failed_node",
    "retryable",
)


def _state_snapshot(state: LearningCoachState | dict[str, Any]) -> dict[str, Any]:
    """Keep node trace payloads useful without copying full reports or messages."""
    snapshot = {key: state.get(key) for key in TRACE_KEYS if key in state}
    snapshot.update({
        "learning_plan_count": len(state.get("learning_plan", []) or []),
        "resources_count": len(state.get("resources", []) or []),
        "repo_analysis_count": len(state.get("repo_analysis", []) or []),
        "quiz_count": len(state.get("quiz", []) or []),
        "interview_questions_count": len(state.get("interview_questions", []) or []),
        "errors_count": len(state.get("errors", []) or []),
        "has_report": bool(state.get("learning_report")),
        "has_project_task": bool(state.get("project_task")),
    })
    return snapshot


def _thread_config(state: LearningCoachState | dict[str, Any]) -> dict[str, Any]:
    thread_id = str(state.get("session_id") or state.get("current_task_id") or "learning-coach")
    return {"recursion_limit": 30, "configurable": {"thread_id": thread_id}}


@lru_cache(maxsize=1)
def get_learning_checkpointer() -> MemorySaver:
    """Official LangGraph checkpointer for graph-level state snapshots."""
    return MemorySaver()


def _safe_agent_node(node_name: str, agent: AgentNode) -> AgentNode:
    """Convert unexpected node exceptions into explicit graph state."""

    def _wrapped(state: LearningCoachState) -> dict[str, Any]:
        started = perf_counter()
        input_snapshot = _state_snapshot(state)
        try:
            update = agent(state)
            duration_ms = round((perf_counter() - started) * 1000, 2)
            output_snapshot = _state_snapshot({**dict(state), **update})
            return {
                **update,
                "agent_metrics": [
                    {"node": node_name, "status": "completed", "duration_ms": duration_ms},
                ],
                "agent_trace": [
                    {
                        "node": node_name,
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "input": input_snapshot,
                        "output": output_snapshot,
                    },
                ],
            }
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            error = {
                "node": node_name,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "retryable": False,
            }
            return {
                "errors": [error],
                "failed_node": node_name,
                "retryable": False,
                "next_action": "supervisor",
                "route_target": "supervisor",
                "status": "failed",
                "agent_metrics": [
                    {
                        "node": node_name,
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "error_type": type(exc).__name__,
                    },
                ],
                "agent_trace": [
                    {
                        "node": node_name,
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "input": input_snapshot,
                        "error": error,
                    },
                ],
            }

    return _wrapped


def learning_parallel_agent(state: LearningCoachState) -> dict[str, Any]:
    """Dispatch Tutor and OpenSource Mentor through LangGraph native Send."""
    return {
        "status": "learning_parallel_dispatched",
        "next_action": "wait_for_parallel_agents",
        "agent_trace": [
            {
                "node": "learning_parallel",
                "status": "dispatched",
                "input": _state_snapshot(state),
                "fanout": ["tutor", "opensource_mentor"],
            },
        ],
    }


def route_learning_parallel(state: LearningCoachState) -> list[Send]:
    branch_state = {**dict(state), "next_action": "supervisor", "route_target": "supervisor"}
    return [
        Send("tutor", branch_state),
        Send("opensource_mentor", branch_state),
    ]


@lru_cache(maxsize=1)
def build_learning_coach_graph():
    """Build and compile the learning coach workflow graph."""
    workflow = StateGraph(LearningCoachState)

    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("planner", _safe_agent_node("planner", planner_agent))
    workflow.add_node("learning_parallel", learning_parallel_agent)
    workflow.add_node("tutor", _safe_agent_node("tutor", tutor_agent))
    workflow.add_node("opensource_mentor", _safe_agent_node("opensource_mentor", opensource_mentor_agent))
    workflow.add_node("reporter", _safe_agent_node("reporter", reporter_agent))
    workflow.add_node("assessment", _safe_agent_node("assessment", assessment_agent))
    workflow.add_node("interview", _safe_agent_node("interview", interview_agent))

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "planner": "planner",
            "learning_parallel": "learning_parallel",
            "tutor": "tutor",
            "opensource_mentor": "opensource_mentor",
            "reporter": "reporter",
            "assessment": "assessment",
            "interview": "interview",
            "end": END,
        },
    )
    workflow.add_conditional_edges("learning_parallel", route_learning_parallel, ["tutor", "opensource_mentor"])

    for node in (
        "planner",
        "tutor",
        "opensource_mentor",
        "reporter",
        "assessment",
        "interview",
    ):
        workflow.add_edge(node, "supervisor")

    return workflow.compile(checkpointer=get_learning_checkpointer())


def run_learning_coach(state: LearningCoachState) -> dict:
    """Run the learning coach workflow and return the final state."""
    return dict(build_learning_coach_graph().invoke(state, _thread_config(state)))


def run_learning_coach_checkpointed(state: LearningCoachState, on_checkpoint: CheckpointCallback) -> dict:
    """Run the workflow and persist state after every completed graph node.

    The callback returns True when the caller wants a graceful pause.
    """
    final_state: dict[str, Any] = dict(state)
    checkpoint_step = int(final_state.get("checkpoint_step") or 0)
    graph = build_learning_coach_graph()

    for chunk in graph.stream(final_state, _thread_config(final_state)):
        if not isinstance(chunk, dict):
            continue
        for node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            checkpoint_step += 1
            final_state.update(update)
            final_state["last_checkpoint_node"] = str(node_name)
            final_state["checkpoint_step"] = checkpoint_step
            if on_checkpoint(dict(final_state)):
                final_state["pause_requested"] = False
                final_state["status"] = "paused"
                final_state["next_action"] = "resume_task"
                on_checkpoint(dict(final_state))
                return dict(final_state)

    return dict(final_state)


__all__ = [
    "build_learning_coach_graph",
    "get_learning_checkpointer",
    "learning_parallel_agent",
    "route_learning_parallel",
    "run_learning_coach",
    "run_learning_coach_checkpointed",
]
