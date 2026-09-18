param(
    [switch]$InstallDeps,
    [switch]$RunFullRegression
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ==="
}

$repo = (Get-Location).Path
$resultsRoot = Join-Path $env:USERPROFILE "Downloads\CGT-results"
New-Item -ItemType Directory -Force -Path $resultsRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $resultsRoot "public-governance-genome-qualification_$stamp.log"

function Invoke-Logged {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    Write-Step $Label
    & $Command 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Write-Step "Repository guard"
if (-not (Test-Path (Join-Path $repo "pyproject.toml"))) {
    throw "Run this script from the public repository root."
}
$remote = (git remote get-url origin).Trim()
if ($remote -notmatch "processual-maestro-kernel(\.git)?$" -or $remote -match "private") {
    throw "This runner must be executed in the public processual-maestro-kernel repository."
}
git rev-parse --show-toplevel 2>&1 | Tee-Object -FilePath $log -Append
$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
Write-Host "Branch: $branch" | Tee-Object -FilePath $log -Append
Write-Host "HEAD:   $head" | Tee-Object -FilePath $log -Append

Write-Step "Python 3.14 check"
$py = $null
try {
    $version = (& py -3.14 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and $version.StartsWith("3.14.")) {
        $py = @("py", "-3.14")
    }
} catch {}
if ($null -eq $py) {
    try {
        $version = (& python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null).Trim()
        if ($LASTEXITCODE -eq 0 -and $version.StartsWith("3.14.")) {
            $py = @("python")
        }
    } catch {}
}
if ($null -eq $py) {
    throw "Python 3.14 is required."
}
Write-Host "Using: $($py -join ' ')" | Tee-Object -FilePath $log -Append

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        if ($py.Count -eq 2) {
            & $py[0] $py[1] @Args
        } else {
            & $py[0] @Args
        }
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($nativeExitCode -ne 0) {
        exit $nativeExitCode
    }
}

if ($InstallDeps) {
    Invoke-Logged "Install focused dependencies" {
        Invoke-Python -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Invoke-Python -m pip install -e ".[dev,api,observability,security,database,cache,reports,llm]"
    }
}

Write-Step "Public/private boundary"
if (Test-Path (Join-Path $repo "cgtlib\private")) {
    throw "FAIL: public repository contains cgtlib/private"
}
Invoke-Logged "Verify private package is not importable" {
    Invoke-Python -c "import importlib.util; assert importlib.util.find_spec('cgtlib.private') is None, 'cgtlib.private is importable'; print('OK: private package absent')"
}

$ruffTargets = @(
    "processual_api/cgt_governor/gateway",
    "processual_api/cgt_governor/policy/engine.py",
    "processual_api/routers/cgt_governor.py",
    "tests/test_public_governance_genome_v2.py",
    "tests/test_cgt_wave3c_core_bundle.py",
    "tests/test_governance_gateway_behavior_regression.py",
    "tests/test_cgt_governor_route_boundaries.py"
)

Invoke-Logged "Ruff public governance check" {
    Invoke-Python -m ruff check @ruffTargets
}

$focusedTests = @(
    "tests/test_public_governance_genome_v2.py",
    "tests/test_cgt_wave3c_core_bundle.py",
    "tests/test_governance_gateway_behavior_regression.py",
    "tests/test_cgt_governor_route_boundaries.py",
    "tests/test_adapter_configure_status_routes.py"
)

Invoke-Logged "Focused public governance tests" {
    Invoke-Python -m pytest -q @focusedTests
}

$mypyArgs = @(
    "-m", "mypy",
    "processual_api/cgt_governor/gateway",
    "processual_api/cgt_governor/policy/engine.py",
    "processual_api/routers/cgt_governor.py",
    "--ignore-missing-imports",
    "--follow-imports=silent",
    "--show-error-codes"
)

Invoke-Logged "Public governance typing" {
    Invoke-Python @mypyArgs
}

if ($RunFullRegression) {
    Invoke-Logged "Full public regression" {
        Invoke-Python -m pytest -q
    }
}

Write-Step "Qualification summary"
Write-Host "PASS" | Tee-Object -FilePath $log -Append
Write-Host "Branch: $branch" | Tee-Object -FilePath $log -Append
Write-Host "HEAD:   $head" | Tee-Object -FilePath $log -Append
Write-Host "Log:    $log" | Tee-Object -FilePath $log -Append
