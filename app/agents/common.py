"""
Agent 通用辅助函数。

提供各 Agent 节点共用的轻量级工具：
- completed: 追加已完成的 Agent 名称到列表
- first_topic: 从学习计划中提取第一个主题
- as_dict / as_list: 类型安全的解包函数，带默认值回退
"""
from __future__ import annotations

from typing import Any


def completed(state: dict, agent_name: str) -> list[str]:
    """将 agent_name 追加到 completed_agents 列表（去重），返回新列表。

    用于标记 Agent 已完成，Supervisor 据此判断下一步路由。
    """
    values = list(state.get("completed_agents", []))
    if agent_name not in values:
        values.append(agent_name)
    return values


def first_topic(state: dict) -> str:
    """从学习计划 learning_plan 中提取第一个主题，回退到 current_topic 或默认值。

    用于 Tutor 等需要知道"当前该教什么"的 Agent。
    """
    plan = state.get("learning_plan", [])
    if plan and isinstance(plan[0], dict):
        return str(plan[0].get("topic") or "LangGraph基础")
    return str(state.get("current_topic") or "LangGraph基础")


def as_dict(value: Any, fallback: dict) -> dict:
    """类型安全解包：如果 value 是 dict 则返回，否则返回 fallback。

    用于处理 LLM 返回结果的不确定性。
    """
    return value if isinstance(value, dict) else fallback


def as_list(value: Any, fallback: list) -> list:
    """类型安全解包：如果 value 是 list 则返回，否则返回 fallback。

    用于处理 LLM 返回结果的不确定性。
    """
    return value if isinstance(value, list) else fallback
