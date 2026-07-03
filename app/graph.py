"""LangGraph workflow for the AI Agent Learning Coach."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

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


def _safe_agent_node(node_name: str, agent: AgentNode) -> AgentNode:
    """Convert unexpected node exceptions into explicit graph state."""

    def _wrapped(state: LearningCoachState) -> dict[str, Any]:
        started = perf_counter()
        try:
            update = agent(state)
            duration_ms = round((perf_counter() - started) * 1000, 2)
            return {
                **update,
                "agent_metrics": [
                    *state.get("agent_metrics", []),
                    {"node": node_name, "status": "completed", "duration_ms": duration_ms},
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
                "errors": [*state.get("errors", []), error],
                "failed_node": node_name,
                "retryable": False,
                "next_action": "supervisor",
                "route_target": "supervisor",
                "status": "failed",
                "agent_metrics": [
                    *state.get("agent_metrics", []),
                    {
                        "node": node_name,
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "error_type": type(exc).__name__,
                    },
                ],
            }

    return _wrapped


def _merge_completed_agents(state: LearningCoachState, updates: list[dict[str, Any]]) -> list[str]:
    values = list(state.get("completed_agents", []))
    for update in updates:
        for agent_name in update.get("completed_agents", []):
            if agent_name not in values:
                values.append(agent_name)
    return values


def _merge_parallel_updates(state: LearningCoachState, updates: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    errors = [*state.get("errors", [])]
    metrics = [*state.get("agent_metrics", [])]
    failed_nodes: list[str] = []

    for update in updates:
        for key, value in update.items():
            if key in {
                "completed_agents",
                "errors",
                "failed_node",
                "next_action",
                "route_target",
                "status",
                "retryable",
                "agent_metrics",
            }:
                continue
            merged[key] = value

        errors.extend(update.get("errors", []))
        metrics.extend(update.get("agent_metrics", []))
        if update.get("failed_node"):
            failed_nodes.append(str(update["failed_node"]))

    merged["completed_agents"] = _merge_completed_agents(state, updates)
    merged["agent_metrics"] = metrics
    merged["next_action"] = "supervisor"
    merged["route_target"] = "supervisor"

    if failed_nodes:
        merged["errors"] = errors
        merged["failed_node"] = ",".join(failed_nodes)
        merged["retryable"] = any(bool(update.get("retryable")) for update in updates)
        merged["status"] = "failed"
    else:
        merged["status"] = "parallel_learning_completed"

    return merged


def _run_parallel_agents(state: LearningCoachState, agents: dict[str, AgentNode]) -> dict[str, Any]:
    updates: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {
            executor.submit(
                _safe_agent_node(name, agent),
                {**dict(state), "errors": [], "agent_metrics": []},
            ): name
            for name, agent in agents.items()
        }
        for future in as_completed(futures):
            updates.append(future.result())

    return _merge_parallel_updates(state, updates)


def learning_parallel_agent(state: LearningCoachState) -> dict[str, Any]:
    """Run Tutor and OpenSource Mentor concurrently after planning."""
    return _run_parallel_agents(
        state,
        {
            "tutor": tutor_agent,
            "opensource_mentor": opensource_mentor_agent,
        },
    )


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

    for node in (
        "planner",
        "learning_parallel",
        "tutor",
        "opensource_mentor",
        "reporter",
        "assessment",
        "interview",
    ):
        workflow.add_edge(node, "supervisor")

    return workflow.compile()


def run_learning_coach(state: LearningCoachState) -> dict:
    """Run the learning coach workflow and return the final state."""
    return dict(build_learning_coach_graph().invoke(state, {"recursion_limit": 30}))


def run_learning_coach_checkpointed(state: LearningCoachState, on_checkpoint: CheckpointCallback) -> dict:
    """Run the workflow and persist state after every completed graph node.

    The callback returns True when the caller wants a graceful pause.
    """
    final_state: dict[str, Any] = dict(state)
    checkpoint_step = int(final_state.get("checkpoint_step") or 0)
    graph = build_learning_coach_graph()

    for chunk in graph.stream(final_state, {"recursion_limit": 30}):
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
    "learning_parallel_agent",
    "run_learning_coach",
    "run_learning_coach_checkpointed",
]
