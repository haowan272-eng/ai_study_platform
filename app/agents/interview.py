"""Interview Agent: prepares questions after the assessment passes."""
from app.schemas.contracts import InterviewQuestion, dump_model
from app.services.llm import invoke_json
from app.state import LearningCoachState
from .common import as_list, completed


def interview_agent(state: LearningCoachState) -> dict:
    fallback = [
        {
            "question": "为什么使用 LangGraph，而不是普通顺序 Chain？",
            "reference_answer": "LangGraph 能显式表达状态、循环、条件路由、持久化和人工介入，更适合长流程 Agent。",
            "follow_up": "如何避免图中的无限循环？",
        },
        {
            "question": "你的 Supervisor 如何决定下一个 Agent？",
            "reference_answer": "基于完整性、测验状态和分数做确定性路由；复杂场景可使用 LLM 分类，但保留规则兜底。",
            "follow_up": "为什么关键路由不应完全交给 LLM？",
        },
        {
            "question": "如何保证 MCP 工具调用安全？",
            "reference_answer": "使用最小权限、路径沙箱、参数校验、超时、审计、密钥隔离和错误降级。",
            "follow_up": "Filesystem MCP 如何防止目录穿越？",
        },
        {
            "question": "如何测试多 Agent 工作流？",
            "reference_answer": "分别测试节点状态增量、路由函数、外部工具适配器、端到端图执行和故障降级。",
            "follow_up": "哪些指标可以衡量 Agent 质量？",
        },
        {
            "question": "测验分数低于 60 后系统如何处理？",
            "reference_answer": "Assessment 写入薄弱点，Supervisor 路由回 Tutor 生成针对性补救内容，然后等待用户重新测验。",
            "follow_up": "如何避免使用旧答案导致死循环？",
        },
    ]
    questions = as_list(
        invoke_json(
            (
                "你是中文 AI Agent 技术面试官。输出由 question、reference_answer、follow_up 组成的数组。"
                "所有字段必须使用中文，问题要贴合当前学习主题和作品集项目。"
            ),
            {
                "goal": state.get("user_goal"),
                "score": state.get("score"),
                "project": state.get("project_task"),
            },
            fallback,
        ),
        fallback,
    )
    questions = [dump_model(InterviewQuestion.model_validate(item)) for item in questions if isinstance(item, dict)]
    return {
        "interview_questions": questions,
        "completed_agents": completed(state, "interview"),
        "next_action": "supervisor",
        "status": "completed",
    }


__all__ = ["interview_agent"]
