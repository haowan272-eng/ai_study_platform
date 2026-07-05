$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot ".platform-venv"

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-dir alembic
