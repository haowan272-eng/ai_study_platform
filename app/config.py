"""Application configuration loaded from .env."""
import os

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
CORS_ORIGINS = [
    value.strip()
    for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if value.strip()
]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/coach.db")
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SHORT_TERM_MEMORY_TTL_SECONDS = max(300, int(os.getenv("SHORT_TERM_MEMORY_TTL_SECONDS", "86400")))
SHORT_TERM_MEMORY_EVENTS = max(5, int(os.getenv("SHORT_TERM_MEMORY_EVENTS", "30")))

COACH_LLM_API_KEY = os.getenv("COACH_LLM_API_KEY", "").strip()
COACH_LLM_BASE_URL = os.getenv("COACH_LLM_BASE_URL", "https://api.deepseek.com").strip()
COACH_LLM_MODEL = os.getenv("COACH_LLM_MODEL", "deepseek-chat").strip()
COACH_LLM_TEMPERATURE = float(os.getenv("COACH_LLM_TEMPERATURE", "0.2"))
COACH_LLM_RETRY_ATTEMPTS = max(1, int(os.getenv("COACH_LLM_RETRY_ATTEMPTS", "3")))
COACH_DATA_DIR = os.path.abspath(os.getenv("COACH_DATA_DIR", "data"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_RETRY_ATTEMPTS = max(1, int(os.getenv("GITHUB_RETRY_ATTEMPTS", "3")))
GITHUB_CACHE_TTL_SECONDS = max(60, int(os.getenv("GITHUB_CACHE_TTL_SECONDS", "3600")))

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL).strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL).strip()
CELERY_TASK_MAX_RETRIES = max(0, int(os.getenv("CELERY_TASK_MAX_RETRIES", "2")))

DEFAULT_SECRET_KEY = "dev-change-me-learning-coach"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY).strip()
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", f"{SECRET_KEY}-refresh").strip()
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))

if IS_PRODUCTION:
    if not SECRET_KEY or SECRET_KEY == DEFAULT_SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set to a non-default value when APP_ENV=production")
    if not REFRESH_SECRET_KEY or REFRESH_SECRET_KEY == f"{DEFAULT_SECRET_KEY}-refresh":
        raise RuntimeError("REFRESH_SECRET_KEY must be set to a non-default value when APP_ENV=production")
    if DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("DATABASE_URL must point to a production database when APP_ENV=production")
