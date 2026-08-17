[CmdletBinding()]
param(
    [string]$PythonCommand = "python",
    [string]$EvidenceDirectory = "artifacts/customer-billing-comprehensive-verification",
    [switch]$SkipInstall,
    [switch]$SkipFullProgram
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList
    )

    Write-Host ""
    Write-Host "=== $Label ==="
    & $FilePath @ArgumentList
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

function Get-JUnitSummary {
    param([Parameter(Mandatory)][string]$Path)

    [xml]$document = Get-Content -LiteralPath $Path -Raw
    $suiteNodes = @()
    if ($null -ne $document.testsuites) {
        $suiteNodes = @($document.testsuites.testsuite)
    }
    elseif ($null -ne $document.testsuite) {
        $suiteNodes = @($document.testsuite)
    }
    if ($suiteNodes.Count -eq 0) {
        throw "Unable to read JUnit test suites from $Path"
    }

    $tests = 0
    $failures = 0
    $errors = 0
    $skipped = 0
    $timeSeconds = 0.0
    foreach ($suite in $suiteNodes) {
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
        time_seconds = [Math]::Round($timeSeconds, 3)
    }
}

function Assert-TestFilesExist {
    param([Parameter(Mandatory)][string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required verification test is missing: $path"
        }
    }
}

function Invoke-PytestPhase {
    param(
        [Parameter(Mandatory)][string]$PhaseId,
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$Tests,
        [Parameter(Mandatory)][string]$EvidenceDirectory,
        [Parameter(Mandatory)][string]$PythonCommand
    )

    Assert-TestFilesExist -Paths $Tests
    $junitPath = Join-Path $EvidenceDirectory "$PhaseId.xml"
    $logPath = Join-Path $EvidenceDirectory "$PhaseId.log"

    Write-Host ""
    Write-Host "=== $Label ==="
    & $PythonCommand -m pytest @Tests -ra --junitxml=$junitPath 2>&1 |
        Tee-Object -FilePath $logPath |
        Out-Host
    $exitCode = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $junitPath -PathType Leaf)) {
        throw "$Label did not produce JUnit evidence at $junitPath"
    }

    $summary = Get-JUnitSummary -Path $junitPath
    $status = if ($exitCode -eq 0 -and $summary.failures -eq 0 -and $summary.errors -eq 0) { "passed" } else { "failed" }
    $result = [ordered]@{
        phase_id = $PhaseId
        label = $Label
        status = $status
        pytest_exit_code = $exitCode
        pytest = $summary
        tests = $Tests
        junit = $junitPath
        log = $logPath
    }

    $phaseJsonPath = Join-Path $EvidenceDirectory "$PhaseId.json"
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $phaseJsonPath -Encoding utf8

    if ($status -ne "passed") {
        throw "$Label failed. Inspect $logPath"
    }

    return $result
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null

    Write-Host "Repository: $repoRoot"
    Write-Host "PowerShell: $($PSVersionTable.PSVersion)"
    Invoke-Checked -Label "Python runtime" -FilePath $PythonCommand -ArgumentList @("--version")

    if (-not $SkipInstall) {
        Invoke-Checked -Label "Upgrade pip" -FilePath $PythonCommand -ArgumentList @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked -Label "Install full verification dependencies" -FilePath $PythonCommand -ArgumentList @(
            "-m", "pip", "install", ".[dev,api,observability,security,database,cache,reports,llm]"
        )
    }

    Invoke-Checked -Label "Pytest availability" -FilePath $PythonCommand -ArgumentList @("-m", "pytest", "--version")

    $billingContractTests = @(
        "tests/test_customer_billing_statements.py",
        "tests/test_customer_billing_statement_gateways.py",
        "tests/test_customer_billing_statement_readiness.py",
        "tests/test_customer_billing_statements_ui.py"
    )

    $commercialRegressionTests = @(
        "tests/test_maestro_units_commercial_authority.py",
        "tests/test_pricing_unit_quota_enforcement_regression.py",
        "tests/test_byok_usage_pricing.py",
        "tests/test_client_usage_summary_service_regression.py",
        "tests/test_client_usage_summary_route_regression.py",
        "tests/test_client_usage_summary_ui_regression.py",
        "tests/test_enterprise_integration_capability_contract.py"
    )

    $topUpLifecycleTests = @(
        "tests/test_subscription_top_up_order_a3.py",
        "tests/test_subscription_top_up_eligibility_a3.py",
        "tests/test_subscription_top_up_purchase_router_a3.py",
        "tests/test_subscription_top_up_grant_a3.py",
        "tests/test_subscription_top_up_reversal_a3.py"
    )

    $boundaryRegressionTests = @(
        "tests/test_api_readiness_automatic_gate_b1.py",
        "tests/test_api_readiness_app_coverage_b1.py",
        "tests/test_settings_runtime_wiring_regression.py",
        "tests/test_settings_enterprise_integration_runtime.py",
        "tests/test_admin_subscription_analytics_ui.py",
        "tests/test_admin_subscription_analytics_regression.py",
        "tests/test_canonical_checkout_gate_a3.py",
        "tests/test_canonical_checkout_resolution_a3.py",
        "tests/test_canonical_checkout_route_a3.py",
        "tests/test_subscription_catalog_runtime_boundary_a3.py"
    )

    $phaseResults = @()
    $phaseResults += Invoke-PytestPhase -PhaseId "01-billing-contract" -Label "Customer billing contract and gateways" -Tests $billingContractTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phaseResults += Invoke-PytestPhase -PhaseId "02-commercial-regressions" -Label "Maestro Units, quota, plan, and usage regressions" -Tests $commercialRegressionTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phaseResults += Invoke-PytestPhase -PhaseId "03-topup-lifecycle" -Label "Top-up purchase, grant, and reversal lifecycle" -Tests $topUpLifecycleTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phaseResults += Invoke-PytestPhase -PhaseId "04-boundary-regressions" -Label "API readiness, Settings, admin UI, and canonical billing boundaries" -Tests $boundaryRegressionTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand

    $fullProgram = $null
    if (-not $SkipFullProgram) {
        $fullEvidence = Join-Path $EvidenceDirectory "full-program"
        $fullScript = Join-Path $PSScriptRoot "verify_full_program_local.ps1"
        if (-not (Test-Path -LiteralPath $fullScript -PathType Leaf)) {
            throw "Full-program verification script is missing: $fullScript"
        }

        Write-Host ""
        Write-Host "=== Full program PowerShell acceptance ==="
        & $fullScript -PythonCommand $PythonCommand -EvidenceDirectory $fullEvidence -SkipInstall
        if ($LASTEXITCODE -ne 0) {
            throw "Full program verification failed with exit code $LASTEXITCODE"
        }

        $fullJson = Join-Path $fullEvidence "full-program-verification.json"
        if (-not (Test-Path -LiteralPath $fullJson -PathType Leaf)) {
            throw "Full program verification did not produce $fullJson"
        }
        $fullProgram = Get-Content -LiteralPath $fullJson -Raw | ConvertFrom-Json
        if ($fullProgram.overall_status -ne "passed") {
            throw "Full program verification result is not passed"
        }
    }

    $focusedTests = 0
    $focusedFailures = 0
    $focusedErrors = 0
    $focusedSkipped = 0
    foreach ($phase in $phaseResults) {
        $focusedTests += [int]$phase.pytest.tests
        $focusedFailures += [int]$phase.pytest.failures
        $focusedErrors += [int]$phase.pytest.errors
        $focusedSkipped += [int]$phase.pytest.skipped
    }

    $overallPassed = (
        $focusedFailures -eq 0 -and
        $focusedErrors -eq 0 -and
        ($SkipFullProgram -or $fullProgram.overall_status -eq "passed")
    )

    $result = [ordered]@{
        schema_version = "2026-08-customer-billing-comprehensive-powershell-v1"
        generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        repository_root = $repoRoot
        powershell_version = $PSVersionTable.PSVersion.ToString()
        python_command = $PythonCommand
        focused = [ordered]@{
            tests = $focusedTests
            failures = $focusedFailures
            errors = $focusedErrors
            skipped = $focusedSkipped
            phases = $phaseResults
        }
        full_program = $fullProgram
        overall_status = if ($overallPassed) { "passed" } else { "failed" }
    }

    $jsonPath = Join-Path $EvidenceDirectory "customer-billing-comprehensive-verification.json"
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding utf8

    $markdownPath = Join-Path $EvidenceDirectory "customer-billing-comprehensive-verification.md"
    $lines = @(
        "# Customer Billing Comprehensive Verification",
        "",
        "- Overall status: **$($result.overall_status.ToUpperInvariant())**",
        "- Focused tests: $focusedTests",
        "- Focused failures: $focusedFailures",
        "- Focused errors: $focusedErrors",
        "- Focused skipped: $focusedSkipped",
        "- Full program executed: $(-not $SkipFullProgram)"
    )
    if ($null -ne $fullProgram) {
        $lines += @(
            "- Full program tests: $($fullProgram.pytest.tests)",
            "- Full program failures: $($fullProgram.pytest.failures)",
            "- Full program errors: $($fullProgram.pytest.errors)",
            "- Full program skipped: $($fullProgram.pytest.skipped)",
            "- Full program pytest exit code: $($fullProgram.pytest_exit_code)"
        )
    }
    $lines += @(
        "",
        "## Focused phases",
        ""
    )
    foreach ($phase in $phaseResults) {
        $lines += "- $($phase.label): $($phase.status.ToUpperInvariant()) - $($phase.pytest.tests) tests"
    }
    $lines += @(
        "",
        "## Evidence",
        "",
        "- $jsonPath",
        "- $markdownPath",
        "- Per-phase JUnit XML and logs under $EvidenceDirectory"
    )
    if (-not $SkipFullProgram) {
        $lines += "- Full-program evidence under $(Join-Path $EvidenceDirectory 'full-program')"
    }
    $lines -join [Environment]::NewLine | Set-Content -LiteralPath $markdownPath -Encoding utf8

    Write-Host ""
    Write-Host "=== Comprehensive verification summary ==="
    Write-Host "Focused tests: $focusedTests"
    Write-Host "Focused failures: $focusedFailures"
    Write-Host "Focused errors: $focusedErrors"
    Write-Host "Focused skipped: $focusedSkipped"
    if ($null -ne $fullProgram) {
        Write-Host "Full program tests: $($fullProgram.pytest.tests)"
        Write-Host "Full program failures: $($fullProgram.pytest.failures)"
        Write-Host "Full program errors: $($fullProgram.pytest.errors)"
        Write-Host "Full program pytest exit code: $($fullProgram.pytest_exit_code)"
    }
    Write-Host "Evidence directory: $EvidenceDirectory"

    if (-not $overallPassed) {
        throw "Customer billing comprehensive verification failed"
    }

    Write-Host ""
    Write-Host "CUSTOMER BILLING COMPREHENSIVE VERIFICATION PASSED"
}
finally {
    Pop-Location
}
