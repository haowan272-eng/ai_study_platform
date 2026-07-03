"""Pydantic contracts for Agent state, tool IO and API payloads."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LearningTask(ContractModel):
    week: int = Field(ge=1, le=52)
    topic: str = Field(min_length=1, max_length=255)
    outcome: str = ""
    hours: int = Field(default=0, ge=0, le=200)
    intent: str = ""
    query: str = ""
    key_points: list[str] = Field(default_factory=list)
    practice: str = ""
    status: str = "pending"
    summary: str | None = None
    sources_summary: str | None = None


class GitHubSearchInput(ContractModel):
    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=3, ge=1, le=10)


class GitHubRepository(ContractModel):
    full_name: str = Field(min_length=1, max_length=255)
    html_url: str = Field(min_length=1, max_length=2048)
    description: str = ""
    stargazers_count: int = Field(default=0, ge=0)
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    source: Literal["github", "fallback"] = "github"
    search_queries: list[str] = Field(default_factory=list)


class GitHubResource(ContractModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    description: str = ""
    stars: int = Field(default=0, ge=0)
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    search_queries: list[str] = Field(default_factory=list)
    source: Literal["github", "fallback"] = "github"
    github_auth_mode: Literal["public", "token"] = "public"


class SourceCitation(ContractModel):
    index: int = Field(ge=1)
    repo: str = ""
    url: str = ""


class RepoAnalysis(ContractModel):
    repo: str = ""
    core_insights: list[str] = Field(default_factory=list)
    key_data: list[str] = Field(default_factory=list)
    source_citations: list[SourceCitation] = Field(default_factory=list)
    architecture: str = ""
    learning_value: str = ""
    reading_order: list[str] = Field(default_factory=list)

    @field_validator("core_insights", "key_data", "reading_order", mode="before")
    @classmethod
    def _stringify_analysis_list_items(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [f"{key}: {item}" for key, item in value.items() if item not in (None, "")]
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                parts = [f"{key}: {val}" for key, val in item.items() if val not in (None, "")]
                text = "; ".join(parts)
            else:
                text = str(item)
            if text.strip():
                normalized.append(text.strip())
        return normalized


class GitHubReference(ContractModel):
    repo: str = ""
    takeaway: str = ""


class ProjectTask(ContractModel):
    title: str = ""
    objective: str = ""
    github_references: list[GitHubReference] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    technical_requirements: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    stretch_goals: list[str] = Field(default_factory=list)
    estimated_hours: int = Field(default=0, ge=0, le=1000)

    @field_validator(
        "milestones",
        "technical_requirements",
        "deliverables",
        "acceptance_criteria",
        "stretch_goals",
        mode="before",
    )
    @classmethod
    def _stringify_list_items(cls, value: Any) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                parts = [
                    str(item.get(key) or "").strip()
                    for key in ("title", "name", "description", "summary", "content")
                    if item.get(key)
                ]
                text = " - ".join(parts) if parts else str(item)
            else:
                text = str(item)
            if text.strip():
                normalized.append(text.strip())
        return normalized


class TutorTask(ContractModel):
    title: str = ""
    objective: str = ""
    concepts: list[str] = Field(default_factory=list)
    example: str = ""
    practice_steps: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    learning_links: list[dict[str, Any]] = Field(default_factory=list)


class QuizQuestion(ContractModel):
    id: int | str
    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    topic: str = ""


class PublicQuizQuestion(ContractModel):
    id: int | str
    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    explanation: str = ""
    topic: str = ""
    correct_answer: str | None = None
    user_answer: str | None = None
    is_correct: bool | None = None


class InterviewQuestion(ContractModel):
    question: str = Field(min_length=1)
    reference_answer: str = ""
    follow_up: str = ""


class InterviewEvaluation(ContractModel):
    question: str = ""
    answer: str = ""
    score: float = Field(default=0, ge=0, le=100)
    feedback: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


class AgentError(ContractModel):
    node: str = ""
    error_type: str = ""
    message: str = ""
    retryable: bool = False


class AgentMetric(ContractModel):
    node: str = ""
    status: str = ""
    duration_ms: float = Field(default=0, ge=0)
    error_type: str | None = None


class LearningCoachStateModel(ContractModel):
    session_id: str = Field(default="", max_length=64)
    current_task_id: str = Field(default="", max_length=64)
    pause_requested: bool = False
    last_checkpoint_node: str = ""
    checkpoint_step: int = Field(default=0, ge=0)
    user_id: int | None = None
    learner_id: str = Field(default="anonymous", min_length=1, max_length=128)
    learner_memories: list[dict[str, Any]] = Field(default_factory=list)
    user_goal: str = ""

    current_topic: str = ""
    current_week: int = Field(default=1, ge=1, le=52)
    completed_weeks: list[int] = Field(default_factory=list)
    plan_only: bool = False
    learning_plan: list[LearningTask] = Field(default_factory=list)

    resources: list[GitHubResource] = Field(default_factory=list)
    repo_analysis: list[RepoAnalysis] = Field(default_factory=list)
    project_task: ProjectTask = Field(default_factory=ProjectTask)
    learning_report: str = ""

    tutor_content: str = ""
    tutor_task: TutorTask = Field(default_factory=TutorTask)
    quiz: list[QuizQuestion] = Field(default_factory=list)
    user_answers: list[str] = Field(default_factory=list)
    score: float | None = Field(default=None, ge=0, le=100)
    weak_points: list[str] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    interview_answers: list[str] = Field(default_factory=list)
    interview_evaluations: list[InterviewEvaluation] = Field(default_factory=list)
    interview_score: float | None = Field(default=None, ge=0, le=100)

    next_action: str = "supervisor"
    route_target: str = "end"
    messages: list[Any] = Field(default_factory=list)
    remediation_done: bool = False
    completed_agents: list[str] = Field(default_factory=list)
    status: str = "started"
    errors: list[AgentError] = Field(default_factory=list)
    failed_node: str | None = None
    retryable: bool = False
    agent_metrics: list[AgentMetric] = Field(default_factory=list)

    @field_validator("completed_weeks")
    @classmethod
    def _unique_completed_weeks(cls, value: list[int]) -> list[int]:
        return sorted({int(item) for item in value})


class PublicLearningCoachStateModel(LearningCoachStateModel):
    quiz: list[PublicQuizQuestion] = Field(default_factory=list)
    user_answers: list[str] = Field(default_factory=list, exclude=True)


def dump_model(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude_none=False)


def validate_state(value: dict[str, Any] | LearningCoachStateModel) -> LearningCoachStateModel:
    if isinstance(value, LearningCoachStateModel):
        return value
    return LearningCoachStateModel.model_validate(value)


def dump_state(value: dict[str, Any] | LearningCoachStateModel) -> dict[str, Any]:
    return dump_model(validate_state(value))


def dump_public_state(value: dict[str, Any]) -> dict[str, Any]:
    return PublicLearningCoachStateModel.model_validate(value).model_dump(mode="json", exclude_none=True)
