$ErrorActionPreference = "Stop"

$backendPath = Join-Path $PSScriptRoot "..\backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Backend virtual environment not found. Create it and install requirements first."
}

Push-Location $backendPath
try {
    & $pythonPath -m uvicorn app.main:createApp --factory --reload --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}

