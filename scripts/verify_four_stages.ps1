[CmdletBinding()]
param(
    [string]$PythonCommand = "python",
    [string]$EvidenceDirectory = "artifacts/four-stage-verification"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([Parameter(Mandatory)][string]$Title)

    if ($env:GITHUB_ACTIONS -eq "true") {
        Write-Host "::group::$Title"
    }
    Write-Host ""
    Write-Host "=== $Title ==="
}

function Close-Section {
    if ($env:GITHUB_ACTIONS -eq "true") {
        Write-Host "::endgroup::"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList
    )

    Write-Host "> $Label"
    & $FilePath @ArgumentList
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

function Get-JUnitSummary {
    param([Parameter(Mandatory)][string]$Path)

    [xml]$document = Get-Content -LiteralPath $Path -Raw
    $suites = @()

    if ($null -ne $document.testsuites) {
        $suites = @($document.testsuites.testsuite)
    }
    elseif ($null -ne $document.testsuite) {
        $suites = @($document.testsuite)
    }

    $suites = @($suites | Where-Object { $null -ne $_ })
    if ($suites.Count -eq 0) {
        throw "Unable to read JUnit test suites from $Path"
    }

    $tests = 0
    $failures = 0
    $errors = 0
    $skipped = 0
    $timeSeconds = 0.0

    foreach ($suite in $suites) {
        $tests += [int]$suite.tests
        $failures += [int]$suite.failures
        $errors += [int]$suite.errors
        $skipped += [int]$suite.skipped
        $timeSeconds += [double]$suite.time
    }

    return [ordered]@{
        tests = $tests
        failures = $failures
        errors = $errors
        skipped = $skipped
        time_seconds = $timeSeconds
    }
}

function Assert-PathsExist {
    param(
        [Parameter(Mandatory)][string]$StageName,
        [Parameter(Mandatory)][string[]]$Paths
    )

    $missing = @($Paths | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count -gt 0) {
        throw "$StageName is missing required evidence paths: $($missing -join ', ')"
    }
}

$stages = @(
    [ordered]@{
        id = "stage1"
        name = "Stage 1 - Authority & Readiness"
        source_files = @(
            "processual_api/api_readiness.py",
            "processual_api/api_readiness_gate.py"
        )
        ruff_targets = @(
            "processual_api/api_readiness.py",
            "processual_api/api_readiness_gate.py",
            "tests/test_api_readiness_automatic_gate_b1.py",
            "tests/test_api_readiness_app_coverage_b1.py"
        )
        pytest_targets = @(
            "tests/test_api_production_readiness_gate_a3.py",
            "tests/test_api_readiness_automatic_gate_b1.py",
            "tests/test_api_readiness_app_coverage_b1.py"
        )
    },
    [ordered]@{
        id = "stage2"
        name = "Stage 2 - Commercial Authority Core"
        source_files = @(
            "processual_api/billing/assessment_plan_fulfillment.py",
            "processual_api/billing/commercial_academic_institution_authority.py",
            "processual_api/billing/commercial_catalog_contracts.py",
            "processual_api/billing/commercial_contract_registry.py",
            "processual_api/billing/commercial_state_machine.py",
            "processual_api/billing/commercial_event_contracts.py",
            "processual_api/billing/commercial_event_models.py",
            "processual_api/billing/commercial_event_repository.py",
            "processual_api/billing/commercial_top_up_transition_authority.py",
            "processual_api/billing/commercial_top_up_event_ledger.py",
            "processual_api/billing/commercial_top_up_application_service.py",
            "processual_api/billing/commercial_top_up_unit_of_work.py",
            "processual_api/billing/public_plan_journey.py"
        )
        ruff_targets = @(
            "processual_api/billing/assessment_plan_fulfillment.py",
            "processual_api/billing/commercial_academic_institution_authority.py",
            "processual_api/billing/commercial_catalog_contracts.py",
            "processual_api/billing/commercial_contract_registry.py",
            "processual_api/billing/commercial_state_machine.py",
            "processual_api/billing/commercial_event_contracts.py",
            "processual_api/billing/commercial_event_models.py",
            "processual_api/billing/commercial_event_repository.py",
            "processual_api/billing/commercial_top_up_transition_authority.py",
            "processual_api/billing/commercial_top_up_event_ledger.py",
            "processual_api/billing/commercial_top_up_application_service.py",
            "processual_api/billing/commercial_top_up_unit_of_work.py",
            "processual_api/billing/public_plan_journey.py",
            "tests/test_commercial_stage2_closure_b2.py",
            "tests/test_commercial_state_machine_b2.py",
            "tests/test_commercial_event_contracts_b2.py",
            "tests/test_commercial_event_sqlalchemy_b2.py",
            "tests/test_commercial_top_up_transition_authority_b2.py",
            "tests/test_commercial_top_up_event_ledger_b2.py",
            "tests/test_commercial_top_up_application_service_group2.py",
            "tests/test_commercial_catalog_contracts_group2.py",
            "tests/test_public_plan_journey_a3.py"
        )
        pytest_targets = @(
            "tests/test_commercial_stage2_closure_b2.py",
            "tests/test_commercial_state_machine_b2.py",
            "tests/test_commercial_event_contracts_b2.py",
            "tests/test_commercial_event_sqlalchemy_b2.py",
            "tests/test_commercial_top_up_transition_authority_b2.py",
            "tests/test_commercial_top_up_event_ledger_b2.py",
            "tests/test_commercial_top_up_order_grant_contracts_group2.py",
            "tests/test_commercial_top_up_order_grant_contracts_boundaries_group2.py",
            "tests/test_commercial_top_up_application_service_group2.py",
            "tests/test_commercial_catalog_contracts_group2.py",
            "tests/test_public_plan_journey_a3.py"
        )
    },
    [ordered]@{
        id = "stage3"
        name = "Stage 3 - Usage, Economics & Operations"
        source_files = @(
            "processual_api/billing/usage_pricing.py",
            "processual_api/billing/usage_economics.py",
            "processual_api/billing/unit_cost_assumptions.py",
            "processual_api/services/usage_log_store.py",
            "processual_api/services/client_usage_summary.py",
            "processual_api/services/customer_360.py",
            "processual_api/services/commercial_operations_read_model.py"
        )
        ruff_targets = @(
            "processual_api/billing/usage_pricing.py",
            "processual_api/billing/usage_economics.py",
            "processual_api/billing/unit_cost_assumptions.py",
            "processual_api/services/usage_log_store.py",
            "processual_api/services/client_usage_summary.py",
            "processual_api/services/customer_360.py",
            "processual_api/services/commercial_operations_read_model.py",
            "tests/test_usage_economics_stage3.py"
        )
        pytest_targets = @(
            "tests/test_usage_economics_stage3.py",
            "tests/test_client_usage_summary_service_regression.py",
            "tests/test_client_usage_summary_security_regression.py",
            "tests/test_client_usage_summary_route_regression.py",
            "tests/test_client_usage_summary_endpoint_regression.py",
            "tests/test_productization_pricing_surface_regression.py"
        )
    },
    [ordered]@{
        id = "stage4"
        name = "Stage 4 - Provider & Production Assurance"
        source_files = @(
            "processual_api/integrations/provider_production_assurance.py",
            "processual_api/integrations/provider_event_inbox.py"
        )
        ruff_targets = @(
            "processual_api/integrations/provider_production_assurance.py",
            "processual_api/integrations/provider_event_inbox.py",
            "tests/test_provider_production_assurance_stage4.py",
            "tests/test_provider_event_inbox_stage4.py",
            "tests/test_provider_assurance_hardening_stage4.py"
        )
        pytest_targets = @(
            "tests/test_provider_production_assurance_stage4.py",
            "tests/test_provider_event_inbox_stage4.py",
            "tests/test_provider_assurance_hardening_stage4.py",
            "tests/test_client_provider_connection_endpoint_regression.py",
            "tests/test_external_connectivity_r10_document_and_exports.py"
        )
    }
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null

    Write-Section "PowerShell verification environment"
    Invoke-Checked -Label "Python runtime" -FilePath $PythonCommand -ArgumentList @("--version")
    Invoke-Checked -Label "Ruff availability" -FilePath $PythonCommand -ArgumentList @("-m", "ruff", "--version")
    Invoke-Checked -Label "Pytest availability" -FilePath $PythonCommand -ArgumentList @("-m", "pytest", "--version")
    Close-Section

    $stageResults = @()
    $allPytestTargets = [System.Collections.Generic.List[string]]::new()

    foreach ($stage in $stages) {
        Write-Section $stage.name
        $requiredPaths = @($stage.source_files + $stage.ruff_targets + $stage.pytest_targets | Select-Object -Unique)
        Assert-PathsExist -StageName $stage.name -Paths $requiredPaths
        Write-Host "Evidence paths: $($requiredPaths.Count) present"

        $ruffArgs = @("-m", "ruff", "check") + $stage.ruff_targets + @("--output-format=concise")
        Invoke-Checked -Label "$($stage.name) Ruff" -FilePath $PythonCommand -ArgumentList $ruffArgs

        $junitPath = Join-Path $EvidenceDirectory "$($stage.id)-pytest.xml"
        $pytestArgs = @("-m", "pytest", "-q") + $stage.pytest_targets + @("--junitxml=$junitPath")
        Invoke-Checked -Label "$($stage.name) pytest" -FilePath $PythonCommand -ArgumentList $pytestArgs
        $pytestSummary = Get-JUnitSummary -Path $junitPath

        if ($pytestSummary.failures -ne 0 -or $pytestSummary.errors -ne 0) {
            throw "$($stage.name) reported failed or errored tests in JUnit evidence"
        }

        foreach ($testTarget in $stage.pytest_targets) {
            if (-not $allPytestTargets.Contains($testTarget)) {
                $allPytestTargets.Add($testTarget)
            }
        }

        $stageResults += [ordered]@{
            id = $stage.id
            name = $stage.name
            evidence_paths = $requiredPaths.Count
            ruff = "passed"
            pytest = $pytestSummary
            status = "passed"
        }
        Close-Section
    }

    Write-Section "Cross-stage combined regression suite"
    $combinedJunitPath = Join-Path $EvidenceDirectory "all-four-stages-pytest.xml"
    $combinedArgs = @("-m", "pytest", "-q") + $allPytestTargets.ToArray() + @("--junitxml=$combinedJunitPath")
    Invoke-Checked -Label "All four stages combined pytest" -FilePath $PythonCommand -ArgumentList $combinedArgs
    $combinedSummary = Get-JUnitSummary -Path $combinedJunitPath
    if ($combinedSummary.failures -ne 0 -or $combinedSummary.errors -ne 0) {
        throw "Combined four-stage regression suite reported failures or errors"
    }
    Close-Section

    $result = [ordered]@{
        schema_version = "2026-08-four-stage-powershell-v1"
        generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        powershell_version = $PSVersionTable.PSVersion.ToString()
        python_command = $PythonCommand
        stages = $stageResults
        combined = [ordered]@{
            unique_test_files = $allPytestTargets.Count
            pytest = $combinedSummary
            status = "passed"
        }
        overall_status = "passed"
    }

    $jsonPath = Join-Path $EvidenceDirectory "four-stage-verification.json"
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding utf8

    $markdown = @(
        "# Four-Stage PowerShell Verification",
        "",
        "Overall status: **PASSED**",
        "",
        "| Stage | Ruff | Tests | Failures | Errors | Skipped |",
        "|---|---:|---:|---:|---:|---:|"
    )
    foreach ($stageResult in $stageResults) {
        $markdown += "| $($stageResult.name) | PASS | $($stageResult.pytest.tests) | $($stageResult.pytest.failures) | $($stageResult.pytest.errors) | $($stageResult.pytest.skipped) |"
    }
    $markdown += @(
        "",
        "## Combined regression",
        "",
        "- Unique test files: $($allPytestTargets.Count)",
        "- Tests: $($combinedSummary.tests)",
        "- Failures: $($combinedSummary.failures)",
        "- Errors: $($combinedSummary.errors)",
        "- Skipped: $($combinedSummary.skipped)",
        "- Status: **PASS**"
    )

    $markdownPath = Join-Path $EvidenceDirectory "four-stage-verification.md"
    $markdown -join [Environment]::NewLine | Set-Content -LiteralPath $markdownPath -Encoding utf8

    Write-Host ""
    Write-Host "FOUR-STAGE VERIFICATION PASSED"
    Write-Host "JSON evidence: $jsonPath"
    Write-Host "Markdown evidence: $markdownPath"

    if ($env:GITHUB_STEP_SUMMARY) {
        Get-Content -LiteralPath $markdownPath -Raw | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY
    }
}
finally {
    Pop-Location
}
