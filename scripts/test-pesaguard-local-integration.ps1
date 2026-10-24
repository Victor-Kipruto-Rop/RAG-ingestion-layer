[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = $env:PESAGUARD_DATASOURCE_API_KEY,
    [string]$TestRegistrationNumber = "LOCAL-INTEGRATION-NOT-A-REAL-REGISTRATION"
)

$ErrorActionPreference = "Stop"
$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")

function Invoke-LocalGet {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [hashtable]$Headers = @{}
    )

    return Invoke-WebRequest -Uri $Uri -Method Get -Headers $Headers -TimeoutSec 8 -UseBasicParsing
}

function Assert-Status {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)][int]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ([int]$Response.StatusCode -ne $Expected) {
        throw "$Label expected HTTP $Expected but got HTTP $($Response.StatusCode)."
    }
    Write-Host "[PASS] $Label (HTTP $Expected)"
}

Write-Host "PesaGuard datasource local integration smoke test"
Write-Host "Target: $ApiBaseUrl"
Write-Host "No records are created or modified by this test."

foreach ($path in @("/health/live", "/health/ready")) {
    $response = Invoke-LocalGet -Uri "$ApiBaseUrl$path"
    if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -ge 300) {
        throw "$path did not return a successful status."
    }
    Write-Host "[PASS] $path (HTTP $($response.StatusCode))"
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "Set PESAGUARD_DATASOURCE_API_KEY to the local-only REGISTRY_API_KEYS value. The key is never printed."
}

$lookupUri = "$ApiBaseUrl/api/v1/registry/lookup?reg_no=$([uri]::EscapeDataString($TestRegistrationNumber))"

# Confirm unauthenticated requests are rejected. Do not print response bodies.
try {
    $unauthenticated = Invoke-LocalGet -Uri $lookupUri
    if ([int]$unauthenticated.StatusCode -lt 400) {
        throw "Unauthenticated registry lookup unexpectedly succeeded (HTTP $($unauthenticated.StatusCode))."
    }
    Write-Host "[PASS] Unauthenticated lookup rejected (HTTP $($unauthenticated.StatusCode))"
}
catch {
    $statusCode = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }
    if ($null -eq $statusCode) {
        throw "Could not verify unauthenticated lookup rejection: $($_.Exception.Message)"
    }
    if ($statusCode -lt 400) {
        throw "Unauthenticated registry lookup unexpectedly succeeded."
    }
    Write-Host "[PASS] Unauthenticated lookup rejected (HTTP $statusCode)"
}

$authenticated = Invoke-LocalGet -Uri $lookupUri -Headers @{ "X-API-Key" = $ApiKey }
Assert-Status -Response $authenticated -Expected 200 -Label "Authenticated registry lookup"

try {
    $payload = $authenticated.Content | ConvertFrom-Json
}
catch {
    throw "Authenticated lookup did not return valid JSON."
}

if ($null -eq $payload.PSObject.Properties["found"]) {
    throw "Lookup response is missing the required 'found' field."
}

if ($payload.found -eq $true -and $null -eq $payload.PSObject.Properties["organization"]) {
    throw "Lookup reports found=true but does not include an organization object."
}

if ($payload.found -eq $false) {
    Write-Host "[PASS] Unknown fictional identifier returned found=false (not a verification decision)"
}
elseif ($payload.found -eq $true) {
    Write-Host "[PASS] Lookup response includes an organization record; review its provenance and data-quality status before use"
}
else {
    throw "Lookup response 'found' field must be a boolean."
}

Write-Host ""
Write-Host "Local datasource smoke test passed."
Write-Host "This does not prove PesaGuard-to-datasource end-to-end integration or BRS/KRA connectivity."
