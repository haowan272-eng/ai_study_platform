"""FastAPI entry points for the Learning Coach graph."""
from __future__ import annotations

import asyncio
import json
import uuid

import redis.asyncio as async_redis
from redis.exceptions import RedisError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.config import REDIS_URL
from app.dependencies import get_current_user
from app.graph import run_learning_coach_checkpointed
from app.models import User
from app.schemas.contracts import InterviewEvaluation, dump_model, dump_public_state, dump_state
from app.schemas.learning_coach import (
    LearningCoachResponse,
    StartLearningRequest,
    SubmitInterviewRequest,
    SubmitQuizRequest,
)
from app.services.coach_memory import append_short_term_event, load_short_term_events
from app.services.llm import invoke_json
from app.services.observability import ErrorEvent, record_error_event
from app.services.storage import get_record_store
from app.redis_client import get_redis
from app.tasks import run_learning_task

router = APIRouter(prefix="/learning-coach", tags=["AI Agent Learning Coach"])

TERMINAL_STATUSES = {
    "awaiting_answers",
    "assessment_failed",
    "interview_reviewed",
    "course_completed",
    "failed",
    "failed_report_completed",
    "paused",
}


def _serializable(state: dict) -> dict:
    """Convert workflow state into JSON-serializable data."""
    value = dict(state)
    value["messages"] = [
        {
            "type": getattr(item, "type", "message"),
            "content": str(getattr(item, "content", item)),
        }
        for item in value.get("messages", [])
    ]
    return dump_state(value)


def _public_state(state: dict) -> dict:
    """Return state that is safe for the frontend to display."""
    value = _serializable(state)
    answers = list(value.get("user_answers", []) or [])
    show_answers = value.get("score") is not None and bool(answers)
    public_quiz = []
    for index, question in enumerate(value.get("quiz", [])):
        item = dict(question)
        correct_answer = str(item.get("correct_answer", ""))
        user_answer = str(answers[index]) if index < len(answers) else ""
        if show_answers:
            item["correct_answer"] = correct_answer
            item["user_answer"] = user_answer
            item["is_correct"] = bool(
                user_answer and user_answer.strip().casefold() == correct_answer.strip().casefold()
            )
        else:
            item.pop("correct_answer", None)
        public_quiz.append(item)
    value["quiz"] = public_quiz
    value.pop("user_answers", None)
    return dump_public_state(value)


def _sse_channel(session_id: str) -> str:
    return f"learning-coach:events:{session_id}"


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _state_event(session_id: str, state: dict, message: str | None = None) -> dict:
    public_state = _public_state(state)
    completed = public_state.get("completed_agents") or []
    return {
        "session_id": session_id,
        "agent": completed[-1] if completed else "session",
        "status": public_state.get("status"),
        "next_action": public_state.get("next_action"),
        "completed_agents": completed,
        "message": message,
        "state": public_state,
    }


def _publish_state_event(session_id: str, state: dict, message: str | None = None) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.publish(_sse_channel(session_id), json.dumps(_state_event(session_id, state, message), ensure_ascii=False))
    except RedisError as exc:
        record_error_event(ErrorEvent(
            component="sse",
            operation="publish_state_event",
            error_type=type(exc).__name__,
            error_message=str(exc),
            fallback_used=True,
            severity="warning",
            session_id=session_id,
        ))


def _initial_state(session_id: str, body: StartLearningRequest, user: User, memories: list[dict]) -> dict:
    return {
        "session_id": session_id,
        "current_task_id": "",
        "pause_requested": False,
        "last_checkpoint_node": "",
        "checkpoint_step": 0,
        "user_id": user.id,
        "learner_id": user.username,
        "learner_memories": memories,
        "user_goal": body.user_goal,
        "plan_only": True,
        "current_week": 1,
        "completed_weeks": [],
        "messages": [],
        "learning_plan": [],
        "resources": [],
        "repo_analysis": [],
        "project_task": {},
        "tutor_task": {},
        "learning_report": "",
        "quiz": [],
        "score": None,
        "weak_points": [],
        "interview_questions": [],
        "interview_answers": [],
        "interview_evaluations": [],
        "interview_score": None,
        "completed_agents": [],
        "remediation_done": False,
        "status": "queued",
        "next_action": "wait_for_result",
    }


def _task_for_week(state: dict, week: int) -> dict | None:
    for item in state.get("learning_plan", []):
        if isinstance(item, dict) and int(item.get("week") or 0) == week:
            return item
    return None


def _prepare_week_state(state: dict, week: int, completed_weeks: list[int] | None = None) -> dict:
    task = _task_for_week(state, week)
    if not task:
        raise HTTPException(status_code=404, detail="未找到对应的学习周")

    completed_set = set(completed_weeks if completed_weeks is not None else state.get("completed_weeks", []))
    plan = []
    for item in state.get("learning_plan", []):
        if not isinstance(item, dict):
            continue
        value = dict(item)
        item_week = int(value.get("week") or 0)
        if item_week in completed_set:
            value["status"] = "completed"
        elif item_week == week:
            value["status"] = "active"
        elif value.get("status") == "active":
            value["status"] = "pending"
        plan.append(value)

    prepared = dict(state)
    prepared.update({
        "plan_only": False,
        "current_week": week,
        "completed_weeks": sorted(completed_set),
        "current_topic": str(task.get("topic") or f"第 {week} 周"),
        "learning_plan": plan,
        "tutor_content": "",
        "resources": [],
        "repo_analysis": [],
        "project_task": {},
        "tutor_task": {},
        "learning_report": "",
        "quiz": [],
        "user_answers": [],
        "score": None,
        "weak_points": [],
        "interview_questions": [],
        "interview_answers": [],
        "interview_evaluations": [],
        "interview_score": None,
        "remediation_done": False,
        "completed_agents": ["planner"],
        "next_action": "wait_for_result",
        "status": "queued",
        "pause_requested": False,
        "last_checkpoint_node": "",
        "checkpoint_step": 0,
        "errors": [],
        "failed_node": None,
        "retryable": False,
    })
    return prepared


def _load_owned_session(session_id: str, user: User) -> dict:
    state = get_record_store().get(session_id, user.id)
    if not state:
        raise HTTPException(status_code=404, detail="学习会话不存在，或不属于当前用户")
    return state


def _save_state(session_id: str, state: dict) -> dict:
    stored = _serializable(state)
    get_record_store().save(session_id, stored)
    _publish_state_event(session_id, stored)
    return stored


def _enqueue_learning_task(session_id: str, state: dict, event: dict | None = None):
    task_id = str(state.get("current_task_id") or uuid.uuid4().hex)
    state["current_task_id"] = task_id
    _save_state(session_id, state)
    try:
        return run_learning_task.apply_async(args=[session_id, state, event], task_id=task_id)
    except Exception as exc:
        failed_state = dict(state)
        failed_state.update({
            "status": "failed",
            "failed_node": "celery_broker",
            "next_action": "start_redis_and_worker",
            "errors": [
                *failed_state.get("errors", []),
                {
                    "node": "celery_broker",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "retryable": True,
                },
            ],
        })
        _save_state(session_id, failed_state)
        raise HTTPException(
            status_code=503,
            detail="后台任务队列不可用，请先启动 Redis 和 Celery worker。",
        ) from exc


def _stored_task_state(session_id: str, task_id: str | None, fallback: dict) -> dict:
    stored = get_record_store().get(session_id)
    if stored and task_id and stored.get("current_task_id") == task_id:
        return dict(stored)
    return dict(fallback)


def _run_learning_task(session_id: str, state: dict, event: dict | None = None) -> None:
    task_id = str(state.get("current_task_id") or "")
    latest_state = get_record_store().get(session_id)
    if latest_state and task_id and latest_state.get("current_task_id") != task_id:
        return
    running_state = _stored_task_state(session_id, task_id, state)
    if running_state.get("status") in TERMINAL_STATUSES and not running_state.get("pause_requested"):
        return
    if running_state.get("pause_requested"):
        running_state["pause_requested"] = False
        running_state["status"] = "paused"
        running_state["next_action"] = "resume_task"
        _save_state(session_id, running_state)
        return

    running_state["status"] = "running"
    running_state["next_action"] = "wait_for_result"
    running_state["pause_requested"] = False
    _save_state(session_id, running_state)

    try:
        def checkpoint(next_state: dict) -> bool:
            latest = get_record_store().get(session_id) or {}
            pause_requested = (
                next_state.get("status") != "paused"
                and latest.get("current_task_id") == running_state.get("current_task_id")
                and bool(latest.get("pause_requested"))
            )
            if pause_requested:
                next_state["pause_requested"] = True
                next_state["status"] = "pausing"
                next_state["next_action"] = "pause_after_checkpoint"
            _save_state(session_id, next_state)
            return pause_requested

        result = _serializable(run_learning_coach_checkpointed(running_state, checkpoint))
        get_record_store().save(session_id, result)
        if event and result.get("user_id") is not None:
            append_short_term_event(int(result["user_id"]), session_id, event)
    except Exception as exc:
        failed_state = dict(running_state)
        failed_state.update({
            "status": "failed",
            "failed_node": "background_task",
            "next_action": "inspect_failure",
            "errors": [
                *failed_state.get("errors", []),
                {
                    "node": "background_task",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "retryable": False,
                },
            ],
        })
        _save_state(session_id, failed_state)
        raise


def _fallback_interview_score(answer: str, reference_answer: str) -> dict:
    answer_words = {word.lower() for word in answer.split() if len(word) > 2}
    reference_words = {word.lower() for word in reference_answer.split() if len(word) > 2}
    overlap = len(answer_words & reference_words)
    score = min(100, max(20 if answer.strip() else 0, overlap * 12))
    return {
        "score": score,
        "feedback": "已经覆盖部分要点，但还需要补充更具体的架构细节、取舍理由和项目例子。",
        "strengths": ["已经提交答案", "触及了部分核心主题"] if answer.strip() else [],
        "improvements": ["对照参考答案补齐关键概念", "加入实现细节、边界情况和故障处理"],
    }


def _grade_interview_answer(question: dict, answer: str) -> dict:
    reference_answer = str(question.get("reference_answer") or "")
    fallback = _fallback_interview_score(answer, reference_answer)
    result = invoke_json(
        (
            "你是中文技术面试官。请根据参考答案评价候选人的回答。"
            "只返回合法 JSON，字段包括：score 数字 0-100、feedback 字符串、"
            "strengths 数组、improvements 数组。"
            "feedback、strengths、improvements 必须使用中文，表达简洁、具体、可执行。"
        ),
        {
            "question": question.get("question"),
            "candidate_answer": answer,
            "reference_answer": reference_answer,
            "follow_up": question.get("follow_up"),
        },
        fallback,
    )
    if not isinstance(result, dict):
        return fallback
    try:
        score = float(result.get("score", fallback["score"]))
    except (TypeError, ValueError):
        score = float(fallback["score"])
    result["score"] = max(0, min(100, round(score, 2)))
    result["feedback"] = str(result.get("feedback") or fallback["feedback"])
    result["strengths"] = list(result.get("strengths") or fallback["strengths"])
    result["improvements"] = list(result.get("improvements") or fallback["improvements"])
    return dump_model(InterviewEvaluation.model_validate(result))


@router.post("/start", response_model=LearningCoachResponse)
def start_learning(
    body: StartLearningRequest,
    current_user: User = Depends(get_current_user),
):
    session_id = uuid.uuid4().hex
    store = get_record_store()
    memories = store.memories(current_user.id)
    state = _initial_state(session_id, body, current_user, memories)
    _save_state(session_id, state)
    task = _enqueue_learning_task(session_id, state, {"event": "session_started", "goal": body.user_goal})
    state["current_task_id"] = task.id
    stored = _save_state(session_id, state)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.get("/{session_id}/events")
async def stream_learning_events(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    state = _load_owned_session(session_id, current_user)

    async def event_stream():
        client = async_redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        try:
            yield _format_sse(_state_event(session_id, state, "connected"))
            await pubsub.subscribe(_sse_channel(session_id))
            while not await request.is_disconnected():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message and message.get("type") == "message":
                    yield f"data: {message['data']}\n\n"
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0)
        finally:
            await pubsub.unsubscribe(_sse_channel(session_id))
            await pubsub.close()
            await client.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/pause", response_model=LearningCoachResponse)
def pause_learning_task(session_id: str, current_user: User = Depends(get_current_user)):
    state = _load_owned_session(session_id, current_user)
    if state.get("status") not in {"queued", "running", "pausing"}:
        raise HTTPException(status_code=409, detail="当前任务不在运行中，不能暂停")

    state["pause_requested"] = True
    if state.get("status") == "queued":
        state["status"] = "paused"
        state["next_action"] = "resume_task"
    else:
        state["status"] = "pausing"
        state["next_action"] = "pause_after_checkpoint"
    stored = _save_state(session_id, state)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.post("/{session_id}/resume", response_model=LearningCoachResponse)
def resume_learning_task(session_id: str, current_user: User = Depends(get_current_user)):
    state = _load_owned_session(session_id, current_user)
    if state.get("status") not in {"paused", "pausing"}:
        raise HTTPException(status_code=409, detail="当前任务没有暂停，不能继续")

    state["pause_requested"] = False
    state["status"] = "queued"
    state["next_action"] = "wait_for_result"
    _save_state(session_id, state)
    task = _enqueue_learning_task(session_id, state, {"event": "task_resumed"})
    state["current_task_id"] = task.id
    stored = _save_state(session_id, state)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.post("/{session_id}/weeks/{week}/start", response_model=LearningCoachResponse)
def start_week(
    session_id: str,
    week: int,
    current_user: User = Depends(get_current_user),
):
    state = _load_owned_session(session_id, current_user)
    prepared = _prepare_week_state(state, week)
    _save_state(session_id, prepared)
    task = _enqueue_learning_task(
        session_id,
        prepared,
        {"event": "week_started", "week": week, "topic": prepared.get("current_topic")},
    )
    prepared["current_task_id"] = task.id
    stored = _save_state(session_id, prepared)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.post("/{session_id}/weeks/{week}/complete", response_model=LearningCoachResponse)
def complete_week(
    session_id: str,
    week: int,
    current_user: User = Depends(get_current_user),
):
    state = _load_owned_session(session_id, current_user)
    if not _task_for_week(state, week):
        raise HTTPException(status_code=404, detail="未找到对应的学习周")

    completed_weeks = sorted({*state.get("completed_weeks", []), week})
    next_week = week + 1
    if not _task_for_week(state, next_week):
        final_state = dict(state)
        final_state["completed_weeks"] = completed_weeks
        final_state["learning_plan"] = [
            {**item, "status": "completed"}
            if isinstance(item, dict) and int(item.get("week") or 0) in completed_weeks
            else item
            for item in state.get("learning_plan", [])
        ]
        final_state["next_action"] = "all_weeks_completed"
        final_state["status"] = "course_completed"
        stored = _save_state(session_id, final_state)
        return LearningCoachResponse(session_id=session_id, state=_public_state(stored))

    prepared = _prepare_week_state(state, next_week, completed_weeks)
    _save_state(session_id, prepared)
    task = _enqueue_learning_task(
        session_id,
        prepared,
        {"event": "week_completed", "week": week, "next_week": next_week},
    )
    prepared["current_task_id"] = task.id
    stored = _save_state(session_id, prepared)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.get("/sessions")
def list_learning_sessions(limit: int = Query(default=10, ge=1, le=50), current_user: User = Depends(get_current_user)):
    return {"sessions": get_record_store().list_sessions(current_user.id, limit)}


@router.get("/sessions/latest", response_model=LearningCoachResponse)
def get_latest_learning_session(current_user: User = Depends(get_current_user)):
    sessions = get_record_store().list_sessions(current_user.id, 1)
    if not sessions:
        raise HTTPException(status_code=404, detail="当前账号还没有学习记录")
    session_id = str(sessions[0]["session_id"])
    state = _load_owned_session(session_id, current_user)
    return LearningCoachResponse(session_id=session_id, state=_public_state(state))


@router.get("/{session_id}", response_model=LearningCoachResponse)
def get_learning_session(session_id: str, current_user: User = Depends(get_current_user)):
    state = _load_owned_session(session_id, current_user)
    return LearningCoachResponse(session_id=session_id, state=_public_state(state))


@router.post("/{session_id}/submit", response_model=LearningCoachResponse)
def submit_quiz(
    session_id: str,
    body: SubmitQuizRequest,
    current_user: User = Depends(get_current_user),
):
    state = _load_owned_session(session_id, current_user)
    if not state.get("quiz"):
        raise HTTPException(status_code=409, detail="当前会话还没有生成测验题")
    state.update({
        "user_answers": body.answers,
        "score": None,
        "weak_points": [],
        "interview_questions": [],
        "interview_answers": [],
        "interview_evaluations": [],
        "interview_score": None,
        "remediation_done": False,
        "next_action": "wait_for_result",
        "status": "queued",
        "pause_requested": False,
        "last_checkpoint_node": "",
        "checkpoint_step": 0,
    })
    _save_state(session_id, state)
    task = _enqueue_learning_task(session_id, state, {"event": "quiz_submitted"})
    state["current_task_id"] = task.id
    stored = _save_state(session_id, state)
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.post("/{session_id}/interview/submit", response_model=LearningCoachResponse)
def submit_interview(session_id: str, body: SubmitInterviewRequest, current_user: User = Depends(get_current_user)):
    state = _load_owned_session(session_id, current_user)
    questions = [item for item in state.get("interview_questions", []) if isinstance(item, dict)]
    if not questions:
        raise HTTPException(status_code=409, detail="当前会话还没有生成面试题")

    answers = list(body.answers)
    evaluations = []
    for index, question in enumerate(questions):
        answer = str(answers[index] if index < len(answers) else "")
        evaluation = _grade_interview_answer(question, answer)
        evaluation["question"] = question.get("question")
        evaluation["answer"] = answer
        evaluations.append(evaluation)

    average_score = round(sum(float(item.get("score") or 0) for item in evaluations) / max(1, len(evaluations)), 2)
    updated = dict(state)
    updated.update({
        "interview_answers": answers,
        "interview_evaluations": evaluations,
        "interview_score": average_score,
        "status": "interview_reviewed",
    })
    stored = _save_state(session_id, updated)
    append_short_term_event(current_user.id, session_id, {"event": "interview_reviewed", "score": average_score})
    return LearningCoachResponse(session_id=session_id, state=_public_state(stored))


@router.get("/{session_id}/memory")
def get_session_memory(session_id: str, current_user: User = Depends(get_current_user)):
    _load_owned_session(session_id, current_user)
    return {
        "short_term": load_short_term_events(current_user.id, session_id),
        "long_term": get_record_store().memories(current_user.id),
    }


__all__ = ["TERMINAL_STATUSES", "_run_learning_task", "router"]
