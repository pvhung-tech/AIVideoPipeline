$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

Push-Location $backendPath
try {
    & $pythonPath smoke_phase8_render_recovery.py
}
finally {
    Pop-Location
}
