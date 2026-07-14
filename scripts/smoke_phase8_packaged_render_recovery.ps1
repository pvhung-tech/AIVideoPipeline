$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$sidecarPath = Join-Path $root "frontend\src-tauri\binaries\fastapi-sidecar-x86_64-pc-windows-msvc.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

if (-not (Test-Path -LiteralPath $sidecarPath)) {
    Write-Error "Packaged FastAPI sidecar was not found at $sidecarPath"
}

$previousSidecarPath = $env:PHASE8_RECOVERY_SIDECAR_PATH
$env:PHASE8_RECOVERY_SIDECAR_PATH = $sidecarPath

Push-Location $backendPath
try {
    & $pythonPath smoke_phase8_render_recovery.py
}
finally {
    Pop-Location
    $env:PHASE8_RECOVERY_SIDECAR_PATH = $previousSidecarPath
}
