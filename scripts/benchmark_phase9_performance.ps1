$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$outputPath = Join-Path $root ".tmp\phase9-performance-matrix.json"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

$env:PHASE9_PERF_OUTPUT = $outputPath

Push-Location $backendPath
try {
    & $pythonPath benchmark_phase9_performance.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 9 performance benchmark failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
    Remove-Item Env:\PHASE9_PERF_OUTPUT -ErrorAction SilentlyContinue
}
