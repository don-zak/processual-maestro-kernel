[CmdletBinding()]
param(
    [string]$PythonCommand = "python",
    [string]$EvidenceDirectory = "artifacts/local-full-program-verification",
    [switch]$SkipInstall
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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null

    Write-Host "Repository: $repoRoot"
    Write-Host "PowerShell: $($PSVersionTable.PSVersion)"
    Invoke-Checked -Label "Python runtime" -FilePath $PythonCommand -ArgumentList @("--version")

    if (-not $SkipInstall) {
        Invoke-Checked -Label "Upgrade pip" -FilePath $PythonCommand -ArgumentList @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked -Label "Install full project test dependencies" -FilePath $PythonCommand -ArgumentList @(
            "-m", "pip", "install", ".[dev,api,observability,security,database,cache,reports,llm]"
        )
    }

    Invoke-Checked -Label "Pytest availability" -FilePath $PythonCommand -ArgumentList @("-m", "pytest", "--version")

    $junitPath = Join-Path $EvidenceDirectory "full-program-pytest.xml"
    $logPath = Join-Path $EvidenceDirectory "full-program-pytest.log"

    Write-Host ""
    Write-Host "=== Full program pytest ==="
    Write-Host "Running the complete repository test suite through PowerShell..."

    & $PythonCommand -m pytest -ra --junitxml=$junitPath 2>&1 | Tee-Object -FilePath $logPath
    $pytestExitCode = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $junitPath -PathType Leaf)) {
        throw "Full pytest did not produce JUnit evidence at $junitPath"
    }

    $summary = Get-JUnitSummary -Path $junitPath

    $result = [ordered]@{
        schema_version = "2026-08-local-full-program-powershell-v1"
        generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        repository_root = $repoRoot
        powershell_version = $PSVersionTable.PSVersion.ToString()
        python_command = $PythonCommand
        pytest_exit_code = $pytestExitCode
        pytest = $summary
        overall_status = if ($pytestExitCode -eq 0 -and $summary.failures -eq 0 -and $summary.errors -eq 0) { "passed" } else { "failed" }
    }

    $jsonPath = Join-Path $EvidenceDirectory "full-program-verification.json"
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding utf8

    $markdownPath = Join-Path $EvidenceDirectory "full-program-verification.md"
    @(
        "# Local Full Program PowerShell Verification",
        "",
        "- Overall status: **$($result.overall_status.ToUpperInvariant())**",
        "- Pytest exit code: $pytestExitCode",
        "- Tests: $($summary.tests)",
        "- Failures: $($summary.failures)",
        "- Errors: $($summary.errors)",
        "- Skipped: $($summary.skipped)",
        "- Time (s): $($summary.time_seconds)",
        "- PowerShell: $($PSVersionTable.PSVersion)",
        "",
        "Evidence files:",
        "- $junitPath",
        "- $logPath",
        "- $jsonPath"
    ) -join [Environment]::NewLine | Set-Content -LiteralPath $markdownPath -Encoding utf8

    Write-Host ""
    Write-Host "=== Full program verification summary ==="
    Write-Host "Tests: $($summary.tests)"
    Write-Host "Failures: $($summary.failures)"
    Write-Host "Errors: $($summary.errors)"
    Write-Host "Skipped: $($summary.skipped)"
    Write-Host "Pytest exit code: $pytestExitCode"
    Write-Host "Evidence directory: $EvidenceDirectory"

    if ($pytestExitCode -ne 0 -or $summary.failures -ne 0 -or $summary.errors -ne 0) {
        throw "Full program pytest verification failed. Inspect $logPath and $junitPath"
    }

    Write-Host ""
    Write-Host "FULL PROGRAM PYTEST VERIFICATION PASSED"
}
finally {
    Pop-Location
}
