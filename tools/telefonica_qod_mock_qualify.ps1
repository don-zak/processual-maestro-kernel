#requires -Version 7.2
<#
.SYNOPSIS
Qualifies the public Telefonica Open Gateway QoD v0 mock sandbox.

.DESCRIPTION
Uses only Telefonica's documented mock convenience token and public sandbox
endpoint. No user credentials are required or accepted.

This runner is deliberately separate from the governed CAMARA QoD v1.1.0
provider qualification path. A successful run proves only external mock
interoperability/reachability for Telefonica QoD v0.10. It MUST NOT be used to
set provider_sandbox_proven, runtime_connector_approved, or production_allowed.

The runner performs:
  1. HTTPS/DNS validation for the fixed Telefonica sandbox host.
  2. GET /qos-profiles.
  3. POST /sessions using deterministic mock-safe test identifiers.
  4. GET /sessions/{sessionId} when a session id is returned.
  5. DELETE /sessions/{sessionId} as cleanup.
  6. Sanitized evidence output with hashes instead of raw response bodies.
#>

[CmdletBinding()]
param(
    [string]$EvidenceDirectory = './telefonica-qod-mock-evidence',
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 30,
    [switch]$SkipSessionLifecycle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$BaseUri = 'https://sandbox.opengateway.telefonica.com/apigateway/ogw/qod/v0'
$MockToken = 'mock_sandbox_access_token'
$DocumentedScope = 'dpv:RequestedServiceProvision#qod'
$ExpectedApiVersion = 'v0.10'

function Fail {
    param([string]$Message)
    throw $Message
}

function Get-Sha256Hex {
    param([AllowEmptyString()][string]$Value)
    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $hash = [Security.Cryptography.SHA256]::HashData($bytes)
    return ([Convert]::ToHexString($hash)).ToLowerInvariant()
}

function Assert-PublicHttpsHost {
    param([Parameter(Mandatory = $true)][Uri]$Uri)

    if ($Uri.Scheme -ne 'https') {
        Fail 'Telefonica sandbox endpoint must use HTTPS.'
    }
    if ($Uri.DnsSafeHost -ne 'sandbox.opengateway.telefonica.com') {
        Fail 'Unexpected Telefonica sandbox host.'
    }

    $addresses = [Net.Dns]::GetHostAddresses($Uri.DnsSafeHost)
    if (-not $addresses -or $addresses.Count -eq 0) {
        Fail 'Telefonica sandbox DNS resolution returned no addresses.'
    }

    foreach ($address in $addresses) {
        if ([Net.IPAddress]::IsLoopback($address)) {
            Fail 'Telefonica sandbox unexpectedly resolved to loopback.'
        }
    }

    return @($addresses | ForEach-Object { $_.ToString() } | Sort-Object -Unique)
}

function Invoke-SandboxRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$Body
    )

    $headers = @{
        Authorization = "Bearer $MockToken"
        Accept = 'application/json'
    }

    $args = @{
        Method = $Method
        Uri = $Uri
        Headers = $headers
        TimeoutSec = $TimeoutSeconds
        MaximumRedirection = 0
        SkipHttpErrorCheck = $true
        ErrorAction = 'Stop'
    }

    if (-not [string]::IsNullOrWhiteSpace($Body)) {
        $args.ContentType = 'application/json'
        $args.Body = $Body
    }

    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest @args
        return [pscustomobject]@{
            status = [int]$response.StatusCode
            body = [string]$response.Content
            elapsed_ms = $timer.ElapsedMilliseconds
        }
    }
    finally {
        $timer.Stop()
    }
}

function New-EvidenceRecord {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [object]$Result,
        [int[]]$ExpectedStatuses
    )

    $passed = $ExpectedStatuses -contains [int]$Result.status
    return [ordered]@{
        name = $Name
        method = $Method
        path = $Path
        http_status = [int]$Result.status
        expected_statuses = @($ExpectedStatuses)
        passed = $passed
        elapsed_ms = [long]$Result.elapsed_ms
        response_body_retained = $false
        response_body_sha256 = Get-Sha256Hex -Value ([string]$Result.body)
    }
}

Write-Host '==> Telefonica QoD v0.10 mock qualification'
Write-Host "Endpoint: $BaseUri"
Write-Host "Documented scope: $DocumentedScope"
Write-Host 'Credential mode: documented public mock convenience token'

$base = [Uri]$BaseUri
$resolvedAddresses = Assert-PublicHttpsHost -Uri $base
Write-Host "[PASS] HTTPS/DNS: $($resolvedAddresses -join ', ')"

$records = @()
$failures = 0
$sessionId = $null

Write-Host '==> GET QoS profiles'
$profilesResult = Invoke-SandboxRequest -Method 'GET' -Uri "$BaseUri/qos-profiles"
$profilesRecord = New-EvidenceRecord -Name 'get_qos_profiles' -Method 'GET' -Path '/qos-profiles' -Result $profilesResult -ExpectedStatuses @(200)
$records += $profilesRecord
if (-not $profilesRecord.passed) { $failures++ }
Write-Host "[$(if ($profilesRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($profilesResult.status)"

if (-not $SkipSessionLifecycle) {
    # The identifiers below are synthetic test values. The phone number ends in 8
    # to avoid Telefonica's documented deterministic mock-conflict suffix 9.
    # 198.51.100.10 is TEST-NET-2 documentation space and is not a real backend.
    $createBodyObject = [ordered]@{
        device = [ordered]@{
            phoneNumber = '+34600000008'
        }
        applicationServer = [ordered]@{
            ipv4Address = '198.51.100.10'
        }
        qosProfile = 'QOS_E'
        duration = 300
    }
    $createBody = $createBodyObject | ConvertTo-Json -Depth 10 -Compress

    Write-Host '==> POST mock QoD session'
    $createResult = Invoke-SandboxRequest -Method 'POST' -Uri "$BaseUri/sessions" -Body $createBody
    $createRecord = New-EvidenceRecord -Name 'create_session' -Method 'POST' -Path '/sessions' -Result $createResult -ExpectedStatuses @(201)
    $createRecord.request_body_sha256 = Get-Sha256Hex -Value $createBody
    $createRecord.synthetic_test_data = $true
    $records += $createRecord
    if (-not $createRecord.passed) { $failures++ }
    Write-Host "[$(if ($createRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($createResult.status)"

    if ($createRecord.passed -and -not [string]::IsNullOrWhiteSpace($createResult.body)) {
        try {
            $created = $createResult.body | ConvertFrom-Json -Depth 30
            if ($null -ne $created.PSObject.Properties['sessionId']) {
                $candidate = [string]$created.sessionId
                if ($candidate -match '^[A-Za-z0-9._~-]{1,256}$') {
                    $sessionId = $candidate
                }
            }
        }
        catch {
            Write-Host '[WARN] Create response was not parseable JSON; lifecycle follow-up skipped.'
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($sessionId)) {
        $escapedSessionId = [Uri]::EscapeDataString($sessionId)

        Write-Host '==> GET created mock QoD session'
        $getResult = Invoke-SandboxRequest -Method 'GET' -Uri "$BaseUri/sessions/$escapedSessionId"
        $getRecord = New-EvidenceRecord -Name 'get_session' -Method 'GET' -Path '/sessions/{sessionId}' -Result $getResult -ExpectedStatuses @(200)
        $getRecord.session_id_sha256 = Get-Sha256Hex -Value $sessionId
        $records += $getRecord
        if (-not $getRecord.passed) { $failures++ }
        Write-Host "[$(if ($getRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($getResult.status)"

        Write-Host '==> DELETE created mock QoD session (cleanup)'
        $deleteResult = Invoke-SandboxRequest -Method 'DELETE' -Uri "$BaseUri/sessions/$escapedSessionId"
        $deleteRecord = New-EvidenceRecord -Name 'delete_session' -Method 'DELETE' -Path '/sessions/{sessionId}' -Result $deleteResult -ExpectedStatuses @(204, 200)
        $deleteRecord.session_id_sha256 = Get-Sha256Hex -Value $sessionId
        $records += $deleteRecord
        if (-not $deleteRecord.passed) { $failures++ }
        Write-Host "[$(if ($deleteRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($deleteResult.status)"
    }
    elseif ($createRecord.passed) {
        $failures++
        Write-Host '[FAIL] Create returned success but no safe sessionId was available for cleanup.'
    }
}

$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-v0-mock-summary.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-v0-mock-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'public_mock_sandbox'
    api_family = 'quality_on_demand'
    api_version = $ExpectedApiVersion
    base_uri = $BaseUri
    documented_scope = $DocumentedScope
    mock_convenience_token_used = $true
    user_credentials_used = $false
    raw_credentials_retained = $false
    external_network_observed = $true
    external_mock_sandbox_proven = ($failures -eq 0)
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    operations = $records
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host ''
if ($failures -eq 0) {
    Write-Host 'TELEFONICA QOD MOCK QUALIFICATION: PASS'
    Write-Host 'external_mock_sandbox_proven=true'
    Write-Host 'operator_network_qos_proven=false'
    Write-Host 'governed_camara_v1_1_provider_sandbox_proven=false'
    Write-Host 'runtime_connector_approved=false'
    Write-Host 'production_allowed=false'
    Write-Host "Summary: $summaryPath"
    exit 0
}

Write-Host 'TELEFONICA QOD MOCK QUALIFICATION: FAIL'
Write-Host 'No provider/runtime/production authority was granted.'
Write-Host "Summary: $summaryPath"
exit 1
