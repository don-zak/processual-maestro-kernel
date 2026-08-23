param(
    [ValidateSet("Prepare", "RealGcp")][string]$Mode = "Prepare",
    [string]$ProjectId,
    [string]$Region,
    [string]$Service,
    [switch]$ValidateRuntimeEnvironment,
    [string]$EvidencePath = ".pmk-validation/stage3e-real-staging-handoff.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

try {
    $contractPath = "governance/stage3e_real_staging_handoff_contract.json"
    if (-not (Test-Path $contractPath)) {
        throw "Stage 3E contract missing: $contractPath"
    }
    $contract = Get-Content $contractPath -Raw | ConvertFrom-Json
    $failures = New-Object System.Collections.Generic.List[string]

    foreach ($path in $contract.required_local_evidence) {
        if (-not (Test-Path ([string]$path))) {
            $failures.Add("MISSING_LOCAL_EVIDENCE:$path")
            continue
        }
        $item = Get-Content ([string]$path) -Raw | ConvertFrom-Json
        if ($item.qualification -ne "STAGE_3B_DATABASE_RECOVERY_REHEARSAL") {
            $failures.Add("INVALID_STAGE3B_EVIDENCE:$path")
        }
        if ($item.migration_rehearsal -ne "PASS" -or $item.restore_verification -ne "PASS" -or $item.rollback_to_snapshot -ne "PASS") {
            $failures.Add("INCOMPLETE_STAGE3B_EVIDENCE:$path")
        }
        if ($item.real_staging_qualified -ne $false) {
            $failures.Add("LOCAL_EVIDENCE_AUTHORITY_BOUNDARY_BROKEN:$path")
        }
    }

    & "$PSScriptRoot/Test-PMKStage3DOperationalReadiness.ps1"
    if ($LASTEXITCODE -ne 0) {
        $failures.Add("STAGE3D_VALIDATOR_FAILED")
    }

    $runtimeValidation = "NOT_REQUESTED"
    if ($ValidateRuntimeEnvironment) {
        & "$PSScriptRoot/Test-PMKStagingRuntimeContract.ps1"
        if ($LASTEXITCODE -ne 0) {
            $failures.Add("STAGE3C_RUNTIME_VALIDATOR_FAILED")
            $runtimeValidation = "FAIL"
        } else {
            $runtimeValidation = "PASS"
        }
    }

    $realPreflight = "NOT_EXECUTED"
    if ($Mode -eq "RealGcp") {
        foreach ($pair in @(
            @{ Name = "ProjectId"; Value = $ProjectId },
            @{ Name = "Region"; Value = $Region },
            @{ Name = "Service"; Value = $Service }
        )) {
            if ([string]::IsNullOrWhiteSpace([string]$pair.Value)) {
                $failures.Add("MISSING_REAL_TARGET:$($pair.Name)")
            }
        }

        if ($failures.Count -eq 0) {
            & "$PSScriptRoot/Invoke-PMKRealStagingPreflight.ps1" `
                -ProjectId $ProjectId `
                -Region $Region `
                -Service $Service
            if ($LASTEXITCODE -ne 0) {
                $failures.Add("REAL_GCP_PREFLIGHT_FAILED")
                $realPreflight = "FAIL"
            } else {
                $realPreflight = "PASS_NON_AUTHORITATIVE_PREFLIGHT"
            }
        }
    }

    $evidenceDirectory = Split-Path -Parent $EvidencePath
    if (-not [string]::IsNullOrWhiteSpace($evidenceDirectory)) {
        New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
    }

    $evidence = [ordered]@{
        schema_version = 1
        qualification = "STAGE_3E_REAL_STAGING_EXECUTION_HANDOFF"
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        mode = $Mode
        local_prepare_pass = ($failures.Count -eq 0)
        runtime_environment_validation = $runtimeValidation
        real_gcp_preflight = $realPreflight
        secret_values_recorded = $false
        target_project_recorded = if ($Mode -eq "RealGcp") { -not [string]::IsNullOrWhiteSpace($ProjectId) } else { $false }
        target_region_recorded = if ($Mode -eq "RealGcp") { -not [string]::IsNullOrWhiteSpace($Region) } else { $false }
        target_service_recorded = if ($Mode -eq "RealGcp") { -not [string]::IsNullOrWhiteSpace($Service) } else { $false }
        failures = @($failures)
        real_staging_qualified = $false
        production_authority_granted = $false
        remaining_real_gates = @($contract.remaining_after_real_preflight)
    }
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -Path $EvidencePath -Encoding UTF8

    if ($failures.Count -gt 0) {
        throw "Stage 3E handoff failed closed: $($failures -join ', ')"
    }

    Write-Host "PASS: Stage 3E $Mode handoff checks completed."
    Write-Host "Evidence: $EvidencePath"
    if ($Mode -eq "Prepare") {
        Write-Host "NOTE: prepare mode requires no GCP and does not qualify real staging."
    } else {
        Write-Host "NOTE: real GCP preflight alone does not qualify real staging; remaining gates are preserved."
    }
}
finally {
    Pop-Location
}
