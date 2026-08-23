param(
    [string]$EvidencePath = ".pmk-validation/lemon-squeezy-provider-preflight.json"
)

$ErrorActionPreference = "Stop"

function Add-Failure {
    param([System.Collections.Generic.List[string]]$Failures, [string]$Code)
    if (-not $Failures.Contains($Code)) { [void]$Failures.Add($Code) }
}

$failures = New-Object 'System.Collections.Generic.List[string]'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $repoRoot "governance/lemon_squeezy_provider_qualification_contract.json"

if (-not (Test-Path $contractPath)) {
    throw "Lemon Squeezy provider qualification contract is missing."
}

$contract = Get-Content -Raw $contractPath | ConvertFrom-Json
if ($contract.provider -ne "lemon_squeezy") { Add-Failure $failures "PROVIDER_CONTRACT_MISMATCH" }
if ($contract.secrets_recorded -ne $false) { Add-Failure $failures "SECRET_RECORDING_FORBIDDEN" }
if ($contract.real_provider_qualified -ne $false) { Add-Failure $failures "REAL_PROVIDER_AUTHORITY_MUST_START_FALSE" }

$requiredSources = @($contract.required_repository_contracts)
foreach ($relativePath in $requiredSources) {
    if (-not (Test-Path (Join-Path $repoRoot $relativePath))) {
        Add-Failure $failures ("MISSING_SOURCE_CONTRACT:" + $relativePath)
    }
}

$apiKey = [Environment]::GetEnvironmentVariable("LEMONSQUEEZY_API_KEY")
$webhookSecret = [Environment]::GetEnvironmentVariable("LEMONSQUEEZY_WEBHOOK_SECRET")
$storeId = [Environment]::GetEnvironmentVariable("LEMONSQUEEZY_STORE_ID")

if ([string]::IsNullOrWhiteSpace($apiKey)) { Add-Failure $failures "MISSING_LEMONSQUEEZY_API_KEY" }
if ([string]::IsNullOrWhiteSpace($webhookSecret) -or $webhookSecret.Trim().Length -lt 32) {
    Add-Failure $failures "MISSING_OR_WEAK_LEMONSQUEEZY_WEBHOOK_SECRET"
}
if ([string]::IsNullOrWhiteSpace($storeId) -or $storeId -notmatch '^[1-9][0-9]*$') {
    Add-Failure $failures "INVALID_LEMONSQUEEZY_STORE_ID"
}

$evidenceDir = Split-Path -Parent $EvidencePath
if ($evidenceDir) { New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null }

$evidence = [ordered]@{
    schema_version = 1
    qualification = "LEMON_SQUEEZY_PROVIDER_PREFLIGHT"
    checked_at_utc = [DateTime]::UtcNow.ToString("o")
    repository_contracts_present = ($failures | Where-Object { $_ -like 'MISSING_SOURCE_CONTRACT:*' }).Count -eq 0
    api_key_present = -not [string]::IsNullOrWhiteSpace($apiKey)
    webhook_secret_present_and_minimum_length = (-not [string]::IsNullOrWhiteSpace($webhookSecret) -and $webhookSecret.Trim().Length -ge 32)
    store_id_valid = (-not [string]::IsNullOrWhiteSpace($storeId) -and $storeId -match '^[1-9][0-9]*$')
    secret_values_recorded = $false
    failures = @($failures)
    preflight_pass = ($failures.Count -eq 0)
    real_provider_qualified = $false
    real_staging_qualified = $false
    production_authority_granted = $false
    commercial_launch = "NO_GO"
    next_action = "Execute authenticated Lemon Squeezy test-mode checkout and signed webhook E2E; retain external evidence without storing secret values."
}

$evidence | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $EvidencePath

if ($failures.Count -gt 0) {
    Write-Host "FAIL: Lemon Squeezy provider preflight is not ready."
    foreach ($failure in $failures) { Write-Host (" - " + $failure) }
    Write-Host ("Evidence: " + $EvidencePath)
    exit 1
}

Write-Host "PASS: Lemon Squeezy provider preflight is ready for real test-mode execution."
Write-Host ("Evidence: " + $EvidencePath)
Write-Host "NOTE: this does not qualify the external provider or grant launch authority."
