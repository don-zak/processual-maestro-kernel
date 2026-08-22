#requires -Version 7.2
<#
.SYNOPSIS
Exercises controlled negative paths for Telefonica Open Gateway QoD v0.10.

.DESCRIPTION
Reads TELEFONICA_CLIENT_ID and TELEFONICA_CLIENT_SECRET from environment,
obtains a normal CIBA access token, then performs only bounded negative tests:

1. POST /qod/v0/sessions with an out-of-range duration (expect 400).
2. GET a synthetic, non-existent session UUID with a valid token (expect 404).
3. GET the same synthetic session without Authorization (expect 401 or 403).
4. POST /qod/v0/sessions using the documented mock-conflict phone-number suffix
   9 (expect 409).

The script never writes raw secrets, access tokens, auth_req_id values, response
bodies, or session identifiers to evidence. It records status codes, timings,
and SHA-256 body hashes only.

This is negative-path mock/sandbox evidence only. It MUST NOT upgrade operator
network proof, governed CAMARA v1.1.0 provider proof, runtime connector approval,
or production authority.
#>

[CmdletBinding()]
param(
    [string]$EvidenceDirectory = './telefonica-qod-ciba-evidence',
    [string]$LoginHint = 'tel:+34666666668',
    [string]$Scope = 'dpv:RequestedServiceProvision#qod',
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Gateway = 'https://sandbox.opengateway.telefonica.com/apigateway'
$BaseUri = "$Gateway/qod/v0"
$ClientId = [Environment]::GetEnvironmentVariable('TELEFONICA_CLIENT_ID')
$ClientSecret = [Environment]::GetEnvironmentVariable('TELEFONICA_CLIENT_SECRET')

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

function New-BasicAuthorization {
    $raw = "$ClientId`:$ClientSecret"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw))
    return "Basic $encoded"
}

function Invoke-ProbeRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$AccessToken,
        [string]$Body,
        [switch]$NoAuthorization
    )

    $headers = @{ Accept = 'application/json' }
    if (-not $NoAuthorization) {
        if ([string]::IsNullOrWhiteSpace($AccessToken)) { Fail 'Access token is required.' }
        $headers.Authorization = "Bearer $AccessToken"
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
    finally { $timer.Stop() }
}

function Add-EvidenceRecord {
    param(
        [System.Collections.ArrayList]$Records,
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [object]$Result,
        [int[]]$ExpectedStatuses
    )

    $record = [ordered]@{
        name = $Name
        method = $Method
        path = $Path
        http_status = [int]$Result.status
        expected_statuses = @($ExpectedStatuses)
        passed = ($ExpectedStatuses -contains [int]$Result.status)
        elapsed_ms = [long]$Result.elapsed_ms
        response_body_retained = $false
        response_body_sha256 = Get-Sha256Hex -Value ([string]$Result.body)
    }
    [void]$Records.Add($record)
    return $record
}

if ([string]::IsNullOrWhiteSpace($ClientId)) { Fail 'TELEFONICA_CLIENT_ID is not set.' }
if ([string]::IsNullOrWhiteSpace($ClientSecret)) { Fail 'TELEFONICA_CLIENT_SECRET is not set.' }
if ($LoginHint -notmatch '^(tel:\+[1-9][0-9]{7,14}|ipport:.+)$') { Fail 'LoginHint must be a tel:+E164 or ipport: value.' }
if ($Scope -ne 'dpv:RequestedServiceProvision#qod') { Fail 'Unexpected QoD scope.' }

Write-Host '==> Telefonica QoD CIBA negative-path probe'
Write-Host "QoD base: $BaseUri"
Write-Host "Scope: $Scope"
Write-Host '[PASS] Client credentials loaded from environment (values not printed).'

$authResponse = Invoke-WebRequest `
    -Method POST `
    -Uri "$Gateway/bc-authorize" `
    -Headers @{ Authorization = (New-BasicAuthorization); Accept = 'application/json' } `
    -ContentType 'application/x-www-form-urlencoded' `
    -Body @{ login_hint = $LoginHint; scope = $Scope } `
    -TimeoutSec $TimeoutSeconds `
    -MaximumRedirection 0 `
    -SkipHttpErrorCheck `
    -ErrorAction Stop

if ([int]$authResponse.StatusCode -ne 200) {
    Fail "CIBA authorization failed with HTTP $([int]$authResponse.StatusCode)."
}
$authJson = ([string]$authResponse.Content) | ConvertFrom-Json -Depth 20
$authReqId = [string]$authJson.auth_req_id
if ([string]::IsNullOrWhiteSpace($authReqId)) { Fail 'CIBA authorization returned no auth_req_id.' }
Write-Host '[PASS] POST /bc-authorize HTTP 200'

$tokenResponse = Invoke-WebRequest `
    -Method POST `
    -Uri "$Gateway/token" `
    -Headers @{ Authorization = (New-BasicAuthorization); Accept = 'application/json' } `
    -ContentType 'application/x-www-form-urlencoded' `
    -Body @{ grant_type = 'urn:openid:params:grant-type:ciba'; auth_req_id = $authReqId } `
    -TimeoutSec $TimeoutSeconds `
    -MaximumRedirection 0 `
    -SkipHttpErrorCheck `
    -ErrorAction Stop

if ([int]$tokenResponse.StatusCode -ne 200) {
    Fail "CIBA token exchange failed with HTTP $([int]$tokenResponse.StatusCode)."
}
$tokenJson = ([string]$tokenResponse.Content) | ConvertFrom-Json -Depth 20
$accessToken = [string]$tokenJson.access_token
if ([string]::IsNullOrWhiteSpace($accessToken)) { Fail 'Token exchange returned no access_token.' }
Write-Host '[PASS] POST /token HTTP 200; token retained in memory only'

$records = [System.Collections.ArrayList]::new()

# Negative 1: documented invalid duration. This body is otherwise shaped like a
# valid mock create request so the failure is attributable to the duration gate.
$invalidDurationBody = [ordered]@{
    device = [ordered]@{ phoneNumber = '+34666666668' }
    applicationServer = [ordered]@{ ipv4Address = '0.0.0.0/0' }
    qosProfile = 'QOS_E'
    duration = 0
} | ConvertTo-Json -Depth 10 -Compress

$result = Invoke-ProbeRequest -Method 'POST' -Uri "$BaseUri/sessions" -AccessToken $accessToken -Body $invalidDurationBody
$record = Add-EvidenceRecord -Records $records -Name 'invalid_duration_rejected' -Method 'POST' -Path '/qod/v0/sessions' -Result $result -ExpectedStatuses @(400)
Write-Host "[$(if ($record.passed) { 'PASS' } else { 'FAIL' })] invalid duration -> HTTP $($result.status)"

# Negative 2: a fixed UUID that is not obtained from createSession and therefore
# cannot reference a session created by this probe.
$missingSessionId = '00000000-0000-4000-8000-000000000001'
$result = Invoke-ProbeRequest -Method 'GET' -Uri "$BaseUri/sessions/$missingSessionId" -AccessToken $accessToken
$record = Add-EvidenceRecord -Records $records -Name 'missing_session_rejected' -Method 'GET' -Path '/qod/v0/sessions/{syntheticMissingSessionId}' -Result $result -ExpectedStatuses @(404)
Write-Host "[$(if ($record.passed) { 'PASS' } else { 'FAIL' })] missing session -> HTTP $($result.status)"

# Negative 3: same harmless missing-session GET without a bearer token.
$result = Invoke-ProbeRequest -Method 'GET' -Uri "$BaseUri/sessions/$missingSessionId" -NoAuthorization
$record = Add-EvidenceRecord -Records $records -Name 'missing_authorization_rejected' -Method 'GET' -Path '/qod/v0/sessions/{syntheticMissingSessionId}' -Result $result -ExpectedStatuses @(401, 403)
Write-Host "[$(if ($record.passed) { 'PASS' } else { 'FAIL' })] no authorization -> HTTP $($result.status)"

# Negative 4: Telefonica documents a deterministic QoD mock conflict when the
# device identifier ends in 9. No successful session should be created.
$conflictBody = [ordered]@{
    device = [ordered]@{ phoneNumber = '+34666666669' }
    applicationServer = [ordered]@{ ipv4Address = '0.0.0.0/0' }
    qosProfile = 'QOS_E'
    duration = 300
} | ConvertTo-Json -Depth 10 -Compress

$result = Invoke-ProbeRequest -Method 'POST' -Uri "$BaseUri/sessions" -AccessToken $accessToken -Body $conflictBody
$record = Add-EvidenceRecord -Records $records -Name 'documented_mock_conflict_rejected' -Method 'POST' -Path '/qod/v0/sessions' -Result $result -ExpectedStatuses @(409)
Write-Host "[$(if ($record.passed) { 'PASS' } else { 'FAIL' })] documented conflict -> HTTP $($result.status)"

$allPassed = @($records | Where-Object { -not $_.passed }).Count -eq 0
$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-ciba-negative-probe-summary.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-ciba-negative-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'sandbox_mock_candidate'
    provider_api_version = 'v0.10'
    authorization_flow = 'CIBA'
    scope = $Scope
    qod_base_uri = $BaseUri
    ciba_authorization_proven = $true
    ciba_token_exchange_proven = $true
    negative_path_suite_passed = $allPassed
    raw_credentials_retained = $false
    access_token_retained = $false
    auth_req_id_retained = $false
    raw_response_bodies_retained = $false
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    operations = @($records)
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$accessToken = $null
$authReqId = $null
$ClientSecret = $null

Write-Host "Summary: $summaryPath"
if ($allPassed) {
    Write-Host 'TELEFONICA QOD CIBA NEGATIVE PATHS: PASS'
    Write-Host 'negative_path_suite_passed=true'
    Write-Host 'operator_network_qos_proven=false'
    Write-Host 'governed_camara_v1_1_provider_sandbox_proven=false'
    Write-Host 'runtime_connector_approved=false'
    Write-Host 'production_allowed=false'
    exit 0
}

Write-Host 'TELEFONICA QOD CIBA NEGATIVE PATHS: FAIL'
Write-Host 'No provider/runtime/production authority was granted.'
exit 1
