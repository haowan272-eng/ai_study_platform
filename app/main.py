"""FastAPI application factory for AI Agent Learning Coach."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import CORS_ORIGINS
from app.redis_client import close_redis, init_redis
from app.services.observability import ErrorEvent, configure_logging, get_logger, record_error_event


configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        init_redis()
    except Exception as exc:
        record_error_event(ErrorEvent(
            component="redis",
            operation="init_redis",
            error_type=type(exc).__name__,
            error_message=str(exc),
            fallback_used=True,
            severity="warning",
        ))
        logger.warning("Redis unavailable, short-term memory degraded")
    try:
        yield
    finally:
        close_redis()


app = FastAPI(title="AI Agent Learning Coach", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-agent-learning-coach"}


@app.get("/metrics")
def metrics():
    return {
        "service": "ai-agent-learning-coach",
        "queue": "celery",
    }
