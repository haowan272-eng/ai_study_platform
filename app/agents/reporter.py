"""
Reporter Agent —— 综合学习报告生成。

汇总学习路线、导师讲解、GitHub 资料分析、作品集项目和测评状态，
生成一份面向学习者的 Markdown 格式综合报告。

输出纯文本（invoke_text），而非 JSON。
"""
from app.services.llm import invoke_text
from app.state import LearningCoachState
from .common import completed


# Reporter 的 System Prompt —— 指导 LLM 按结构生成综合学习报告
REPORTER_PROMPT = """
你是 AI Agent Learning Coach 中的 Reporter Agent，负责把学习路线、导师讲解、GitHub资料分析、作品集项目和测评状态汇总成学习报告。

请输出 Markdown，不要输出 JSON，不要包含代码块。

报告结构：
## 学习目标
概括用户目标与当前学习重点。

## 路线总览
用条目总结每个 LearningTask 的 topic、intent、outcome 和 practice。

## 开源参考
以下是已经搜索和分析过的 GitHub 开源项目列表（不要输出"尚未"、"暂无"、"未进行"等否定词，这些数据是真实存在的）：
{repo_summary}

请总结这些仓库对你学习目标的价值，保留仓库名、地址、star 数、核心借鉴点。

## 作品集任务
说明项目目标、里程碑、交付物和验收标准。

## 测评与下一步
如果已有 score 和 weak_points，给出补救建议；如果尚未测评，说明测评重点。

要求：
1. 内容要面向学习者，清晰、可执行
2. 每个仓库必须附带完整的 GitHub 地址（如 https://github.com/langchain-ai/langgraph）、star 数、技术栈等关键数据
3. 不要编造不存在的来源
4. 中文输出
5. 如果已有开源分析数据，必须在报告中如实列出，不得说"尚未分析"
"""


def reporter_agent(state: LearningCoachState) -> dict:
    """报告 Agent：汇总所有学习环节生成综合报告。

    1. 调用 LLM (invoke_text) 根据当前状态生成 Markdown 报告
    2. LLM 失败时使用状态数据拼接回退报告
    3. 回退报告根据实际数据动态生成，避免"尚未分析"与实际数据矛盾
    """
    resources = [
        item for item in state.get("resources", []) if isinstance(item, dict)
    ]
    repo_analysis = state.get("repo_analysis", [])
    has_repos = bool(resources or repo_analysis)

    # 预构建开源参考文本：有数据则拼接为易读的字符串，无数据则写提示
    if has_repos:
        repo_summary_lines = [
            "以下是根据你的学习主题搜索到的 GitHub 开源项目，重点关注这些仓库：", ""
        ]
        for item in resources:
            url = item.get("url", "")
            repo_summary_lines.append(
                f"- {item.get('name', '')}（{item.get('stars', 0)} stars）：{item.get('description', '')}"
            )
            if url:
                repo_summary_lines.append(f"  地址：{url}")
            # 附上深度分析的核心借鉴点
            for a in repo_analysis:
                if isinstance(a, dict) and a.get("repo") == item.get("name"):
                    insights = a.get("core_insights", [])
                    if insights:
                        repo_summary_lines.append(f"  借鉴：{insights[0]}")
                    learning_value = a.get("learning_value", "")
                    if learning_value:
                        repo_summary_lines.append(f"  学习价值：{learning_value}")
                    break
        repo_summary_text = "\n".join(repo_summary_lines)
    else:
        repo_summary_text = "暂时没有搜索到相关的 GitHub 仓库，建议检查网络或 GitHub Token 配置。"

    # 回退报告：从状态数据动态拼接
    fallback = (
        "## 学习目标\n"
        f"{state.get('user_goal', '学习AI Agent开发')}\n\n"
        "## 路线总览\n"
        + "\n".join(
            f"- {item.get('topic')}: {item.get('outcome')}"
            for item in state.get("learning_plan", [])
            if isinstance(item, dict)
        )
        + "\n\n## 开源参考\n"
        + repo_summary_text
        + "\n\n## 作品集任务\n"
        + str(state.get("project_task", {}).get("objective", "完成一个可演示的多Agent学习教练项目"))
        + "\n\n## 测评与下一步\n完成阶段测验后，根据薄弱点回到Tutor补救。"
    )

    # 把预格式化的开源数据嵌入 prompt，避免 LLM 解析原始 JSON 出错
    prompt = REPORTER_PROMPT.format(repo_summary=repo_summary_text)

    # 调用 LLM 生成报告（纯文本，非 JSON）
    report = invoke_text(
        prompt,
        {
            "user_goal": state.get("user_goal"),
            "current_topic": state.get("current_topic"),
            "learning_plan": state.get("learning_plan", []),
            "tutor_content": state.get("tutor_content", ""),
            "project_task": state.get("project_task", {}),
            "score": state.get("score"),
            "weak_points": state.get("weak_points", []),
        },
        fallback,
    )

    return {
        "learning_report": report,
        "completed_agents": completed(state, "reporter"),
        "next_action": "supervisor",
        "status": "failed_report_completed" if state.get("errors") else "report_completed",
    }


__all__ = ["reporter_agent"]
