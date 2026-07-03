"""Unit and workflow tests for the Learning Coach."""
from app.agents.assessment import assessment_agent
from app.agents.supervisor import supervisor_agent
from app.graph import _run_parallel_agents, _safe_agent_node, run_learning_coach
from app.schemas.contracts import RepoAnalysis


def test_initial_run_generates_plan_resources_project_and_quiz(monkeypatch, tmp_path):
    from app.mcp.github_client import GitHubMCPClient

    monkeypatch.setattr(
        GitHubMCPClient,
        "search_repositories",
        lambda self, query, limit=3: [
            {
                "full_name": "langchain-ai/langgraph",
                "html_url": "https://github.com/langchain-ai/langgraph",
                "description": "Build resilient language agents as graphs.",
                "stargazers_count": 22000,
                "language": "Python",
            }
        ][:limit],
    )
    monkeypatch.setattr(
        GitHubMCPClient,
        "read_readme",
        lambda self, repo: "# langgraph\nBuild resilient language agents as graphs.",
    )
    result = run_learning_coach({
        "user_goal": "学习LangGraph和MCP",
        "messages": [],
        "learning_plan": [],
        "resources": [],
        "repo_analysis": [],
        "project_task": {},
        "learning_report": "",
        "quiz": [],
        "score": None,
        "weak_points": [],
        "interview_questions": [],
        "completed_agents": [],
        "remediation_done": False,
    })
    assert result["learning_plan"]
    assert result["resources"]
    assert result["repo_analysis"]
    assert result["project_task"]
    assert result["learning_report"]
    assert "opensource_mentor" in result["completed_agents"]
    assert len(result["quiz"]) == 5
    assert result["status"] == "awaiting_answers"


def test_score_below_60_routes_to_tutor():
    state = {"learning_plan": [{}], "tutor_content": "old", "resources": [{}],
             "project_task": {"title": "demo"}, "quiz": [{}], "score": 40,
             "remediation_done": False}
    assert supervisor_agent(state)["next_action"] == "tutor"


def test_missing_tutor_and_project_routes_to_parallel_learning():
    state = {"learning_plan": [{}], "tutor_content": "", "project_task": {}}
    result = supervisor_agent(state)
    assert result["route_target"] == "learning_parallel"
    assert result["next_action"] == "learning_parallel"


def test_empty_project_task_model_routes_to_open_source_mentor():
    state = {
        "learning_plan": [{}],
        "tutor_content": "lesson",
        "project_task": {
            "title": "",
            "objective": "",
            "github_references": [],
            "milestones": [],
            "technical_requirements": [],
            "deliverables": [],
            "acceptance_criteria": [],
            "stretch_goals": [],
            "estimated_hours": 0,
        },
    }
    result = supervisor_agent(state)
    assert result["route_target"] == "opensource_mentor"
    assert result["next_action"] == "opensource_mentor"


def test_repo_analysis_accepts_dict_key_data_from_llm():
    analysis = RepoAnalysis.model_validate({
        "repo": "langchain-ai/langchain",
        "core_insights": [{"title": "模块化", "description": "链式调用清晰"}],
        "key_data": {"stars": 140382, "language": "Python"},
        "reading_order": [{"step": "README"}, {"step": "examples"}],
    })

    assert "stars: 140382" in analysis.key_data
    assert analysis.core_insights[0] == "title: 模块化; description: 链式调用清晰"
    assert analysis.reading_order == ["step: README", "step: examples"]


def test_quiz_scoring_requires_exact_option_not_same_first_character():
    result = assessment_agent({
        "quiz": [
            {
                "id": 1,
                "question": "Which option is correct?",
                "options": ["Alpha correct", "Another wrong"],
                "correct_answer": "Alpha correct",
                "topic": "strict scoring",
            }
        ],
        "user_answers": ["Another wrong"],
        "completed_agents": [],
    })

    assert result["score"] == 0
    assert result["status"] == "assessment_failed"


def test_quiz_scoring_maps_letter_answers_to_options():
    result = assessment_agent({
        "quiz": [
            {
                "id": 1,
                "question": "Which option is correct?",
                "options": ["Wrong", "Correct"],
                "correct_answer": "B",
                "topic": "letter scoring",
            }
        ],
        "user_answers": ["Correct"],
        "completed_agents": [],
    })

    assert result["score"] == 100
    assert result["status"] == "assessment_passed"


def test_score_at_least_60_routes_to_interview():
    state = {"learning_plan": [{}], "tutor_content": "ok", "resources": [{}],
             "project_task": {"title": "demo"}, "quiz": [{}], "score": 60,
             "interview_questions": []}
    assert supervisor_agent(state)["next_action"] == "interview"


def test_scoring_path_generates_interview():
    initial = run_learning_coach({
        "user_goal": "学习Agent",
        "messages": [], "learning_plan": [], "resources": [], "repo_analysis": [],
        "project_task": {}, "learning_report": "", "quiz": [], "score": None, "weak_points": [],
        "interview_questions": [], "completed_agents": [], "remediation_done": False,
    })
    initial["user_answers"] = [q["correct_answer"] for q in initial["quiz"]]
    initial["score"] = None
    result = run_learning_coach(initial)
    assert result["score"] == 100
    assert result["interview_questions"]


def test_failed_scoring_path_returns_to_tutor_once():
    initial = run_learning_coach({
        "user_goal": "学习Agent",
        "messages": [], "learning_plan": [], "resources": [], "repo_analysis": [],
        "project_task": {}, "learning_report": "", "quiz": [], "score": None, "weak_points": [],
        "interview_questions": [], "completed_agents": [], "remediation_done": False,
    })
    initial["user_answers"] = ["错误"] * len(initial["quiz"])
    initial["score"] = None
    result = run_learning_coach(initial)
    assert result["score"] == 0
    assert result["remediation_done"] is True
    assert result["status"] == "remediation_completed"


def test_agent_exception_is_written_to_state():
    def broken_agent(state):
        raise RuntimeError("boom")

    result = _safe_agent_node("tutor", broken_agent)({"errors": []})

    assert result["status"] == "failed"
    assert result["failed_node"] == "tutor"
    assert result["errors"][0]["node"] == "tutor"
    assert result["errors"][0]["error_type"] == "RuntimeError"
    assert result["next_action"] == "supervisor"


def test_failed_state_routes_to_reporter_then_end():
    failed_state = {
        "status": "failed",
        "failed_node": "opensource_mentor",
        "errors": [{"node": "opensource_mentor", "message": "timeout"}],
    }
    assert supervisor_agent(failed_state)["route_target"] == "reporter"

    reported_state = {**failed_state, "learning_report": "failure report"}
    assert supervisor_agent(reported_state)["route_target"] == "end"

    completed_failure_report_state = {**failed_state, "status": "failed_report_completed"}
    assert supervisor_agent(completed_failure_report_state)["route_target"] == "end"


def test_parallel_learning_merges_branch_updates():
    def tutor(_state):
        return {
            "tutor_content": "lesson",
            "completed_agents": ["tutor"],
            "status": "tutoring_completed",
        }

    def mentor(_state):
        return {
            "project_task": {"title": "demo"},
            "completed_agents": ["opensource_mentor"],
            "status": "resources_and_project_completed",
        }

    result = _run_parallel_agents(
        {"completed_agents": []},
        {"tutor": tutor, "opensource_mentor": mentor},
    )

    assert result["tutor_content"] == "lesson"
    assert result["project_task"] == {"title": "demo"}
    assert set(result["completed_agents"]) == {"tutor", "opensource_mentor"}
    assert result["status"] == "parallel_learning_completed"


def test_parallel_learning_keeps_successful_branch_when_other_branch_fails():
    def tutor(_state):
        return {"tutor_content": "lesson", "completed_agents": ["tutor"]}

    def mentor(_state):
        raise TimeoutError("github timeout")

    result = _run_parallel_agents(
        {"completed_agents": [], "errors": []},
        {"tutor": tutor, "opensource_mentor": mentor},
    )

    assert result["tutor_content"] == "lesson"
    assert result["status"] == "failed"
    assert result["failed_node"] == "opensource_mentor"
    assert result["errors"][0]["error_type"] == "TimeoutError"
