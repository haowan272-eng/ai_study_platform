"""Planner Agent: generate a staged learning roadmap."""
from app.schemas.contracts import LearningTask, dump_model
from app.services.llm import invoke_json
from app.state import LearningCoachState
from .common import as_list, completed


PLANNER_PROMPT = """
你是 AI Agent Learning Coach 中的 Planner Agent。你的任务是把用户学习目标拆成 4-6 个可执行的 LearningTask。
项目定位：这是一个基于 LangGraph、LangChain、MCP Adapter 和 FastAPI 的多智能体学习教练。
后续 Tutor、OpenSource Mentor、Assessment、Interview、Reporter 都会读取你的 learning_plan。

每个 LearningTask 必须既能指导学习，也能驱动后续资源搜索、项目实践和测评。
请只输出 JSON 数组，不要输出 Markdown 或代码块。每个元素包含：
- week：阶段序号，从 1 开始连续递增
- topic：阶段主题
- outcome：阶段学习产出
- hours：建议投入小时数，整数
- intent：为什么要学习这个阶段
- query：用于搜索资料或 GitHub 项目的英文查询词
- key_points：3-5 个关键知识点
- practice：一个小型实践任务
- status：固定为 "pending"
- summary：固定为 null
- sources_summary：固定为 null

要求：
1. 任务从基础到工程实践再到评测部署，形成递进关系。
2. 优先覆盖 AI Agent、LangGraph、LangChain、MCP、工具调用、多智能体协作、记忆、评测、部署。
3. 根据 learner_memories 跳过已掌握内容，并加强薄弱点。
4. 输出必须是合法 JSON 数组。
"""


def planner_agent(state: LearningCoachState) -> dict:
    """Generate the staged learning roadmap."""
    goal = state.get("user_goal", "学习 AI Agent 开发")

    fallback = [
        {
            "week": 1,
            "topic": "LLM 与 Prompt 基础",
            "outcome": "理解消息、上下文和结构化输出",
            "hours": 6,
            "intent": "为后续 Agent 节点的稳定输出和协作打基础",
            "query": "LLM prompt engineering structured JSON output agent design",
            "key_points": ["System/Human Message", "上下文管理", "JSON 结构化输出"],
            "practice": "编写一个将学习目标拆成 JSON 任务的 Planner Prompt",
            "status": "pending",
            "summary": None,
            "sources_summary": None,
        },
        {
            "week": 2,
            "topic": "LangChain 工具调用",
            "outcome": "实现带工具的单 Agent",
            "hours": 8,
            "intent": "掌握 Agent 访问外部工具和处理结构化结果的基本方式",
            "query": "LangChain tool calling agent Python examples",
            "key_points": ["工具注册", "工具参数", "结果解析"],
            "practice": "实现一个能调用搜索或文件工具的 Simple Agent",
            "status": "pending",
            "summary": None,
            "sources_summary": None,
        },
        {
            "week": 3,
            "topic": "LangGraph 状态与路由",
            "outcome": "掌握 StateGraph、节点、边和检查点",
            "hours": 10,
            "intent": "把多步骤 Agent 流程变成可追踪、可测试的图",
            "query": "LangGraph StateGraph conditional routing checkpoint Python",
            "key_points": ["TypedDict State", "条件路由", "节点状态增量"],
            "practice": "实现 Planner 到 Tutor 再到 Assessment 的最小 LangGraph",
            "status": "pending",
            "summary": None,
            "sources_summary": None,
        },
        {
            "week": 4,
            "topic": "MCP 协议与适配器",
            "outcome": "接入 GitHub 与 Filesystem 工具",
            "hours": 8,
            "intent": "隔离业务 Agent 与外部工具传输协议",
            "query": "Model Context Protocol Python SDK GitHub filesystem agent tools",
            "key_points": ["MCP 工具边界", "适配器模式", "HTTP 传输"],
            "practice": "为 GitHub 搜索实现稳定的 MCP Client 接口",
            "status": "pending",
            "summary": None,
            "sources_summary": None,
        },
        {
            "week": 5,
            "topic": "多智能体协作与作品集项目",
            "outcome": "实现 Supervisor 和专用 Agent，并生成可展示项目",
            "hours": 12,
            "intent": "把路线、讲解、搜索、测评串成完整学习闭环",
            "query": "multi agent supervisor workflow portfolio project LangGraph",
            "key_points": ["Supervisor 路由", "专业 Agent 分工", "项目验收标准"],
            "practice": "完成 AI Agent Learning Coach 作品集 Demo",
            "status": "pending",
            "summary": None,
            "sources_summary": None,
        },
    ]

    plan = as_list(
        invoke_json(
            PLANNER_PROMPT,
            {"user_goal": goal, "learner_memories": state.get("learner_memories", [])},
            fallback,
        ),
        fallback,
    )
    plan = [dump_model(LearningTask.model_validate(item)) for item in plan if isinstance(item, dict)]
    current = str(plan[0].get("topic", "LangGraph 基础")) if plan else "LangGraph 基础"

    return {
        "learning_plan": plan,
        "current_week": int(plan[0].get("week", 1)) if plan and isinstance(plan[0], dict) else 1,
        "completed_weeks": list(state.get("completed_weeks", [])),
        "current_topic": current,
        "completed_agents": completed(state, "planner"),
        "next_action": "supervisor",
        "status": "planning_completed",
    }


__all__ = ["planner_agent"]
