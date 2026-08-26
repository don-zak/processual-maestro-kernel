#requires -Version 7.2
<#
.SYNOPSIS
Isolates Telefonica Open Gateway QoD v0.10 missing-session behavior.

.DESCRIPTION
Uses the existing Telefonica sandbox CIBA credentials from environment variables,
obtains an access token, generates a fresh random UUID that was never created by
this probe, and requests GET /qod/v0/sessions/{sessionId}.

Telefonica's current QoD v0.10 API reference documents HTTP 404 for "Session not
found". A 404 therefore satisfies the documented negative-path expectation.
Any other status is retained as a conformance observation. In particular, HTTP
200 is recorded explicitly as a provider mock/documentation divergence and MUST
NOT be converted into provider, runtime connector, staging, or production proof.

No client secret, access token, auth_req_id, raw response body, or generated
session UUID is retained in evidence.
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

if ([string]::IsNullOrWhiteSpace($ClientId)) { Fail 'TELEFONICA_CLIENT_ID is not set.' }
if ([string]::IsNullOrWhiteSpace($ClientSecret)) { Fail 'TELEFONICA_CLIENT_SECRET is not set.' }
if ($LoginHint -notmatch '^(tel:\+[1-9][0-9]{7,14}|ipport:.+)$') { Fail 'LoginHint must be a tel:+E164 or ipport: value.' }
if ($Scope -ne 'dpv:RequestedServiceProvision#qod') { Fail 'Unexpected QoD scope.' }

Write-Host '==> Telefonica QoD missing-session isolation probe'
Write-Host "QoD base: $BaseUri"
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

# Generate a fresh UUID locally. It is never sent to createSession and is never
# retained in the evidence file, eliminating the fixed-ID collision hypothesis.
$missingSessionId = [Guid]::NewGuid().ToString()
$timer = [Diagnostics.Stopwatch]::StartNew()
try {
    $response = Invoke-WebRequest `
        -Method GET `
        -Uri "$BaseUri/sessions/$missingSessionId" `
        -Headers @{ Authorization = "Bearer $accessToken"; Accept = 'application/json' } `
        -TimeoutSec $TimeoutSeconds `
        -MaximumRedirection 0 `
        -SkipHttpErrorCheck `
        -ErrorAction Stop
}
finally {
    $timer.Stop()
}

$status = [int]$response.StatusCode
$body = [string]$response.Content
$documentedExpectationMet = ($status -eq 404)
$mockDocumentationDivergenceObserved = ($status -eq 200)

$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-missing-session-probe-summary.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-missing-session-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'sandbox_mock_candidate'
    provider_api_version = 'v0.10'
    authorization_flow = 'CIBA'
    scope = $Scope
    qod_base_uri = $BaseUri
    operation = 'getSession'
    request_path_template = '/qod/v0/sessions/{freshSyntheticSessionId}'
    synthetic_session_id_generated_fresh = $true
    synthetic_session_id_retained = $false
    session_created_by_probe = $false
    documented_missing_session_status = 404
    observed_http_status = $status
    documented_expectation_met = $documentedExpectationMet
    mock_documentation_divergence_observed = $mockDocumentationDivergenceObserved
    elapsed_ms = [long]$timer.ElapsedMilliseconds
    raw_response_body_retained = $false
    response_body_sha256 = Get-Sha256Hex -Value $body
    raw_credentials_retained = $false
    access_token_retained = $false
    auth_req_id_retained = $false
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$accessToken = $null
$authReqId = $null
$missingSessionId = $null
$ClientSecret = $null

Write-Host "Observed fresh missing-session GET -> HTTP $status"
Write-Host "Summary: $summaryPath"
if ($documentedExpectationMet) {
    Write-Host 'TELEFONICA QOD MISSING SESSION: PASS (documented 404 observed)'
    exit 0
}

if ($mockDocumentationDivergenceObserved) {
    Write-Host 'TELEFONICA QOD MISSING SESSION: DIVERGENCE (HTTP 200 observed; docs specify 404 for session not found)'
} else {
    Write-Host "TELEFONICA QOD MISSING SESSION: FAIL (unexpected HTTP $status; documented missing-session status is 404)"
}
Write-Host 'No provider/runtime/staging/production authority was granted.'
exit 1
