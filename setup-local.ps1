$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot ".platform-venv"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is required. Install Node.js 20 LTS first."
}

uv python install 3.12
uv sync --extra dev

Push-Location frontend/vue
try {
    npm ci
}
finally {
    Pop-Location
}

Write-Host "Local environment is ready."
Write-Host "Backend: .\dev.ps1"
Write-Host "Frontend: cd frontend/vue; npm run dev"
Write-Host "Checks: .\check.ps1"