param(
    [string]$EvidencePath = ".pmk-validation/stage3d-operational-readiness.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $root "governance/stage3d_operational_readiness_contract.json"
$mainPath = Join-Path $root "processual_api/main.py"
$settingsPath = Join-Path $root "processual_api/settings.py"
$dockerfilePath = Join-Path $root "Dockerfile"

foreach ($path in @($contractPath, $mainPath, $settingsPath, $dockerfilePath)) {
    if (-not (Test-Path $path)) {
        throw "Stage 3D required file missing: $path"
    }
}

$contract = Get-Content $contractPath -Raw | ConvertFrom-Json
$main = Get-Content $mainPath -Raw
$settings = Get-Content $settingsPath -Raw
$dockerfile = Get-Content $dockerfilePath -Raw

$failures = New-Object System.Collections.Generic.List[string]

foreach ($endpoint in $contract.observability.required_endpoints) {
    if ($main -notmatch [regex]::Escape([string]$endpoint)) {
        $failures.Add("MISSING_OBSERVABILITY_ENDPOINT:$endpoint")
    }
}

foreach ($component in $contract.observability.required_runtime_components) {
    if ($main -notmatch [regex]::Escape([string]$component)) {
        $failures.Add("MISSING_RUNTIME_COMPONENT:$component")
    }
}

foreach ($page in $contract.browser_e2e.required_public_pages) {
    if ($main -notmatch [regex]::Escape([string]$page)) {
        $failures.Add("MISSING_PUBLIC_PAGE_ROUTE:$page")
    }
}
foreach ($page in $contract.browser_e2e.required_admin_pages) {
    if ($main -notmatch [regex]::Escape([string]$page)) {
        $failures.Add("MISSING_ADMIN_PAGE_ROUTE:$page")
    }
}

if ($settings -notmatch 'docs_url="/docs" if not settings\.is_production else None') {
    $failures.Add("PRODUCTION_DOCS_DISABLE_CONTRACT_MISSING")
}
if ($settings -notmatch 'CORS_ORIGINS contains wildcard') {
    $failures.Add("WILDCARD_CORS_FAIL_CLOSED_MISSING")
}
if ($settings -notmatch '_WEAK_SECRETS') {
    $failures.Add("WEAK_SECRET_POLICY_MISSING")
}

foreach ($forbidden in $contract.security.private_runtime_modules_forbidden) {
    $normalized = ([string]$forbidden).Replace("/", "\\")
    $dockerMarker = ([string]$forbidden).Replace("/", " ")
    if ($dockerfile -notmatch [regex]::Escape([string]$forbidden)) {
        $failures.Add("PRIVATE_RUNTIME_EXCLUSION_MISSING:$forbidden")
    }
}

$evidence = [ordered]@{
    schema_version = 1
    qualification = "STAGE_3D_OPERATIONAL_READINESS_PREPARATION"
    captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    contract_valid = ($failures.Count -eq 0)
    synthetic_preparation_only = $true
    real_staging_qualified = $false
    production_authority_granted = $false
    observability_contract = if ($failures | Where-Object { $_ -like "*OBSERVABILITY*" -or $_ -like "*RUNTIME_COMPONENT*" }) { "FAIL" } else { "PASS" }
    browser_route_contract = if ($failures | Where-Object { $_ -like "*PAGE_ROUTE*" }) { "FAIL" } else { "PASS" }
    security_static_contract = if ($failures | Where-Object { $_ -like "*DOCS*" -or $_ -like "*CORS*" -or $_ -like "*SECRET*" -or $_ -like "*PRIVATE_RUNTIME*" }) { "FAIL" } else { "PASS" }
    load_endurance_contract = "PREPARED_NOT_EXECUTED"
    failures = @($failures)
    remaining_real_gates = @($contract.remaining_real_gates)
}

$directory = Split-Path -Parent $EvidencePath
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$evidence | ConvertTo-Json -Depth 8 | Set-Content -Path $EvidencePath -Encoding UTF8

if ($failures.Count -gt 0) {
    throw "Stage 3D readiness contract failed: $($failures -join ', ')"
}

Write-Host "PASS: Stage 3D operational readiness preparation contract is satisfied."
Write-Host "Evidence: $EvidencePath"
Write-Host "NOTE: this is static/local preparation only; real staging qualification remains false."
