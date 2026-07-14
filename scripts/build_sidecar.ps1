$ErrorActionPreference = "Stop"

$repositoryPath = Split-Path $PSScriptRoot -Parent
$backendPath = Join-Path $repositoryPath "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$binariesPath = Join-Path $repositoryPath "frontend\src-tauri\binaries"
$sidecarDistPath = Join-Path $backendPath "dist\sidecar"
$sidecarWorkPath = Join-Path $backendPath "build\sidecar"
$specPath = Join-Path $backendPath "build"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Backend virtual environment not found. Run scripts\install_backend.ps1 first."
}

$targetTriple = (& rustc --print host-tuple).Trim()
if (-not $targetTriple) {
    throw "Unable to determine the Rust host target triple."
}

$executableExtension = if ($IsWindows -or $env:OS -eq "Windows_NT") { ".exe" } else { "" }
$sourceBinary = Join-Path $sidecarDistPath "fastapi-sidecar$executableExtension"
$targetBinary = Join-Path $binariesPath "fastapi-sidecar-$targetTriple$executableExtension"

New-Item -ItemType Directory -Path $binariesPath -Force | Out-Null

Push-Location $backendPath
try {
    & $pythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name "fastapi-sidecar" `
        --distpath $sidecarDistPath `
        --workpath $sidecarWorkPath `
        --specpath $specPath `
        --add-data "$repositoryPath\configs;configs" `
        --hidden-import "uvicorn.lifespan.on" `
        --hidden-import "uvicorn.loops.asyncio" `
        --hidden-import "uvicorn.protocols.http.h11_impl" `
        --exclude-module "httptools" `
        --exclude-module "uvloop" `
        --exclude-module "watchfiles" `
        --exclude-module "websockets" `
        --exclude-module "wsproto" `
        sidecar.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Copy-Item -LiteralPath $sourceBinary -Destination $targetBinary -Force
Write-Output "Sidecar created: $targetBinary"
