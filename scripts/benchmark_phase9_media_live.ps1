$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$outputPath = Join-Path $root ".tmp\phase9-media-live-search-cache.json"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

$env:PHASE9_MEDIA_LIVE_OUTPUT = $outputPath

Push-Location $backendPath
try {
    & $pythonPath benchmark_phase9_media_live.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 9 live media benchmark failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
    Remove-Item Env:\PHASE9_MEDIA_LIVE_OUTPUT -ErrorAction SilentlyContinue
}
