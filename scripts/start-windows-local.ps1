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
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example." -ForegroundColor Yellow
    Write-Host "Open .env, replace REGISTRY_API_KEYS with a long random LOCAL-ONLY key, save it, then rerun this script."
    Start-Process notepad.exe -ArgumentList (Join-Path $repoRoot ".env")
    exit 1
}

$envText = Get-Content ".env" -Raw
if ($envText -match "(?m)^\s*REGISTRY_API_KEYS\s*=\s*(change-this-local-only-key-before-use|replace-with-a-long-random-secret)?\s*$") {
    throw "REGISTRY_API_KEYS is still a placeholder. Edit .env to use a long random local-only key, then rerun this script."
}

function Get-LocalComposePort([string]$name, [int]$defaultPort) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if (-not $value) {
        $match = [regex]::Match($envText, "(?m)^\s*$([regex]::Escape($name))\s*=\s*(\d+)\s*(?:#.*)?$")
        $value = if ($match.Success) { $match.Groups[1].Value } else { "$defaultPort" }
    }

    if ($value -notmatch '^\d{1,5}$' -or [int]$value -lt 1 -or [int]$value -gt 65535) {
        throw "$name must be a port number between 1 and 65535."
    }
    return [int]$value
}

$apiHostPort = Get-LocalComposePort "REGISTRY_API_HOST_PORT" 8002
$frontendHostPort = Get-LocalComposePort "REGISTRY_FRONTEND_HOST_PORT" 5176

Write-Host "Validating local Compose configuration..."
docker compose -f docker-compose.windows.local.yml config --quiet
if ($LASTEXITCODE -ne 0) { throw "Compose configuration validation failed." }

docker network inspect pesaguard-local_default *> $null
if ($LASTEXITCODE -ne 0) {
    docker network create pesaguard-local_default | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create the shared PesaGuard Compose network." }
}

Write-Host "Building and starting local API, worker, and dashboard..."
docker compose -f docker-compose.windows.local.yml up -d --build
if ($LASTEXITCODE -ne 0) { throw "Local stack failed to start. Inspect Docker Compose logs." }

Write-Host "Waiting for API readiness..."
$apiReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$apiHostPort/health/ready" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $apiReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $apiReady) {
    docker compose -f docker-compose.windows.local.yml ps
    docker compose -f docker-compose.windows.local.yml logs --tail 80 registry-api
    throw "API did not become ready within 120 seconds. Review the API logs above."
}

Write-Host "Waiting for dashboard HTTP response..."
$frontendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendHostPort" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { $frontendReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $frontendReady) {
    docker compose -f docker-compose.windows.local.yml ps
    docker compose -f docker-compose.windows.local.yml logs --tail 80 registry-frontend
    throw "Dashboard did not respond within 120 seconds. Review the frontend logs above."
}

docker compose -f docker-compose.windows.local.yml ps
Write-Host ""
Write-Host "Local stack passed HTTP readiness checks." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:$frontendHostPort" -ForegroundColor Green
Write-Host "API docs:  http://localhost:$apiHostPort/docs" -ForegroundColor Green
Write-Host "Liveness:  http://localhost:$apiHostPort/health/live"
Write-Host "Readiness: http://localhost:$apiHostPort/health/ready"
Write-Host "Use only the local API key from .env in the local dashboard. Never use a production key here."
Start-Process "http://localhost:$frontendHostPort"
