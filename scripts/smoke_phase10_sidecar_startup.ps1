param(
    [string]$SidecarPath = "",
    [int]$Port = 9898,
    [int]$Attempts = 3,
    [int]$TimeoutSeconds = 25,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $SidecarPath) {
    $SidecarPath = Join-Path $root "frontend\src-tauri\binaries\fastapi-sidecar-x86_64-pc-windows-msvc.exe"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $root ".tmp\phase10-sidecar-startup.json"
}

if (-not (Test-Path -LiteralPath $SidecarPath)) {
    Write-Error "FastAPI sidecar was not found at $SidecarPath"
}

if ($Attempts -lt 1) {
    Write-Error "Attempts must be at least 1."
}

$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$workspace = Join-Path $root ".tmp\phase10-sidecar-startup"
New-Item -ItemType Directory -Force -Path $workspace | Out-Null

$samples = @()
for ($index = 1; $index -le $Attempts; $index++) {
    $existing = netstat.exe -ano -p tcp | Select-String "127.0.0.1:$Port\s+.*LISTENING"
    if ($existing) {
        Write-Error "Port 127.0.0.1:$Port is already in use."
    }

    $appData = Join-Path $workspace "app-data-$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Force -Path $appData | Out-Null
    $previousAppData = $env:APP_DATA_DIR
    $env:APP_DATA_DIR = $appData
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $SidecarPath -ArgumentList "--host", "127.0.0.1", "--port", $Port -PassThru -WindowStyle Hidden
    try {
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        $health = $null
        do {
            try {
                $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
            }
            catch {
                Start-Sleep -Milliseconds 100
            }
        } until ($health -or (Get-Date) -gt $deadline)
        $stopwatch.Stop()

        if (-not $health -or -not $health.success -or $health.data.status -ne "ok") {
            Write-Error "Sidecar did not return a healthy FastAPI response within $TimeoutSeconds seconds."
        }

        $samples += [PSCustomObject]@{
            Attempt = $index
            StartupSeconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 4)
            HealthStatus = $health.data.status
            ProcessId = $process.Id
        }
    }
    finally {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        $listener = netstat.exe -ano -p tcp | Select-String "127.0.0.1:$Port\s+.*LISTENING" | Select-Object -First 1
        if ($listener) {
            $listenerPid = [int](($listener.ToString() -split "\s+")[-1])
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 300
        if ($null -eq $previousAppData) {
            Remove-Item Env:\APP_DATA_DIR -ErrorAction SilentlyContinue
        }
        else {
            $env:APP_DATA_DIR = $previousAppData
        }
    }
}

$startupSeconds = @($samples | ForEach-Object { $_.StartupSeconds })
$summary = [PSCustomObject]@{
    Probe = "phase10_sidecar_startup"
    SidecarPath = (Resolve-Path -LiteralPath $SidecarPath).Path
    Attempts = $Attempts
    AverageStartupSeconds = [Math]::Round(($startupSeconds | Measure-Object -Average).Average, 4)
    MaxStartupSeconds = [Math]::Round(($startupSeconds | Measure-Object -Maximum).Maximum, 4)
    TargetStartupSeconds = 5
    MeetsTarget = (($startupSeconds | Measure-Object -Maximum).Maximum -le 5)
    Samples = $samples
}

$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$summary | Format-List
