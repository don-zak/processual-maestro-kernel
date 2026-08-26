param(
    [switch]$FullSuite,
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    Write-Host "== Commercial Launch Blocker #1 verification =="
    Write-Host "Repository: $repoRoot"

    $python = Get-Command python -ErrorAction Stop
    Write-Host "Python: $(& $python.Source --version)"

    if ($InstallDependencies) {
        Write-Host "Installing the same public development extras used by CI..."
        & $python.Source -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $python.Source -m pip install ".[dev,api,observability,security,database,cache,reports,llm]"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "Running focused Blocker #1 activation/runtime tests..."
    $env:PYTHONPATH = "."
    & $python.Source -m pytest -q tests/test_subscription_activation_runtime_blocker_a3.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Blocker #1 focused tests failed."
        exit $LASTEXITCODE
    }

    if ($FullSuite) {
        Write-Host "Running the full public unit-test command used by CI..."
        & $python.Source -m pytest `
            --cov=processual_kernel `
            --cov=processual_api `
            --cov-report=xml `
            --cov-report=term-missing `
            -q
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Full public unit-test suite failed."
            exit $LASTEXITCODE
        }
    }

    Write-Host "Blocker #1 verification passed."
}
finally {
    Pop-Location
}
