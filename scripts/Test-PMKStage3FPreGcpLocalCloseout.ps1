param(
    [string]$EvidencePath = ".pmk-validation/stage3f-pre-gcp-local-closeout.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

try {
    $contractPath = "governance/stage3f_pre_gcp_local_closeout_contract.json"
    $statusPath = "governance/repository_closeout_status.json"
    foreach ($path in @($contractPath, $statusPath, "scripts/Invoke-PMKStage3ERealStagingHandoff.ps1")) {
        if (-not (Test-Path $path)) {
            throw "Stage 3F required file missing: $path"
        }
    }

    $contract = Get-Content $contractPath -Raw | ConvertFrom-Json
    $status = Get-Content $statusPath -Raw | ConvertFrom-Json
    $failures = New-Object System.Collections.Generic.List[string]

    foreach ($property in $contract.required_repository_status.PSObject.Properties) {
        $stageName = $property.Name
        $allowed = @($property.Value)
        $stage = $status.phase_c_real_staging.$stageName
        if ($null -eq $stage) {
            $failures.Add("MISSING_STAGE_STATUS:$stageName")
            continue
        }
        if ($allowed -notcontains [string]$stage.status) {
            $failures.Add("STAGE_NOT_CLOSED:${stageName}:$($stage.status)")
        }
    }

    foreach ($path in $contract.required_local_evidence) {
        if (-not (Test-Path ([string]$path))) {
            $failures.Add("MISSING_LOCAL_EVIDENCE:$path")
        }
    }

    if ($status.authority.real_staging_qualified -ne $false) {
        $failures.Add("REAL_STAGING_AUTHORITY_MUST_REMAIN_FALSE")
    }
    if ($status.authority.production_authority_granted -ne $false) {
        $failures.Add("PRODUCTION_AUTHORITY_MUST_REMAIN_FALSE")
    }
    if ($status.launch_authority.commercial_launch -ne "NO_GO") {
        $failures.Add("COMMERCIAL_LAUNCH_MUST_REMAIN_NO_GO")
    }

    $gitignore = Get-Content ".gitignore" -Raw
    $dockerignore = Get-Content ".dockerignore" -Raw
    if ($gitignore -notmatch '(?m)^\.pmk-validation/\r?$') {
        $failures.Add("PMK_VALIDATION_NOT_GIT_IGNORED")
    }
    if ($dockerignore -notmatch '(?m)^\.pmk-validation\r?$') {
        $failures.Add("PMK_VALIDATION_NOT_DOCKER_IGNORED")
    }
    if ($dockerignore -notmatch '(?m)^\.env\.\*\r?$') {
        $failures.Add("ENV_VARIANTS_NOT_DOCKER_IGNORED")
    }

    $evidenceDirectory = Split-Path -Parent $EvidencePath
    if (-not [string]::IsNullOrWhiteSpace($evidenceDirectory)) {
        New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
    }

    $evidence = [ordered]@{
        schema_version = 1
        qualification = "STAGE_3F_PRE_GCP_FINAL_LOCAL_CLOSEOUT"
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        local_closeout_pass = ($failures.Count -eq 0)
        failures = @($failures)
        secret_values_recorded = $false
        real_staging_qualified = $false
        production_authority_granted = $false
        commercial_launch = "NO_GO"
        external_blockers_only = @($contract.external_blockers_only)
    }
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -Path $EvidencePath -Encoding UTF8

    if ($failures.Count -gt 0) {
        throw "Stage 3F local closeout failed: $($failures -join ', ')"
    }

    Write-Host "PASS: Stage 3F pre-GCP local closeout is satisfied."
    Write-Host "Evidence: $EvidencePath"
    Write-Host "NOTE: all remaining blockers are external/real-staging gates; production authority remains false."
}
finally {
    Pop-Location
}
