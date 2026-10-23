$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

Write-Host "PesaGuard Datasource - Supabase + R2 sandbox startup" -ForegroundColor Cyan

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
    Write-Host "Open .env and configure the Supabase sandbox URL, private R2 sandbox bucket/credentials, a random sandbox API key, and CONFIRM_SANDBOX_TARGET=YES. Save and rerun this script."
    Start-Process notepad.exe -ArgumentList (Join-Path $repoRoot ".env")
    exit 1
}

$envText = Get-Content ".env" -Raw
function Get-EnvValue([string]$name) {
    $match = [regex]::Match($envText, "(?m)^\s*" + [regex]::Escape($name) + "\s*=\s*(.*?)\s*$")
    if (-not $match.Success) { return "" }
    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}
$required = @("DATABASE_URL", "REGISTRY_API_KEYS", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace((Get-EnvValue $name))) { throw "$name is required in .env." }
}
if ((Get-EnvValue "DATABASE_URL") -notmatch "^postgres(ql)?://") {
    throw "DATABASE_URL must be the Supabase PostgreSQL connection string, not SQLite."
}
if ((Get-EnvValue "APP_ENV") -ne "development" -or (Get-EnvValue "DATASOURCE_ENVIRONMENT") -ne "sandbox") {
    throw "For this local stack, set APP_ENV=development and DATASOURCE_ENVIRONMENT=sandbox."
}
if ((Get-EnvValue "CONFIRM_SANDBOX_TARGET") -ne "YES") {
    throw "After confirming the Supabase project and R2 bucket are dedicated sandbox resources, set CONFIRM_SANDBOX_TARGET=YES."
}
if ((Get-EnvValue "REGISTRY_API_KEYS") -match "replace-with|change-this|example|placeholder") {
    throw "REGISTRY_API_KEYS is still a placeholder. Set a long random sandbox-only key."
}

Write-Host "Validating local Compose configuration..."
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Compose configuration validation failed." }

Write-Host "Building and starting local API, worker, and dashboard. The worker can write to the configured Supabase and R2 sandbox resources..."
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
