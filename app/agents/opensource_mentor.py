"""Open Source Mentor Agent: search GitHub, analyze repositories, and design a portfolio task."""
from __future__ import annotations

import re

from app.mcp.github_client import GitHubMCPClient
from app.schemas.contracts import GitHubRepository, GitHubResource, ProjectTask, RepoAnalysis, dump_model
from app.services.llm import invoke_json
from app.state import LearningCoachState
from .common import as_dict, completed


TASK_SUMMARIZER_PROMPT = """
你是 AI Agent Learning Coach 中的 OpenSource Mentor Agent。
你的任务是总结 GitHub 搜索结果，并提取可以迁移到学习者作品集项目中的工程经验。

任务标题：{task_title}
任务意图：{task_intent}
搜索查询：{task_query}

请根据仓库元数据和 README 内容，输出 JSON 对象，不要输出 Markdown 或代码块。
JSON 字段：
- core_insights：数组，3-5 条核心观点，每条说明该项目对学习者有什么参考价值
- key_data：数组，重要数字、名称、技术栈、日期或仓库特征
- source_citations：数组，每项包含 index、repo、url，用于标记来源
- architecture：该类项目的典型架构总结
- learning_value：学习者应该重点借鉴什么
- reading_order：建议阅读顺序数组

要求：
1. 每条核心观点尽量带来源标记，例如 [1]。
2. 保留 star 数、语言、仓库名、关键模块等重要细节。
3. 聚焦 AI Agent、LangGraph、LangChain、MCP、工具调用、状态管理、评测、部署等工程经验。
4. 输出必须是合法 JSON 对象。
"""


PORTFOLIO_PROJECT_PROMPT = """
你是 AI Agent Learning Coach 中的 Project Coach Agent。
请基于学习路线和开源项目分析，生成一个作品集级实战任务。

请输出 JSON 对象，不要输出 Markdown 或代码块。
JSON 字段：
- title：项目标题
- objective：项目目标，说明要解决的问题和最终效果
- github_references：数组，列出可参考仓库及借鉴点
- milestones：数组，5-7 个递进式里程碑
- technical_requirements：数组，核心技术要求
- deliverables：数组，最终应提交或展示的产物
- acceptance_criteria：数组，可验证的验收标准
- stretch_goals：数组，进阶挑战
- estimated_hours：整数，预计总投入小时数

要求：
1. 项目必须能放进作品集，而不是普通练习题。
2. 项目要结合用户学习目标、当前学习主题、学习路线和 GitHub 分析结果。
3. 验收标准必须可测试、可演示。
4. 优先贴合本系统定位：多 Agent 学习教练、LangGraph 工作流、MCP 工具接入、记忆、测评、开源项目分析。
5. 输出必须是合法 JSON 对象。
"""


def _github_search_queries(state: LearningCoachState, topic: str, goal: str) -> list[str]:
    """Build GitHub search queries from the learner goal and planner output."""
    plan = state.get("learning_plan", [])
    candidates: list[str] = []

    for item in plan:
        if not isinstance(item, dict):
            continue
        if item.get("topic") == topic and item.get("query"):
            candidates.append(str(item["query"]))
        elif item.get("query"):
            candidates.append(str(item["query"]))

    goal_terms = re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,}", goal)
    topic_terms = re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,}", topic)
    goal_query = " ".join(dict.fromkeys([*topic_terms, *goal_terms, "agent", "python"]))
    if goal_query.strip():
        candidates.insert(0, goal_query)

    if not candidates:
        candidates.append(f"{topic} agent python")

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean = " ".join(candidate.split())
        if not clean:
            continue
        if "language:" not in clean.lower():
            clean = f"{clean} language:python"
        if "stars:" not in clean.lower():
            clean = f"{clean} stars:>100"
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            queries.append(clean)
    return queries[:4]


def _dedupe_repositories(repositories: list[dict], limit: int = 3) -> list[dict]:
    unique: list[dict] = []
    seen: set[str] = set()
    for repo in repositories:
        name = str(repo.get("full_name") or repo.get("html_url") or repo.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(repo)
        if len(unique) >= limit:
            break
    return unique


def _fallback_repositories(search_queries: list[str]) -> list[dict]:
    fallback = [
        {
            "full_name": "langchain-ai/langgraph",
            "html_url": "https://github.com/langchain-ai/langgraph",
            "description": "Build resilient language agents as graphs.",
            "stargazers_count": 22000,
            "language": "Python",
            "topics": ["agents", "langgraph", "langchain", "state-machine"],
            "updated_at": None,
        },
        {
            "full_name": "modelcontextprotocol/python-sdk",
            "html_url": "https://github.com/modelcontextprotocol/python-sdk",
            "description": "The official Python SDK for Model Context Protocol servers and clients.",
            "stargazers_count": 7000,
            "language": "Python",
            "topics": ["mcp", "model-context-protocol", "python", "tools"],
            "updated_at": None,
        },
        {
            "full_name": "langchain-ai/langchain",
            "html_url": "https://github.com/langchain-ai/langchain",
            "description": "Build context-aware reasoning applications.",
            "stargazers_count": 110000,
            "language": "Python",
            "topics": ["agents", "llm", "rag", "tools"],
            "updated_at": None,
        },
    ]
    for repo in fallback:
        repo["search_queries"] = search_queries
        repo["source"] = "fallback"
    return [dump_model(GitHubRepository.model_validate(repo)) for repo in fallback]


def _fallback_analysis(repo: dict, topic: str) -> dict:
    full_name = str(repo.get("full_name") or "unknown")
    url = str(repo.get("html_url") or f"https://github.com/{full_name}")
    return {
        "core_insights": [
            f"该仓库可以作为 {topic} 的工程实现参考，重点观察入口、状态和工具层设计 [1]",
            "README 的安装、运行和示例结构可以作为作品集项目文档参考 [1]",
        ],
        "key_data": [
            f"repo: {full_name}",
            f"stars: {repo.get('stargazers_count', 0)}",
            f"language: {repo.get('language')}",
        ],
        "source_citations": [{"index": 1, "repo": full_name, "url": url}],
        "architecture": "建议阅读项目入口、状态模型、工具层、测试和部署说明。",
        "learning_value": "观察真实项目如何组织 Agent、工具、状态和错误处理。",
        "reading_order": ["README", "examples", "core graph/state", "tools", "tests"],
    }


def _project_fallback(goal: str, resources: list[dict]) -> dict:
    return {
        "title": "AI Agent Learning Coach",
        "objective": "实现一个基于 LangGraph 的多 Agent 学习工作流，并通过 MCP 风格适配器访问 GitHub 与文件系统。",
        "github_references": [
            {
                "repo": resource.get("name", ""),
                "takeaway": "借鉴项目结构、工具接入方式和 README 中的运行说明。",
            }
            for resource in resources
        ],
        "milestones": [
            "定义 TypedDict State 和 Supervisor 条件路由",
            "实现 Planner、Tutor、OpenSource Mentor、Assessment 等节点",
            "实现 GitHub 与 Filesystem 工具适配层",
            "基于开源仓库分析生成作品集实战任务",
            "增加 FastAPI 接口和端到端测试",
        ],
        "technical_requirements": ["LangGraph", "LangChain", "MCP Adapter", "FastAPI", "Vue"],
        "deliverables": ["可运行 Demo", "项目 README", "测试报告", "学习路线与项目任务 JSON 导出"],
        "acceptance_criteria": [
            "能根据学习目标生成阶段化路线",
            "能搜索并分析 GitHub 项目",
            "能生成可验收的作品集项目任务",
            "缺少外部服务时能给出清晰错误和降级结果",
        ],
        "stretch_goals": ["接入真实 GitHub API", "增加长期记忆个性化规划", "添加项目质量评分"],
        "estimated_hours": 18,
    }


def _stringify_project_list_items(project_task: dict, field_names: tuple[str, ...]) -> dict:
    normalized = dict(project_task)
    for field_name in field_names:
        values = normalized.get(field_name, [])
        if not isinstance(values, list):
            normalized[field_name] = [str(values)] if values else []
            continue

        items: list[str] = []
        for value in values:
            if isinstance(value, str):
                text = value
            elif isinstance(value, dict):
                text = (
                    value.get("title")
                    or value.get("description")
                    or value.get("milestone")
                    or value.get("objective")
                    or "；".join(str(part) for part in value.values() if part)
                )
            else:
                text = str(value)
            if text:
                items.append(str(text))
        normalized[field_name] = items
    return normalized


def opensource_mentor_agent(state: LearningCoachState) -> dict:
    """Search GitHub, summarize repositories, and generate a portfolio project task."""
    topic = str(state.get("current_topic") or "LangGraph MCP")
    goal = str(state.get("user_goal") or "学习 AI Agent 开发")

    client = GitHubMCPClient()
    search_queries = _github_search_queries(state, topic, goal)
    found_repositories: list[dict] = []
    for search_query in search_queries:
        found_repositories.extend(client.search_repositories(search_query, limit=3))
    repositories = _dedupe_repositories(found_repositories, limit=3)
    if not repositories:
        repositories = _fallback_repositories(search_queries)

    analyses = []
    resources = []

    for repo in repositories:
        full_name = str(repo.get("full_name") or "unknown")
        readme = client.read_readme(full_name)
        fallback = _fallback_analysis(repo, topic)

        analysis = as_dict(
            invoke_json(
                TASK_SUMMARIZER_PROMPT.format(
                    task_title=f"{topic} 开源项目分析",
                    task_intent="搜索并分析相关 GitHub 项目，提取可迁移的架构、工具调用和工程实践经验。",
                    task_query=" | ".join(search_queries),
                ),
                {"repo": repo, "readme": readme[:5000], "topic": topic, "goal": goal},
                fallback,
            ),
            fallback,
        )
        analysis["repo"] = full_name
        analyses.append(dump_model(RepoAnalysis.model_validate(analysis)))

        resources.append(dump_model(GitHubResource.model_validate({
            "name": full_name,
            "url": repo.get("html_url", f"https://github.com/{full_name}"),
            "description": repo.get("description", ""),
            "stars": repo.get("stargazers_count", 0),
            "language": repo.get("language"),
            "topics": repo.get("topics", [])[:8],
            "updated_at": repo.get("updated_at"),
            "search_queries": search_queries,
            "source": repo.get("source", "github"),
            "github_auth_mode": client.auth_mode,
        })))

    project_fallback = _project_fallback(goal, resources)
    project_task = as_dict(
        invoke_json(
            PORTFOLIO_PROJECT_PROMPT,
            {
                "goal": goal,
                "topic": topic,
                "learning_plan": state.get("learning_plan", []),
                "resources": resources,
                "repo_analysis": analyses,
            },
            project_fallback,
        ),
        project_fallback,
    )
    project_task = _stringify_project_list_items(
        project_task,
        (
            "milestones",
            "technical_requirements",
            "deliverables",
            "acceptance_criteria",
            "stretch_goals",
        ),
    )
    project_task = dump_model(ProjectTask.model_validate(project_task))

    return {
        "resources": resources,
        "repo_analysis": analyses,
        "project_task": project_task,
        "completed_agents": completed(state, "opensource_mentor"),
        "next_action": "supervisor",
        "status": "resources_and_project_completed",
    }


__all__ = ["opensource_mentor_agent"]
