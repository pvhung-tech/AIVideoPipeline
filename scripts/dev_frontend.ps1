$ErrorActionPreference = "Stop"

$frontendPath = Join-Path $PSScriptRoot "..\frontend"

Push-Location $frontendPath
try {
    npm.cmd run dev
}
finally {
    Pop-Location
}

