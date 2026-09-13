[CmdletBinding()]
param(
    [string]$ExpectedSha = '',
    [string]$PythonBin = 'python',
    [string]$ResultsDir = 'launch-hardening-results',
    [switch]$IncludeDocker,
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
$Results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $status = if ($Passed) { 'PASS' } else { 'FAIL' }
    $safeDetail = ($Detail -replace '(?i)(token|secret|password|api[_-]?key)=[^\s]+', '$1=<redacted>')
    $entry = [pscustomobject]@{ name = $Name; status = $status; detail = $safeDetail }
    $Results.Add($entry)
    Write-Host ("[{0}] {1} - {2}" -f $status, $Name, $safeDetail)
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Captured {
    param([string]$Name, [string]$Command, [string[]]$Arguments)
    try {
        $output = & $Command @Arguments 2>&1
        $code = $LASTEXITCODE
        $text = ($output | Out-String).Trim()
        Add-Result $Name ($code -eq 0) $text
        return ($code -eq 0)
    }
    catch {
        Add-Result $Name $false $_.Exception.GetType().Name
        return $false
    }
}

function Invoke-PythonPytest {
    param([string]$Name, [string[]]$Tests)
    $args = @('-m', 'pytest', '-q') + $Tests
    return Invoke-Captured $Name $PythonBin $args
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
Add-Result 'working-tree-clean' ([string]::IsNullOrWhiteSpace($porcelain)) ($(if ($porcelain) { 'working tree has changes' } else { 'clean' }))
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
    'tests/test_final_release_checklist_regression.py'
) | Out-Null

Invoke-Captured 'release-check' $PythonBin @('scripts/release_check.py') | Out-Null

if ($IncludeDocker) {
    Require-Command 'docker'
    Invoke-Captured 'docker-compose-config' 'docker' @('compose', 'config', '--quiet') | Out-Null
    Invoke-Captured 'docker-public-build' 'docker' @('build', '--target', 'public', '-t', 'pmk-public-launch-qualification:local', '.') | Out-Null
    Invoke-Captured 'docker-public-no-private-cgt' 'docker' @('run', '--rm', '--entrypoint', 'sh', 'pmk-public-launch-qualification:local', '-c', 'test ! -e /app/cgtlib/private && python -c "import cgtlib, cgtlib._backend; assert not cgtlib._backend.HAS_PRIVATE_COMPUTE"') | Out-Null

    try {
        $ports = (& docker compose config | Out-String)
        $grafanaLoopback = $ports -match '127\.0\.0\.1:3000:3000'
        Add-Result 'grafana-loopback-binding' $grafanaLoopback ($(if ($grafanaLoopback) { 'Grafana is loopback-bound' } else { 'Grafana is not loopback-bound' }))
    }
    catch {
        Add-Result 'grafana-loopback-binding' $false $_.Exception.GetType().Name
    }
}

if ($IncludeGitHub) {
    Require-Command 'gh'
    $apiPath = "repos/$Repo/commits/$head/check-runs"
    try {
        $raw = & gh api $apiPath 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'gh api failed' }
        $payload = $raw | ConvertFrom-Json
        $count = [int]$payload.total_count
        Add-Result 'github-check-allocation' ($count -gt 0) ("check_runs={0}" -f $count)
    }
    catch {
        Add-Result 'github-check-allocation' $false 'Unable to read GitHub check-runs for exact HEAD'
    }
}

if ($IncludeRemote) {
    if (-not $RemoteBaseUrl) { throw 'RemoteBaseUrl is required with -IncludeRemote' }
    $base = $RemoteBaseUrl.TrimEnd('/')
    foreach ($probe in @('/health/live', '/health/ready')) {
        try {
            $response = Invoke-WebRequest -Uri ($base + $probe) -UseBasicParsing -TimeoutSec 15
            $body = $response.Content
            $safe = if ($body.Length -gt 500) { $body.Substring(0, 500) } else { $body }
            Add-Result ("remote{0}" -f ($probe -replace '/', '-')) ($response.StatusCode -eq 200) ("HTTP {0}; {1}" -f $response.StatusCode, $safe)
        }
        catch {
            $status = $null
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            Add-Result ("remote{0}" -f ($probe -replace '/', '-')) $false ("HTTP {0}" -f $status)
        }
    }
}

$failed = @($Results | Where-Object { $_.status -eq 'FAIL' })
$summary = if ($failed.Count -eq 0) { 'OVERALL PASS' } else { "OVERALL FAIL ($($failed.Count) failed checks)" }
$lines = @("Launch hardening qualification", "HEAD: $head", "Branch: $branch", "Result: $summary", '')
$lines += $Results | ForEach-Object { "[$($_.status)] $($_.name): $($_.detail)" }
$lines | Set-Content -Path $ReportPath -Encoding UTF8
@{ head = $head; branch = $branch; overall = $summary; checks = @($Results) } | ConvertTo-Json -Depth 5 | Set-Content -Path $JsonPath -Encoding UTF8
Write-Host $summary
Write-Host "Evidence: $ReportPath"
Write-Host "JSON: $JsonPath"
if ($failed.Count -gt 0) { exit 1 }
exit 0
