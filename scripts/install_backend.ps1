$ErrorActionPreference = "Stop"

$backendPath = Join-Path $PSScriptRoot "..\backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

Push-Location $backendPath
try {
    if (-not (Test-Path $pythonPath)) {
        py -m venv .venv
    }

    & $pythonPath -m pip install --upgrade pip
    & $pythonPath -m pip install -r requirements.txt -r requirements-dev.txt
}
finally {
    Pop-Location
}

