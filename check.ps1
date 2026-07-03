$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

python -m ruff check .
python -m pytest

Push-Location frontend/vue
try {
    npm run build
}
finally {
    Pop-Location
}
