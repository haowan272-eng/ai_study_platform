$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot ".platform-venv"

uv run --extra dev ruff check .
uv run --extra dev pytest

Push-Location frontend/vue
try {
    npm ci
    npm run build
}
finally {
    Pop-Location
}