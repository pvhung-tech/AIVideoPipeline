$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $root "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$installerPath = Join-Path $root "frontend\src-tauri\target\release\bundle\msi\AI Video Pipeline Studio_0.1.0_x64_en-US.msi"
$installBase = Join-Path $root ".tmp\phase8-installed-app-msi-smoke"
$installPath = Join-Path $installBase ([Guid]::NewGuid().ToString("N"))
$installLog = Join-Path $installBase "msi-install.log"
$uninstallLog = Join-Path $installBase "msi-uninstall.log"
$registryPath = "HKCU:\Software\aivideopipeline\AI Video Pipeline Studio"

function Remove-SmokeInstallDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    $resolvedBase = (Resolve-Path -LiteralPath $BasePath).Path
    $resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path
    if ($resolvedTarget.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Backend virtual environment was not found at $pythonPath"
}

if (-not (Test-Path -LiteralPath $installerPath)) {
    Write-Error "MSI installer was not found at $installerPath"
}

New-Item -ItemType Directory -Force -Path $installBase | Out-Null
New-Item -ItemType Directory -Force -Path $installPath | Out-Null

$installed = $false
$health = $null
$hadRegistryInstallDir = $false
$previousRegistryInstallDir = $null

if (Test-Path -LiteralPath $registryPath) {
    $registryProperties = Get-ItemProperty -LiteralPath $registryPath
    $installDirProperty = $registryProperties.PSObject.Properties["InstallDir"]
    if ($installDirProperty) {
        $hadRegistryInstallDir = $true
        $previousRegistryInstallDir = $installDirProperty.Value
    }
}
else {
    New-Item -Path $registryPath -Force | Out-Null
}

New-ItemProperty -LiteralPath $registryPath -Name "InstallDir" -Value "$installPath\" -PropertyType String -Force | Out-Null

try {
    $installArgs = @(
        "/i",
        "`"$installerPath`"",
        "/qn",
        "/norestart",
        "INSTALLDIR=`"$installPath`"",
        "/L*v",
        "`"$installLog`""
    )
    $installer = Start-Process -FilePath "msiexec.exe" -ArgumentList $installArgs -Wait -PassThru -WindowStyle Hidden
    if ($installer.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $installLog) {
            if (Select-String -LiteralPath $installLog -Pattern "Error 1925" -Quiet) {
                Write-Error "MSI installer requires Administrator privileges because this package is per-machine. Run this smoke from an elevated terminal. Log: $installLog"
            }

            if (Select-String -LiteralPath $installLog -Pattern "Error 2502|Error 2503" -Quiet) {
                Write-Error "MSI installer could not complete in this restricted session. Run this smoke from a normal elevated Administrator terminal. Log: $installLog"
            }
        }

        Write-Error "MSI installer failed with exit code $($installer.ExitCode). Log: $installLog"
    }
    $installed = $true

    $appExe = Get-ChildItem -LiteralPath $installPath -Recurse -File -Filter "ai-video-pipeline-studio.exe" |
        Select-Object -First 1
    $sidecar = Get-ChildItem -LiteralPath $installPath -Recurse -File |
        Where-Object { $_.Name -eq "fastapi-sidecar.exe" -or $_.Name -like "fastapi-sidecar-*.exe" } |
        Select-Object -First 1

    if (-not $appExe) {
        Write-Error "Installed app executable was not found under $installPath"
    }

    if (-not $sidecar) {
        Write-Error "Installed FastAPI sidecar was not found under $installPath"
    }

    $port = 9898
    $existing = netstat.exe -ano -p tcp | Select-String "127.0.0.1:$port\s+.*LISTENING"
    if ($existing) {
        Write-Error "Port 127.0.0.1:$port is already in use."
    }

    $healthProcess = Start-Process -FilePath $sidecar.FullName -ArgumentList "--host", "127.0.0.1", "--port", $port -PassThru -WindowStyle Hidden
    try {
        $deadline = (Get-Date).AddSeconds(25)
        do {
            try {
                $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2
            }
            catch {
                Start-Sleep -Milliseconds 500
            }
        } until ($health -or (Get-Date) -gt $deadline)

        if (-not $health -or -not $health.success -or $health.data.status -ne "ok") {
            Write-Error "Installed MSI sidecar did not return a healthy FastAPI response."
        }
    }
    finally {
        if ($healthProcess -and -not $healthProcess.HasExited) {
            Stop-Process -Id $healthProcess.Id -Force -ErrorAction SilentlyContinue
        }
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
        InstallLog = $installLog
    } | Format-List
}
finally {
    if ($installed) {
        $uninstallArgs = @(
            "/x",
            "`"$installerPath`"",
            "/qn",
            "/norestart",
            "/L*v",
            "`"$uninstallLog`""
        )
        $uninstall = Start-Process -FilePath "msiexec.exe" -ArgumentList $uninstallArgs -Wait -PassThru -WindowStyle Hidden
        if ($uninstall.ExitCode -ne 0) {
            Write-Warning "MSI uninstaller exited with code $($uninstall.ExitCode). Log: $uninstallLog"
        }
    }

    Remove-SmokeInstallDirectory -BasePath $installBase -TargetPath $installPath

    if ($hadRegistryInstallDir) {
        New-ItemProperty -LiteralPath $registryPath -Name "InstallDir" -Value $previousRegistryInstallDir -PropertyType String -Force | Out-Null
    }
    else {
        Remove-ItemProperty -LiteralPath $registryPath -Name "InstallDir" -ErrorAction SilentlyContinue
    }
}
