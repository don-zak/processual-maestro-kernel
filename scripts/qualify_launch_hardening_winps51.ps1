[CmdletBinding()]
param(
    [string]$ExpectedSha = '',
    [string]$PythonBin = 'python',
    [string]$ResultsDir = 'launch-hardening-results',
    [switch]$IncludeStaticReleaseCheck,
    [switch]$IncludeProductionReleaseGate,
    [switch]$IncludeDocker,
    [switch]$IncludeCompose,
    [switch]$IncludeGitHub,
    [switch]$IncludeRemote,
    [string]$RemoteBaseUrl = '',
    [string]$Repo = 'don-zak/processual-maestro-kernel'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
$ReportPath = Join-Path $ResultsDir 'launch-hardening-report.txt'
$JsonPath = Join-Path $ResultsDir 'launch-hardening-report.json'
$Results = New-Object System.Collections.ArrayList

function Add-Entry {
    param([string]$Name, [string]$Status, [string]$Detail)
    $safeDetail = ($Detail -replace '(?i)(token|secret|password|api[_-]?key)=[^\s]+', '$1=<redacted>')
    $entry = [pscustomobject]@{ name = $Name; status = $Status; detail = $safeDetail }
    [void]$Results.Add($entry)
    Write-Host ("[{0}] {1} - {2}" -f $Status, $Name, $safeDetail)
}

function Add-Result {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    Add-Entry $Name ($(if ($Passed) { 'PASS' } else { 'FAIL' })) $Detail
}

function Add-Skip {
    param([string]$Name, [string]$Detail)
    Add-Entry $Name 'SKIP' $Detail
}

function Add-Blocked {
    param([string]$Name, [string]$Detail)
    Add-Entry $Name 'BLOCKED' $Detail
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Captured {
    param([string]$Name, [string]$Command, [string[]]$Arguments)

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Command @Arguments 2>&1
        $code = $LASTEXITCODE
        $text = ($output | ForEach-Object { $_.ToString() } | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) {
            $text = "exit_code=$code"
        }
        Add-Result $Name ($code -eq 0) $text
        return ($code -eq 0)
    }
    catch {
        $detail = $_.Exception.Message
        if ([string]::IsNullOrWhiteSpace($detail)) {
            $detail = $_.Exception.GetType().FullName
        }
        Add-Result $Name $false $detail
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Invoke-PythonPytest {
    param([string]$Name, [string[]]$Tests)
    $args = @('-m', 'pytest', '-q') + $Tests
    return Invoke-Captured $Name $PythonBin $args
}

function Test-DockerDaemon {
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & docker info --format '{{.ServerVersion}}' 2>&1
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            $serverVersion = ($output | ForEach-Object { $_.ToString() } | Out-String).Trim()
            Add-Result 'docker-daemon' $true ("server_version={0}" -f $serverVersion)
            return $true
        }
        $detail = ($output | ForEach-Object { $_.ToString() } | Out-String).Trim()
        Add-Blocked 'docker-daemon' ($(if ($detail) { $detail } else { "docker info exit_code=$code" }))
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

Require-Command 'git'
Require-Command $PythonBin

$head = (& git rev-parse HEAD).Trim()
$branch = (& git branch --show-current).Trim()
if ($ExpectedSha) {
    Add-Result 'exact-sha' ($head -eq $ExpectedSha) ("HEAD={0}; expected={1}" -f $head, $ExpectedSha)
} else {
    Add-Result 'exact-sha' $true ("HEAD={0}; no expected SHA supplied" -f $head)
}
Add-Result 'branch' ($branch -eq 'feat/evaluation-key-delivery-lifecycle') ("branch={0}" -f $branch)

$porcelain = (& git status --porcelain | Out-String).Trim()
$treeDetail = if ($porcelain) { ($porcelain -replace "`r?`n", '; ') } else { 'clean' }
Add-Result 'working-tree-clean' ([string]::IsNullOrWhiteSpace($porcelain)) $treeDetail
Invoke-Captured 'git-diff-check' 'git' @('diff', '--check') | Out-Null
Invoke-Captured 'compileall' $PythonBin @('-m', 'compileall', '-q', 'processual_api', 'processual_kernel', 'cgtlib') | Out-Null

Invoke-PythonPytest 'launch-targeted-tests' @(
    'tests/test_health_readiness_contract.py',
    'tests/test_docker_compose_production_regression.py',
    'tests/test_production_secrets_contract.py',
    'tests/test_production_startup_hardening_regression.py',
    'tests/test_auth_fallback_production_boundary.py',
    'tests/test_secret_encryption_readiness_regression.py',
    'tests/test_fastapi_integration_smoke.py',
    'tests/test_final_release_checklist_regression.py',
    'tests/test_release_check_operator_contract.py',
    'tests/test_adapter_registry_safe_logging.py',
    'tests/test_sensitive_auth_safe_logging_regression.py',
    'tests/test_llm_reporter_safe_failure_regression.py',
    'tests/test_postgres_recovery_qualification_contract.py'
) | Out-Null

if ($IncludeStaticReleaseCheck) {
    Invoke-Captured 'static-release-check' $PythonBin @('scripts/release_check.py', '--skip-docker') | Out-Null
} else {
    Add-Skip 'static-release-check' 'Use -IncludeStaticReleaseCheck in a clean release workspace; local .venv/cache files intentionally fail this check.'
}

if ($IncludeProductionReleaseGate) {
    Invoke-Captured 'production-release-gate' $PythonBin @('-m', 'processual_api.release_gate') | Out-Null
} else {
    Add-Skip 'production-release-gate' 'Use -IncludeProductionReleaseGate only after loading the intended staging/production environment without printing secrets.'
}

if ($IncludeDocker) {
    Require-Command 'docker'
    if (Test-DockerDaemon) {
        $buildOk = Invoke-Captured 'docker-public-build' 'docker' @('build', '--target', 'public', '-t', 'pmk-public-launch-qualification:local', '.')
        if ($buildOk) {
            $publicProof = "test ! -e /app/cgtlib/private && python -c 'import cgtlib, cgtlib._backend; assert not cgtlib._backend.HAS_PRIVATE_COMPUTE'"
            Invoke-Captured 'docker-public-no-private-cgt' 'docker' @('run', '--rm', '--entrypoint', 'sh', 'pmk-public-launch-qualification:local', '-c', $publicProof) | Out-Null
        } else {
            Add-Skip 'docker-public-no-private-cgt' 'Public image build failed; private-CGT absence proof was not run.'
        }
    } else {
        Add-Skip 'docker-public-build' 'Docker daemon unavailable; build not attempted.'
        Add-Skip 'docker-public-no-private-cgt' 'Docker daemon unavailable; image proof not attempted.'
    }
} else {
    Add-Skip 'docker-image-qualification' 'Use -IncludeDocker on a computer with Docker; this mode does not require Compose secrets.'
}

if ($IncludeCompose) {
    Require-Command 'docker'
    if (Test-DockerDaemon) {
        $composeOk = Invoke-Captured 'docker-compose-config' 'docker' @('compose', 'config', '--quiet')
        if ($composeOk) {
            $previousErrorActionPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $portsOutput = & docker compose config 2>&1
                $portsCode = $LASTEXITCODE
                $ports = ($portsOutput | ForEach-Object { $_.ToString() } | Out-String)
                if ($portsCode -ne 0) {
                    Add-Result 'grafana-loopback-binding' $false ("docker compose config exit_code={0}" -f $portsCode)
                } else {
                    $grafanaLoopback = $ports -match '127\.0\.0\.1:3000:3000'
                    Add-Result 'grafana-loopback-binding' $grafanaLoopback ($(if ($grafanaLoopback) { 'Grafana is loopback-bound' } else { 'Grafana is not loopback-bound' }))
                }
            }
            finally {
                $ErrorActionPreference = $previousErrorActionPreference
            }
        } else {
            Add-Skip 'grafana-loopback-binding' 'Compose configuration failed; rendered port proof was not run.'
        }
    } else {
        Add-Skip 'docker-compose-config' 'Docker daemon unavailable; Compose qualification not attempted.'
        Add-Skip 'grafana-loopback-binding' 'Docker daemon unavailable; rendered port proof not attempted.'
    }
} else {
    Add-Skip 'compose-qualification' 'Use -IncludeCompose only after the intended Compose environment is loaded securely.'
}

if ($IncludeGitHub) {
    Require-Command 'gh'
    $apiPath = "repos/$Repo/commits/$head/check-runs"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = & gh api $apiPath 2>$null
        $code = $LASTEXITCODE
        if ($code -ne 0) { throw "gh api failed with exit code $code" }
        $payload = $raw | ConvertFrom-Json
        $count = [int]$payload.total_count
        if ($count -gt 0) {
            Add-Result 'github-check-allocation' $true ("check_runs={0}" -f $count)
        } else {
            Add-Blocked 'github-check-allocation' 'check_runs=0; no executable GitHub Actions allocation exists for exact HEAD'
        }
    }
    catch {
        Add-Blocked 'github-check-allocation' 'Unable to read GitHub check-runs for exact HEAD'
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
} else {
    Add-Skip 'github-check-allocation' 'Use -IncludeGitHub when GitHub CLI is authenticated.'
}

if ($IncludeRemote) {
    if (-not $RemoteBaseUrl) { throw 'RemoteBaseUrl is required with -IncludeRemote' }
    $base = $RemoteBaseUrl.TrimEnd('/')
    foreach ($probe in @('/health/live', '/health/ready')) {
        try {
            $response = Invoke-WebRequest -Uri ($base + $probe) -UseBasicParsing -TimeoutSec 15
            $body = [string]$response.Content
            $safe = if ($body.Length -gt 500) { $body.Substring(0, 500) } else { $body }
            Add-Result ("remote{0}" -f ($probe -replace '/', '-')) ($response.StatusCode -eq 200) ("HTTP {0}; {1}" -f $response.StatusCode, $safe)
        }
        catch {
            $status = $null
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            Add-Result ("remote{0}" -f ($probe -replace '/', '-')) $false ("HTTP {0}" -f $status)
        }
    }
} else {
    Add-Skip 'remote-health' 'Use -IncludeRemote -RemoteBaseUrl <https://...> for the exact deployed candidate.'
}

$failed = @($Results | Where-Object { $_.status -eq 'FAIL' })
$blocked = @($Results | Where-Object { $_.status -eq 'BLOCKED' })
if ($failed.Count -gt 0) {
    $summary = "OVERALL FAIL ($($failed.Count) failed checks)"
} elseif ($blocked.Count -gt 0) {
    $summary = "OVERALL BLOCKED ($($blocked.Count) infrastructure/external blockers)"
} else {
    $summary = 'OVERALL PASS FOR REQUESTED CHECKS'
}

$lines = @("Launch hardening qualification", "HEAD: $head", "Branch: $branch", "Result: $summary", '')
$lines += @($Results | ForEach-Object { "[$($_.status)] $($_.name): $($_.detail)" })
$lines | Set-Content -Path $ReportPath -Encoding UTF8

$resultArray = @($Results | ForEach-Object { $_ })
$reportObject = [pscustomobject]@{
    head = $head
    branch = $branch
    overall = $summary
    checks = $resultArray
}
$reportObject | ConvertTo-Json -Depth 5 | Set-Content -Path $JsonPath -Encoding UTF8

Write-Host $summary
Write-Host "Evidence: $ReportPath"
Write-Host "JSON: $JsonPath"
if ($failed.Count -gt 0) { exit 1 }
if ($blocked.Count -gt 0) { exit 2 }
exit 0
