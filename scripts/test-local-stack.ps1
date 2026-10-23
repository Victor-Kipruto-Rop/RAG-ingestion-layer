$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

if (-not (Test-Path ".env")) {
    throw "Missing .env. Copy example.env, configure Supabase and R2 sandbox credentials, then explicitly confirm the sandbox target."
}

$keyLine = Get-Content ".env" | Where-Object { $_ -match "^\s*REGISTRY_API_KEYS\s*=" } | Select-Object -First 1
if (-not $keyLine) { throw "REGISTRY_API_KEYS is missing from .env." }
$apiKey = ($keyLine -replace "^\s*REGISTRY_API_KEYS\s*=", "").Split(",")[0].Trim()
if (-not $apiKey -or $apiKey -match "replace-with|change-this|example|placeholder") {
    throw "Set REGISTRY_API_KEYS to a long random sandbox-only key before testing."
}
$envText = Get-Content ".env" -Raw
function Get-EnvValue([string]$name) {
    $match = [regex]::Match($envText, "(?m)^\s*" + [regex]::Escape($name) + "\s*=\s*(.*?)\s*$")
    if (-not $match.Success) { return "" }
    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}
if ((Get-EnvValue "CONFIRM_SANDBOX_TARGET") -ne "YES" -or (Get-EnvValue "DATASOURCE_ENVIRONMENT") -ne "sandbox") {
    throw "Smoke tests write to the configured database and bucket. Confirm dedicated sandbox resources in .env first."
}

Write-Host "Checking API readiness..." -ForegroundColor Cyan
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 5 | Out-Null
$headers = @{ "X-API-Key" = $apiKey }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/summary" -Headers $headers -TimeoutSec 10 | Out-Null

$samplePath = Join-Path $repoRoot "samples/test-organizations.csv"
if (-not (Test-Path $samplePath)) { throw "Fictional CSV fixture not found: $samplePath" }
$responsePath = Join-Path ([System.IO.Path]::GetTempPath()) ("pesaguard-upload-" + [guid]::NewGuid().ToString("N") + ".json")
try {
    $httpCode = & curl.exe -sS -o $responsePath -w "%{http_code}" -H "X-API-Key: $apiKey" -F "file=@$samplePath;type=text/csv" "http://127.0.0.1:8000/api/v1/ingestion/uploads"
    if ($LASTEXITCODE -ne 0 -or $httpCode -ne "202") {
        $body = if (Test-Path $responsePath) { Get-Content $responsePath -Raw } else { "" }
        throw "CSV upload failed (HTTP $httpCode): $body"
    }
    $upload = Get-Content $responsePath -Raw | ConvertFrom-Json
    if (-not $upload.job_id) { throw "Upload response did not include a job_id." }
} finally {
    Remove-Item $responsePath -Force -ErrorAction SilentlyContinue
}

Write-Host "Waiting for ingestion worker to process job $($upload.job_id)..." -ForegroundColor Cyan
$job = $null
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $jobs = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/ingestion/jobs?page=1&page_size=100" -Headers $headers -TimeoutSec 10
    $job = $jobs.items | Where-Object { $_.id -eq $upload.job_id } | Select-Object -First 1
    if ($job -and $job.status -in @("COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "NEEDS_PDF_PROCESSING")) { break }
    Start-Sleep -Seconds 2
}
if (-not $job) { throw "Worker job was not returned by the API." }
if ($job.status -notin @("COMPLETED", "COMPLETED_WITH_ERRORS")) {
    docker compose logs --tail 80 registry-worker
    throw "Worker did not complete the CSV test. Final status: $($job.status). Error: $($job.error_summary)"
}
if ([int]$job.records_processed -lt 1) { throw "The worker completed without processing any CSV rows." }

Write-Host ""
Write-Host "SUPABASE + R2 SANDBOX END-TO-END TEST PASSED" -ForegroundColor Green
Write-Host "API and frontend containers: use 'docker compose ps' to inspect."
Write-Host "Job: $($job.id) | Status: $($job.status) | Processed rows: $($job.records_processed)"
Write-Host "Dashboard: http://localhost:5173"
Write-Host "API docs:  http://localhost:8000/docs"
