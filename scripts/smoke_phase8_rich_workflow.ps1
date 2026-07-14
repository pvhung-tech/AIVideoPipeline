$ErrorActionPreference = "Stop"

$backendPath = Join-Path $PSScriptRoot "..\backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment not found. Create it and install requirements first."
}

Push-Location $backendPath
try {
    & $pythonPath smoke_phase8_rich_workflow.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 8 rich workflow smoke failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
