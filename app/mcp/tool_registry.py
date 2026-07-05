"""Explicit tool registry for agent-scoped MCP-style adapters."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPermission:
    agent: str
    tool: str


ALLOWED_TOOLS_BY_AGENT: dict[str, frozenset[str]] = {
    "opensource_mentor": frozenset({
        "github.search_repositories",
        "github.read_readme",
    }),
    "storage": frozenset({
        "filesystem.read_json",
        "filesystem.write_json",
        "filesystem.list_json",
    }),
}


class ToolPermissionError(PermissionError):
    """Raised when an agent attempts to use a tool outside its registry."""


def allowed_tools(agent: str) -> frozenset[str]:
    return ALLOWED_TOOLS_BY_AGENT.get(agent, frozenset())


def assert_tool_allowed(agent: str, tool: str) -> ToolPermission:
    if tool not in allowed_tools(agent):
        raise ToolPermissionError(f"Agent '{agent}' is not allowed to use tool '{tool}'")
    return ToolPermission(agent=agent, tool=tool)


__all__ = [
    "ALLOWED_TOOLS_BY_AGENT",
    "ToolPermission",
    "ToolPermissionError",
    "allowed_tools",
    "assert_tool_allowed",
]
