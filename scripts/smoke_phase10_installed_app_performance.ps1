param(
    [string]$InstallerPath = "",
    [int]$Port = 9899,
    [int]$Attempts = 3,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $InstallerPath) {
    $InstallerPath = Join-Path $root "frontend\src-tauri\target\release\bundle\nsis\AI Video Pipeline Studio_0.1.0_x64-setup.exe"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $root ".tmp\phase10-installed-app-performance.json"
}

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    Write-Error "NSIS installer was not found at $InstallerPath"
}

$installBase = Join-Path $root ".tmp\phase10-installed-app-performance"
$installPath = Join-Path $installBase ([Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $installBase | Out-Null

$installer = Start-Process -FilePath $InstallerPath -ArgumentList "/S", "/D=$installPath" -Wait -PassThru -WindowStyle Hidden
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

$startupOutput = Join-Path $installBase "startup-$([Guid]::NewGuid().ToString('N')).json"
& (Join-Path $PSScriptRoot "smoke_phase10_sidecar_startup.ps1") -SidecarPath $sidecar.FullName -Port $Port -Attempts $Attempts -OutputPath $startupOutput

$startup = Get-Content -LiteralPath $startupOutput -Raw | ConvertFrom-Json
$summary = [PSCustomObject]@{
    Probe = "phase10_installed_app_performance"
    InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
    InstallPath = $installPath
    AppExe = $appExe.FullName
    Sidecar = $sidecar.FullName
    Startup = $startup
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$summary | Format-List

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
