[CmdletBinding()]
param(
    [string]$PythonCommand = "python",
    [string]$EvidenceDirectory = "artifacts/enterprise-endpoint-task-bindings-verification",
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
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Get-JUnitSummary {
    param([Parameter(Mandatory)][string]$Path)
    [xml]$document = Get-Content -LiteralPath $Path -Raw
    $suiteNodes = if ($null -ne $document.testsuites) {
        @($document.testsuites.testsuite)
    } elseif ($null -ne $document.testsuite) {
        @($document.testsuite)
    } else {
        @()
    }
    if ($suiteNodes.Count -eq 0) {
        throw "Unable to read JUnit test suites from $Path"
    }
    $summary = [ordered]@{ tests = 0; failures = 0; errors = 0; skipped = 0; time_seconds = 0.0 }
    foreach ($suite in $suiteNodes) {
        $summary.tests += [int]$suite.tests
        $summary.failures += [int]$suite.failures
        $summary.errors += [int]$suite.errors
        $summary.skipped += [int]$suite.skipped
        $summary.time_seconds += [double]$suite.time
    }
    $summary.time_seconds = [Math]::Round($summary.time_seconds, 3)
    return $summary
}

function Invoke-PytestPhase {
    param(
        [Parameter(Mandatory)][string]$PhaseId,
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$Tests,
        [Parameter(Mandatory)][string]$EvidenceDirectory,
        [Parameter(Mandatory)][string]$PythonCommand
    )
    foreach ($test in $Tests) {
        if (-not (Test-Path -LiteralPath $test -PathType Leaf)) {
            throw "Required verification test is missing: $test"
        }
    }
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
    $pytest = Get-JUnitSummary -Path $junitPath
    $status = if ($exitCode -eq 0 -and $pytest.failures -eq 0 -and $pytest.errors -eq 0) { "passed" } else { "failed" }
    $result = [ordered]@{
        phase_id = $PhaseId
        label = $Label
        status = $status
        pytest_exit_code = $exitCode
        pytest = $pytest
        tests = $Tests
        junit = $junitPath
        log = $logPath
    }
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory "$PhaseId.json") -Encoding utf8
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

    $contractTests = @(
        "tests/test_integration_task_catalog_contracts.py",
        "tests/test_integration_task_injection.py",
        "tests/test_enterprise_endpoint_bindings.py"
    )
    $mappingTests = @(
        "tests/test_enterprise_endpoint_request_mapping.py",
        "tests/test_settings_enterprise_request_mapping_runtime.py",
        "tests/test_settings_enterprise_endpoint_bindings_runtime.py"
    )
    $sandboxProofTests = @(
        "tests/test_enterprise_endpoint_sandbox_grants.py",
        "tests/test_enterprise_sandbox_execution.py",
        "tests/test_enterprise_sandbox_task_injection_proof.py",
        "tests/test_settings_enterprise_sandbox_execution_runtime.py"
    )
    $failureReviewTests = @(
        "tests/test_enterprise_endpoint_failure_review.py",
        "tests/test_settings_enterprise_endpoint_failure_review_runtime.py",
        "tests/test_settings_enterprise_failure_review_ui.py"
    )
    $settingsBoundaryTests = @(
        "tests/test_settings_enterprise_endpoints_ui.py",
        "tests/test_settings_enterprise_sandbox_proof_ui.py",
        "tests/test_settings_enterprise_integration_runtime.py",
        "tests/test_enterprise_endpoint_sandbox_readiness.py",
        "tests/test_api_readiness_automatic_gate_b1.py",
        "tests/test_api_readiness_app_coverage_b1.py"
    )

    $phases = @()
    $phases += Invoke-PytestPhase -PhaseId "01-contracts" -Label "Advertised integration task contracts" -Tests $contractTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phases += Invoke-PytestPhase -PhaseId "02-mappings" -Label "Endpoint request and response mappings" -Tests $mappingTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phases += Invoke-PytestPhase -PhaseId "03-live-sandbox-proof" -Label "Governed live sandbox proof, grants, and task injection" -Tests $sandboxProofTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phases += Invoke-PytestPhase -PhaseId "04-failure-review-recovery" -Label "Sandbox failure review, correction, and successful retest lifecycle" -Tests $failureReviewTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand
    $phases += Invoke-PytestPhase -PhaseId "05-settings-boundaries" -Label "Enterprise Settings UI, runtime, and readiness boundaries" -Tests $settingsBoundaryTests -EvidenceDirectory $EvidenceDirectory -PythonCommand $PythonCommand

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
    foreach ($phase in $phases) {
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
        schema_version = "2026-08-enterprise-endpoint-task-bindings-powershell-v2"
        generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        repository_root = $repoRoot
        powershell_version = $PSVersionTable.PSVersion.ToString()
        python_command = $PythonCommand
        focused = [ordered]@{
            tests = $focusedTests
            failures = $focusedFailures
            errors = $focusedErrors
            skipped = $focusedSkipped
            phases = $phases
        }
        full_program = $fullProgram
        overall_status = if ($overallPassed) { "passed" } else { "failed" }
    }
    $jsonPath = Join-Path $EvidenceDirectory "enterprise-endpoint-task-bindings-verification.json"
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding utf8
    $markdownPath = Join-Path $EvidenceDirectory "enterprise-endpoint-task-bindings-verification.md"
    $lines = @(
        "# Enterprise Endpoint Task Bindings Verification",
        "",
        "- Overall status: **$($result.overall_status.ToUpperInvariant())**",
        "- Focused tests: $focusedTests",
        "- Focused failures: $focusedFailures",
        "- Focused errors: $focusedErrors",
        "- Focused skipped: $focusedSkipped",
        "- Full program executed: $(-not $SkipFullProgram)",
        "",
        "## Focused phases",
        ""
    )
    foreach ($phase in $phases) {
        $lines += "- $($phase.label): $($phase.status.ToUpperInvariant()) - $($phase.pytest.tests) tests"
    }
    if ($null -ne $fullProgram) {
        $lines += @(
            "",
            "## Full program",
            "",
            "- Tests: $($fullProgram.pytest.tests)",
            "- Failures: $($fullProgram.pytest.failures)",
            "- Errors: $($fullProgram.pytest.errors)",
            "- Skipped: $($fullProgram.pytest.skipped)",
            "- Pytest exit code: $($fullProgram.pytest_exit_code)"
        )
    }
    $lines -join [Environment]::NewLine | Set-Content -LiteralPath $markdownPath -Encoding utf8

    Write-Host ""
    Write-Host "=== Enterprise endpoint verification summary ==="
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
        throw "Enterprise endpoint task bindings verification failed"
    }
    Write-Host ""
    Write-Host "ENTERPRISE ENDPOINT TASK BINDINGS VERIFICATION PASSED"
}
finally {
    Pop-Location
}
