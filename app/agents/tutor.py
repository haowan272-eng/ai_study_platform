"""Tutor Agent: generate structured weekly learning content."""
from urllib.parse import quote_plus

from app.schemas.contracts import TutorTask, dump_model
from app.services.llm import invoke_json
from app.state import LearningCoachState
from .common import as_dict, completed, first_topic


def _topic_for_current_week(state: LearningCoachState) -> str:
    plan = state.get("learning_plan", [])
    current_week = int(state.get("current_week") or 1)
    for item in plan:
        if isinstance(item, dict) and int(item.get("week") or 0) == current_week:
            return str(item.get("topic") or first_topic(state))
    return first_topic(state)


def _video_links(topic: str) -> list[dict]:
    query = quote_plus(f"{topic} tutorial")
    return [
        {
            "title": f"YouTube 搜索：{topic}",
            "url": f"https://www.youtube.com/results?search_query={query}",
            "description": "用于查找近期教程视频、项目演示和完整 walkthrough。",
        },
        {
            "title": f"Bilibili 搜索：{topic}",
            "url": f"https://search.bilibili.com/all?keyword={query}",
            "description": "适合查找中文课程、项目讲解和学习笔记。",
        },
        {
            "title": f"GitHub 搜索：{topic}",
            "url": f"https://github.com/search?q={query}&type=repositories",
            "description": "配合真实仓库学习代码结构、实现方式和 README 写法。",
        },
    ]


def tutor_agent(state: LearningCoachState) -> dict:
    topic = _topic_for_current_week(state)
    weak_points = state.get("weak_points", [])
    remediation = state.get("score") is not None and float(state.get("score") or 0) < 60

    fallback = {
        "title": topic,
        "objective": f"理解 {topic} 的核心思想，并把它应用到一个小型 Agent 项目中。",
        "concepts": [
            "State：在图节点之间传递的共享上下文。",
            "Node：负责一个明确任务的 Agent 工作单元。",
            "Edge：根据状态决定下一步的路由逻辑。",
        ],
        "example": "StateGraph(State) -> add_node(...) -> add_conditional_edges(...) -> compile()",
        "practice_steps": [
            "创建一个包含 planner 和 tutor 节点的最小图。",
            "根据 state.next_action 添加条件路由。",
            "记录每个节点的输出，观察状态如何变化。",
        ],
        "common_mistakes": [
            "把所有逻辑塞进一个节点，没有拆分职责。",
            "直接原地修改状态，而不是返回清晰的状态增量。",
            "外部工具失败时没有设计回退行为。",
        ],
    }

    content = as_dict(
        invoke_json(
            (
                "你是中文 AI Agent 学习导师。只返回合法 JSON 对象。"
                "字段包括 title、objective、concepts、example、practice_steps、common_mistakes。"
                "concepts、practice_steps、common_mistakes 必须是中文短句数组。"
                "请聚焦原理、代码级实现和常见工程错误。"
            ),
            {"topic": topic, "weak_points": weak_points, "remediation": remediation},
            fallback,
        ),
        fallback,
    )

    tutor_task = {
        "title": str(content.get("title") or topic),
        "objective": str(content.get("objective") or fallback["objective"]),
        "concepts": list(content.get("concepts") or fallback["concepts"]),
        "example": str(content.get("example") or fallback["example"]),
        "practice_steps": list(content.get("practice_steps") or fallback["practice_steps"]),
        "common_mistakes": list(content.get("common_mistakes") or fallback["common_mistakes"]),
        "learning_links": _video_links(topic),
    }
    tutor_task = dump_model(TutorTask.model_validate(tutor_task))

    rendered = (
        f"{tutor_task['title']}\n\n{tutor_task['objective']}\n\n"
        f"示例：\n{tutor_task['example']}"
    )

    return {
        "current_topic": topic,
        "tutor_task": tutor_task,
        "tutor_content": rendered,
        "remediation_done": bool(remediation),
        "completed_agents": completed(state, "tutor"),
        "next_action": "supervisor",
        "status": "remediation_completed" if remediation else "tutoring_completed",
    }


__all__ = ["tutor_agent"]
