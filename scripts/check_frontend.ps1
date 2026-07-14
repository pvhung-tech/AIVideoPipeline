$ErrorActionPreference = "Stop"

$frontendPath = Join-Path $PSScriptRoot "..\frontend"

Push-Location $frontendPath
try {
    npm.cmd run test
    npm.cmd run build
}
finally {
    Pop-Location
}

