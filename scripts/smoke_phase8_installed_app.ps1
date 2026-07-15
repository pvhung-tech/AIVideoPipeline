$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$installerPath = Join-Path $root "frontend\src-tauri\target\release\bundle\nsis\AI Video Pipeline Studio_0.1.0_x64-setup.exe"
$installBase = Join-Path $root ".tmp\phase8-installed-app-smoke"
$installPath = Join-Path $installBase ([Guid]::NewGuid().ToString("N"))

function Stop-SidecarProcessesFromPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SidecarPath
    )

    $resolvedSidecarPath = (Resolve-Path -LiteralPath $SidecarPath -ErrorAction SilentlyContinue).Path
    if (-not $resolvedSidecarPath) {
        return
    }

    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -like "fastapi-sidecar*" -and $_.Path -eq $resolvedSidecarPath } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

if (-not (Test-Path -LiteralPath $installerPath)) {
    Write-Error "NSIS installer was not found at $installerPath"
}

New-Item -ItemType Directory -Force -Path $installBase | Out-Null

$installer = Start-Process -FilePath $installerPath -ArgumentList "/S", "/D=$installPath" -Wait -PassThru -WindowStyle Hidden
if ($installer.ExitCode -ne 0) {
    Write-Error "NSIS installer failed with exit code $($installer.ExitCode)."
}

$appExe = Get-ChildItem -LiteralPath $installPath -Recurse -File -Filter "ai-video-pipeline-studio.exe" | Select-Object -First 1
$sidecar = Get-ChildItem -LiteralPath $installPath -Recurse -File |
    Where-Object { $_.Name -eq "fastapi-sidecar.exe" -or $_.Name -like "fastapi-sidecar-*.exe" } |
    Select-Object -First 1

if (-not $appExe) {
    Write-Error "Installed app executable was not found under $installPath"
}

if (-not $sidecar) {
    Write-Error "Installed FastAPI sidecar was not found under $installPath"
}

$port = 9897
$existing = netstat.exe -ano -p tcp | Select-String "127.0.0.1:$port\s+.*LISTENING"
if ($existing) {
    Write-Error "Port 127.0.0.1:$port is already in use."
}

$healthProcess = Start-Process -FilePath $sidecar.FullName -ArgumentList "--host", "127.0.0.1", "--port", $port -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds(25)
    $health = $null
    do {
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    } until ($health -or (Get-Date) -gt $deadline)

    if (-not $health -or -not $health.success -or $health.data.status -ne "ok") {
        Write-Error "Installed sidecar did not return a healthy FastAPI response."
    }
}
finally {
    if ($healthProcess -and -not $healthProcess.HasExited) {
        Stop-Process -Id $healthProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-SidecarProcessesFromPath -SidecarPath $sidecar.FullName
}

$previousSidecarPath = $env:PHASE8_RECOVERY_SIDECAR_PATH
$env:PHASE8_RECOVERY_SIDECAR_PATH = $sidecar.FullName

Push-Location $backendPath
try {
    & $pythonPath smoke_phase8_render_recovery.py
}
finally {
    Pop-Location
    $env:PHASE8_RECOVERY_SIDECAR_PATH = $previousSidecarPath
}

[PSCustomObject]@{
    InstallPath = $installPath
    AppExe = $appExe.FullName
    Sidecar = $sidecar.FullName
    Health = $health.data.status
} | Format-List

$uninstaller = Join-Path $installPath "uninstall.exe"
if (Test-Path -LiteralPath $uninstaller) {
    $uninstall = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru -WindowStyle Hidden
    if ($uninstall.ExitCode -ne 0) {
        Write-Warning "Installed app uninstaller exited with code $($uninstall.ExitCode)."
    }
}

$resolvedInstallBase = (Resolve-Path -LiteralPath $installBase).Path
if ((Test-Path -LiteralPath $installPath) -and $installPath.StartsWith($resolvedInstallBase, [StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $installPath -Recurse -Force -ErrorAction SilentlyContinue
}
