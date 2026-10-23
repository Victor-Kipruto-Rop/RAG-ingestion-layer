$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot
docker compose -f docker-compose.windows.local.yml down
if ($LASTEXITCODE -ne 0) { throw "Could not stop the local stack." }
Write-Host "Local API, worker, and dashboard stopped. Persistent local test data volumes were preserved." -ForegroundColor Green
Write-Host "To also delete the local test database/uploads, run docker compose -f docker-compose.windows.local.yml down -v"
