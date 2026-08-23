param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$Service,
    [string]$EvidencePath = ".pmk-validation/real-staging-preflight.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-GcloudJson {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $raw = & gcloud @Arguments --format=json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: $($Arguments -join ' ')`n$raw"
    }
    return ($raw | Out-String | ConvertFrom-Json)
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is required for real staging qualification."
}

$activeAccount = (& gcloud auth list --filter=status:ACTIVE --format="value(account)" | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($activeAccount)) {
    throw "No active gcloud account is available."
}

$serviceDoc = Invoke-GcloudJson -Arguments @(
    "run", "services", "describe", $Service,
    "--project", $ProjectId,
    "--region", $Region
)

$serviceUrl = [string]$serviceDoc.status.url
$latestReadyRevision = [string]$serviceDoc.status.latestReadyRevisionName
if ([string]::IsNullOrWhiteSpace($serviceUrl) -or -not $serviceUrl.StartsWith("https://")) {
    throw "Cloud Run service URL is missing or is not HTTPS."
}
if ([string]::IsNullOrWhiteSpace($latestReadyRevision)) {
    throw "Cloud Run latest ready revision is missing."
}

$revisionDoc = Invoke-GcloudJson -Arguments @(
    "run", "revisions", "describe", $latestReadyRevision,
    "--project", $ProjectId,
    "--region", $Region
)

$containers = @($revisionDoc.spec.containers)
if ($containers.Count -ne 1) {
    throw "Qualification requires exactly one application container."
}
$image = [string]$containers[0].image
if ($image -notmatch '@sha256:[0-9a-fA-F]{64}$') {
    throw "Cloud Run revision is not pinned to an immutable sha256 image digest: $image"
}

$traffic = @($serviceDoc.status.traffic)
$latestTraffic = @($traffic | Where-Object { [string]$_.revisionName -eq $latestReadyRevision })
$trafficPercent = [int](($latestTraffic | Measure-Object -Property percent -Sum).Sum)
if ($trafficPercent -ne 100) {
    throw "Latest ready revision must receive exactly 100 percent of staging traffic. Observed: $trafficPercent"
}

$live = Invoke-RestMethod -Method Get -Uri "$serviceUrl/health/live" -TimeoutSec 30
$ready = Invoke-RestMethod -Method Get -Uri "$serviceUrl/health/ready" -TimeoutSec 30
if ([string]$live.status -ne "alive") {
    throw "Cloud Run liveness proof failed."
}
if ([string]$ready.status -ne "ready") {
    throw "Cloud Run readiness proof failed closed. Observed status: $($ready.status)"
}

$secretRefs = @()
foreach ($envItem in @($containers[0].env)) {
    if ($null -ne $envItem.valueFrom.secretKeyRef) {
        $secretRefs += [ordered]@{
            name = [string]$envItem.name
            secret = [string]$envItem.valueFrom.secretKeyRef.name
            version = [string]$envItem.valueFrom.secretKeyRef.key
        }
    }
}
if ($secretRefs.Count -eq 0) {
    throw "No Secret Manager references were found on the staging revision."
}

$evidence = [ordered]@{
    schema_version = 1
    qualification = "REAL_GCP_CLOUD_RUN_STAGING_PREFLIGHT"
    qualified = $false
    captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    active_gcloud_account = $activeAccount
    project_id = $ProjectId
    region = $Region
    service = $Service
    service_url = $serviceUrl
    latest_ready_revision = $latestReadyRevision
    image = $image
    image_digest_pinned = $true
    latest_revision_traffic_percent = $trafficPercent
    health_live = [string]$live.status
    health_ready = [string]$ready.status
    secret_manager_reference_count = $secretRefs.Count
    secret_manager_references = $secretRefs
    remaining_required_gates = @(
        "migration_rehearsal",
        "backup_restore",
        "rollback",
        "metrics_alerts",
        "external_provider_integration",
        "browser_e2e",
        "load_endurance",
        "security_review",
        "named_human_approvals",
        "signed_go_no_go"
    )
}

$directory = Split-Path -Parent $EvidencePath
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$evidence | ConvertTo-Json -Depth 8 | Set-Content -Path $EvidencePath -Encoding UTF8
Write-Host "PASS: real staging preflight evidence captured at $EvidencePath"
Write-Host "NOTE: preflight does not set RealStagingQualified=true. Remaining gates must still pass."
