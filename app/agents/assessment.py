"""Assessment Agent: generate quizzes and score submitted answers."""
from __future__ import annotations

from app.schemas.contracts import QuizQuestion, dump_model
from app.services.llm import invoke_json
from app.state import LearningCoachState
from .common import as_list, completed


def _default_quiz(topic: str) -> list[dict]:
    """Fallback quiz used when the LLM is unavailable."""
    return [
        {
            "id": 1,
            "question": "StateGraph 中的 State 主要解决什么问题？",
            "options": ["保存节点共享上下文", "启动 HTTP 服务", "训练模型", "创建数据库"],
            "correct_answer": "保存节点共享上下文",
            "explanation": "State 用来在各个节点之间传递共享上下文，让图中的节点能基于同一份状态协作。",
            "topic": topic,
        },
        {
            "id": 2,
            "question": "实现动态分支通常应该使用哪个方法？",
            "options": ["add_conditional_edges", "add_database", "bind_tools_only", "mount"],
            "correct_answer": "add_conditional_edges",
            "explanation": "LangGraph 中的条件分支通常通过 add_conditional_edges 根据状态选择下一步节点。",
            "topic": "条件路由",
        },
        {
            "id": 3,
            "question": "MCP 适配层的主要价值是什么？",
            "options": ["隔离业务与工具传输协议", "替代 Python", "训练 Embedding", "生成 CSS"],
            "correct_answer": "隔离业务与工具传输协议",
            "explanation": "MCP 适配层把业务 Agent 和外部工具协议解耦，方便替换工具、控制权限并统一错误处理。",
            "topic": "MCP",
        },
        {
            "id": 4,
            "question": "多 Agent 系统中 Supervisor 通常负责什么？",
            "options": ["根据状态选择下一个 Agent", "保存图片", "编译前端", "建立向量索引"],
            "correct_answer": "根据状态选择下一个 Agent",
            "explanation": "Supervisor 的核心职责是读取当前状态，并决定下一步应该由哪个 Agent 继续处理。",
            "topic": "Supervisor",
        },
        {
            "id": 5,
            "question": "为什么 Agent 节点更适合返回状态增量？",
            "options": ["减少副作用并便于追踪测试", "提高屏幕亮度", "绕过鉴权", "删除日志"],
            "correct_answer": "减少副作用并便于追踪测试",
            "explanation": "节点返回状态增量可以让状态变化更清晰，也便于记录、测试和回放工作流。",
            "topic": "状态更新",
        },
    ]


def _normalize_answer(answer: object, options: list[object]) -> str:
    value = str(answer or "").strip()
    if len(value) == 1 and value.upper() in {"A", "B", "C", "D"}:
        index = ord(value.upper()) - ord("A")
        if 0 <= index < len(options):
            value = str(options[index] or "").strip()
    return value.casefold()


def assessment_agent(state: LearningCoachState) -> dict:
    """Generate a quiz or score submitted answers."""
    answers = list(state.get("user_answers", []))
    quiz = list(state.get("quiz", []))

    if not quiz:
        fallback = _default_quiz(state.get("current_topic", "LangGraph"))
        quiz = as_list(
            invoke_json(
                (
                    "你是中文 AI Agent 学习测评专家。输出 5 道中文单选题数组。"
                    "每题必须包含 id、question、options、correct_answer、explanation、topic。"
                    "question、options、correct_answer、explanation、topic 必须使用中文。"
                    "correct_answer 必须是 options 中的完整文本，不能只写 A/B/C/D 字母。"
                    "explanation 用 1-2 句中文解释为什么该选项正确。"
                ),
                {
                    "goal": state.get("user_goal"),
                    "plan": state.get("learning_plan", []),
                    "topic": state.get("current_topic"),
                },
                fallback,
            ),
            fallback,
        )
        quiz = [dump_model(QuizQuestion.model_validate(item)) for item in quiz if isinstance(item, dict)]
        return {
            "quiz": quiz,
            "score": None,
            "weak_points": [],
            "completed_agents": completed(state, "assessment"),
            "next_action": "supervisor",
            "status": "awaiting_answers",
        }

    total = max(1, len(quiz))
    correct = 0
    weak_points: list[str] = []

    for index, question in enumerate(quiz):
        options = list(question.get("options") or [])
        expected_raw = _normalize_answer(question.get("correct_answer", ""), options)
        actual_raw = _normalize_answer(answers[index] if index < len(answers) else "", options)
        matched = bool(expected_raw and actual_raw and actual_raw == expected_raw)

        if matched:
            correct += 1
        else:
            weak_points.append(str(question.get("topic") or question.get("question") or "未知知识点"))

    score = round(correct * 100 / total, 2)

    return {
        "score": score,
        "weak_points": list(dict.fromkeys(weak_points)),
        "completed_agents": completed(state, "assessment"),
        "next_action": "supervisor",
        "status": "assessment_passed" if score >= 60 else "assessment_failed",
    }


__all__ = ["assessment_agent"]
