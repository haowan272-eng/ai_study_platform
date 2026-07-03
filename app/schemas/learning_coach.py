"""API contracts for the Learning Coach."""
from pydantic import BaseModel, Field

from app.schemas.contracts import PublicLearningCoachStateModel


class StartLearningRequest(BaseModel):
    user_goal: str = Field(min_length=3, max_length=2000)
    learner_id: str = Field(default="anonymous", min_length=1, max_length=128)


class SubmitQuizRequest(BaseModel):
    answers: list[str] = Field(min_length=1, max_length=20)


class SubmitInterviewRequest(BaseModel):
    answers: list[str] = Field(min_length=1, max_length=20)


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LearningCoachResponse(BaseModel):
    session_id: str
    state: PublicLearningCoachStateModel


__all__ = [
    "AuthRequest",
    "LearningCoachResponse",
    "RefreshRequest",
    "StartLearningRequest",
    "SubmitInterviewRequest",
    "SubmitQuizRequest",
    "TokenResponse",
]
