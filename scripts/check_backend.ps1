$ErrorActionPreference = "Stop"

$backendPath = Join-Path $PSScriptRoot "..\backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Backend virtual environment not found. Create it and install requirements first."
}

Push-Location $backendPath
try {
    & $pythonPath -m ruff check app tests
    if ($LASTEXITCODE -ne 0) {
        throw "Ruff failed with exit code $LASTEXITCODE."
    }

    & $pythonPath -m mypy app tests
    if ($LASTEXITCODE -ne 0) {
        throw "Mypy failed with exit code $LASTEXITCODE."
    }

    & $pythonPath -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw "Pytest failed with exit code $LASTEXITCODE."
    }

    & $pythonPath check_media_dedup_regression.py
    if ($LASTEXITCODE -ne 0) {
        throw "Media deduplication regression gate failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
