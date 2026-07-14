param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendPath = Join-Path $root "frontend"
$sidecarPath = Join-Path $frontendPath "src-tauri\binaries\fastapi-sidecar-x86_64-pc-windows-msvc.exe"
$releaseExePath = Join-Path $frontendPath "src-tauri\target\release\ai-video-pipeline-studio.exe"
$msiPath = Join-Path $frontendPath "src-tauri\target\release\bundle\msi\AI Video Pipeline Studio_0.1.0_x64_en-US.msi"
$nsisPath = Join-Path $frontendPath "src-tauri\target\release\bundle\nsis\AI Video Pipeline Studio_0.1.0_x64-setup.exe"

$artifacts = @($sidecarPath, $releaseExePath, $msiPath, $nsisPath)
foreach ($artifact in $artifacts) {
    if (-not (Test-Path -LiteralPath $artifact)) {
        Write-Error "Packaged desktop artifact is missing: $artifact"
    }
}

$existing = netstat.exe -ano -p tcp | Select-String "127.0.0.1:$Port\s+.*LISTENING"
if ($existing) {
    Write-Error "Port 127.0.0.1:$Port is already in use. Close the running desktop app or backend before package smoke, or pass -Port with a free port."
}

$process = Start-Process -FilePath $sidecarPath -ArgumentList "--host","127.0.0.1","--port",$Port -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds(25)
    $health = $null
    do {
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    } until ($health -or (Get-Date) -gt $deadline)

    if (-not $health -or -not $health.success -or $health.data.status -ne "ok") {
        Write-Error "Packaged sidecar did not return a healthy FastAPI response."
    }

    $artifactSummary = $artifacts | ForEach-Object {
        $file = Get-Item -LiteralPath $_
        [PSCustomObject]@{
            Path = $file.FullName
            SizeBytes = $file.Length
        }
    }
    $artifactSummary | Format-Table -AutoSize
    Write-Output "Packaged desktop sidecar health: $($health.data.status)"
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
