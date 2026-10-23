$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot
docker compose down
if ($LASTEXITCODE -ne 0) { throw "Could not stop the local stack." }
Write-Host "Local API, worker, and dashboard stopped. Persistent local test data volumes were preserved." -ForegroundColor Green
Write-Host "To also delete the local test database/uploads, run docker compose down -v"
