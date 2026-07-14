$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check_backend.ps1")
& (Join-Path $PSScriptRoot "check_frontend.ps1")

