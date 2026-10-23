$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

Write-Host "PesaGuard Datasource - safe Windows local startup" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Install Docker Desktop, open it, then rerun this script."
}

try {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker engine unavailable" }
} catch {
    throw "Docker Desktop is not running yet. Start Docker Desktop, wait for it to become ready, and rerun this script."
}

if (-not (Test-Path ".env")) {
    Copy-Item "example.env" ".env"
    Write-Host "Created .env from example.env." -ForegroundColor Yellow
    Write-Host "Open .env, replace REGISTRY_API_KEYS with a long random LOCAL-ONLY key, save it, then rerun this script."
    Start-Process notepad.exe -ArgumentList (Join-Path $repoRoot ".env")
    exit 1
}

$envText = Get-Content ".env" -Raw
if ($envText -match "(?m)^\s*REGISTRY_API_KEYS\s*=\s*(change-this-local-only-key-before-use|replace-with-a-long-random-secret)?\s*$") {
    throw "REGISTRY_API_KEYS is still a placeholder. Edit .env to use a long random local-only key, then rerun this script."
}

Write-Host "Validating local Compose configuration..."
docker compose -f docker-compose.windows.local.yml config --quiet
if ($LASTEXITCODE -ne 0) { throw "Compose configuration validation failed." }

Write-Host "Building and starting local API, worker, and dashboard..."
docker compose -f docker-compose.windows.local.yml up -d --build
if ($LASTEXITCODE -ne 0) { throw "Local stack failed to start. Inspect Docker Compose logs." }

docker compose -f docker-compose.windows.local.yml ps
Write-Host ""
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor Green
Write-Host "API docs:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Use only the local API key from .env in the local dashboard. Never use a production key here."
Start-Process "http://localhost:5173"
