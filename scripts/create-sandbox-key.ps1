$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
if (-not (Test-Path ".env")) { throw "Missing .env. Copy example.env to .env and configure local-only secrets first." }

$envMap = @{}
foreach ($line in Get-Content ".env") {
    if ($line -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
        $envMap[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}
$operatorToken = $envMap["DATASOURCE_ADMIN_TOKEN"]
if (-not $operatorToken -or $operatorToken -match 'replace-with|change-this|YOUR_') {
    throw "Set DATASOURCE_ADMIN_TOKEN to a strong local-only operator token in .env."
}
if (-not $envMap["REGISTRY_API_KEYS"] -or $envMap["REGISTRY_API_KEYS"] -match 'replace-with|change-this') {
    throw "Set REGISTRY_API_KEYS to a strong local-only API key in .env."
}

$body = @{
    name = "PesaGuard local sandbox $(Get-Date -Format 'yyyyMMdd-HHmmss')"
    environment = "sandbox"
    scopes = @("registry:read")
    expires_in_days = 90
} | ConvertTo-Json

Write-Host "Creating a registry:read sandbox key on localhost..." -ForegroundColor Cyan
$key = Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/admin/api-keys" `
    -Headers @{ Authorization = "Bearer $operatorToken" } `
    -ContentType "application/json" -Body $body -TimeoutSec 10

if (-not $key.secret -or -not $key.secret.StartsWith("pg_sandbox_")) {
    throw "The API did not return a valid sandbox key."
}
$headers = @{ "X-API-Key" = $key.secret }
try {
    $search = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/registry/search?q=sandbox" -Headers $headers -TimeoutSec 10
    $summary = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/summary" -Headers $headers -TimeoutSec 10
} catch {
    try {
        Invoke-RestMethod -Method Delete -Uri ("http://127.0.0.1:8000/api/v1/admin/api-keys/" + $key.item.id) -Headers @{ Authorization = "Bearer $operatorToken" } -TimeoutSec 10 | Out-Null
    } catch { Write-Warning "Automatic cleanup failed; revoke key id $($key.item.id) in the local API Keys page." }
    throw
}

Write-Host ""
Write-Host "SANDBOX API TEST PASSED" -ForegroundColor Green
Write-Host "Datasource: http://127.0.0.1:8000"
Write-Host "Key id: $($key.item.id)"
Write-Host "Key prefix: $($key.item.key_prefix)"
Write-Host "Search response count: $($search.count)"
Write-Host "Metrics total organizations: $($summary.total_organizations)"
Write-Host ""
Write-Host "COPY THIS SECRET NOW INTO THE PesaGuard BACKEND'S LOCAL .env ONLY:" -ForegroundColor Yellow
Write-Host $key.secret -ForegroundColor Yellow
Write-Host "Do not put this secret in React/VITE variables, Git, screenshots, or chat."
Write-Host "The key is active for 90 days. Revoke it in the local API Keys page when testing is complete."
