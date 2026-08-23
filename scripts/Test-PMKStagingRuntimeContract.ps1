param(
    [string]$ContractPath = "governance/staging_runtime_contract.json",
    [string]$EvidencePath = ".pmk-validation/stage3c-runtime-contract.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

try {
    if (-not (Test-Path $ContractPath)) {
        throw "Staging runtime contract not found: $ContractPath"
    }

    $contract = Get-Content -Raw -Path $ContractPath | ConvertFrom-Json
    $forbidden = @{}
    foreach ($value in $contract.forbidden_values_case_insensitive) {
        $forbidden[$value.ToString().ToLowerInvariant()] = $true
    }

    $failures = New-Object System.Collections.Generic.List[string]
    $checked = New-Object System.Collections.Generic.List[string]

    foreach ($name in $contract.required_secret_env) {
        $value = [Environment]::GetEnvironmentVariable($name)
        $checked.Add($name)
        if ([string]::IsNullOrWhiteSpace($value)) {
            $failures.Add("MISSING_SECRET:$name")
            continue
        }
        if ($forbidden.ContainsKey($value.Trim().ToLowerInvariant())) {
            $failures.Add("WEAK_SECRET:$name")
        }
    }

    foreach ($name in $contract.required_non_secret_env) {
        $value = [Environment]::GetEnvironmentVariable($name)
        $checked.Add($name)
        if ([string]::IsNullOrWhiteSpace($value)) {
            $failures.Add("MISSING_CONFIG:$name")
        }
    }

    foreach ($property in $contract.environment_contract.PSObject.Properties) {
        $name = $property.Name
        $expected = $property.Value.ToString()
        $actual = [Environment]::GetEnvironmentVariable($name)
        $checked.Add($name)
        if ($actual -ne $expected) {
            $failures.Add("CONFIG_MISMATCH:$name")
        }
    }

    $cors = [Environment]::GetEnvironmentVariable("CORS_ORIGINS")
    if (-not [string]::IsNullOrWhiteSpace($cors)) {
        $origins = @($cors.Split(",") | ForEach-Object { $_.Trim() })
        foreach ($forbiddenOrigin in $contract.forbidden_cors_origins) {
            if ($origins -contains $forbiddenOrigin) {
                $failures.Add("FORBIDDEN_CORS:$forbiddenOrigin")
            }
        }
    }

    $evidenceDirectory = Split-Path -Parent $EvidencePath
    if (-not [string]::IsNullOrWhiteSpace($evidenceDirectory)) {
        New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
    }

    $evidence = [ordered]@{
        schema_version = 1
        qualification = "STAGE_3C_STAGING_RUNTIME_CONTRACT"
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        contract_path = $ContractPath
        checked_variable_names = @($checked | Sort-Object -Unique)
        secret_values_recorded = $false
        failure_count = $failures.Count
        failures = @($failures)
        contract_pass = ($failures.Count -eq 0)
        real_staging_qualified = $false
        production_authority_granted = $false
    }

    $evidence | ConvertTo-Json -Depth 6 | Set-Content -Path $EvidencePath -Encoding UTF8

    if ($failures.Count -gt 0) {
        Write-Host "FAIL: Stage 3C runtime contract has $($failures.Count) issue(s)."
        foreach ($failure in $failures) {
            Write-Host " - $failure"
        }
        Write-Host "Evidence: $EvidencePath"
        exit 1
    }

    Write-Host "PASS: Stage 3C runtime contract is satisfied by the current process environment."
    Write-Host "Evidence: $EvidencePath"
    Write-Host "NOTE: no secret values were written to evidence and RealStagingQualified remains false."
}
finally {
    Pop-Location
}
