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

if ($envText -match "(?m)^\s*DATASOURCE_ADMIN_TOKEN\s*=\s*(replace-with-a-long-random-local-operator-token|change-this-local-only-key-before-use)?\s*$") {
    throw "DATASOURCE_ADMIN_TOKEN is still a placeholder. Set a separate strong local-only operator token in .env, then rerun this script."
}

Write-Host "Validating local Compose configuration..."
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Compose configuration validation failed." }

Write-Host "Building and starting local API, worker, and dashboard..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "Local stack failed to start. Inspect Docker Compose logs." }

Write-Host "Waiting for API readiness..."
$apiReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $apiReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $apiReady) {
    docker compose ps
    docker compose logs --tail 80 registry-api
    throw "API did not become ready within 120 seconds. Review the API logs above."
}

Write-Host "Waiting for dashboard HTTP response..."
$frontendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { $frontendReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $frontendReady) {
    docker compose ps
    docker compose logs --tail 80 registry-frontend
    throw "Dashboard did not respond within 120 seconds. Review the frontend logs above."
}

docker compose ps
Write-Host ""
Write-Host "Local stack passed HTTP readiness checks." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor Green
Write-Host "API docs:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Liveness:  http://localhost:8000/health/live"
Write-Host "Readiness: http://localhost:8000/health/ready"
Write-Host "Use only the local API key from .env in the local dashboard. Never use a production key here."
Start-Process "http://localhost:5173"
