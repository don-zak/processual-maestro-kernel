#requires -Version 7.2
<#
.SYNOPSIS
Performs a safe Telefonica Open Gateway QoD CIBA authentication probe.

.DESCRIPTION
Reads TELEFONICA_CLIENT_ID and TELEFONICA_CLIENT_SECRET from the process
environment. The secret and returned access token are never written to evidence
or stdout. This probe obtains a CIBA auth_req_id, exchanges it for an access
token, and then performs a read-only QoS profile probe.

This proves only authenticated external sandbox reachability/interoperability.
It does NOT grant provider network proof, runtime connector approval, or
production authority, and it does not alter the governed CAMARA QoD v1.1.0
contract.
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
$BaseUri = "$Gateway/ogw/qod/v0"
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

function Get-SanitizedPreview {
    param([AllowNull()][string]$Body)
    if ([string]::IsNullOrWhiteSpace($Body)) { return $null }
    $preview = $Body
    if (-not [string]::IsNullOrWhiteSpace($ClientId)) {
        $preview = $preview -replace [Regex]::Escape($ClientId), '<redacted-client-id>'
    }
    if (-not [string]::IsNullOrWhiteSpace($ClientSecret)) {
        $preview = $preview -replace [Regex]::Escape($ClientSecret), '<redacted-client-secret>'
    }
    $preview = $preview -replace '(?i)"?(access_token|refresh_token|id_token|client_secret)"?\s*:\s*"[^"]+"', '"$1":"<redacted>"'
    $preview = $preview -replace '(?i)Bearer\s+[A-Za-z0-9._~-]+', 'Bearer <redacted>'
    if ($preview.Length -gt 2048) { $preview = $preview.Substring(0, 2048) + '...<truncated>' }
    return $preview
}

function New-BasicAuthorization {
    $raw = "$ClientId`:$ClientSecret"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw))
    return "Basic $encoded"
}

function Invoke-FormPost {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][hashtable]$Form
    )

    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest `
            -Method POST `
            -Uri $Uri `
            -Headers @{ Authorization = (New-BasicAuthorization); Accept = 'application/json' } `
            -ContentType 'application/x-www-form-urlencoded' `
            -Body $Form `
            -TimeoutSec $TimeoutSeconds `
            -MaximumRedirection 0 `
            -SkipHttpErrorCheck `
            -ErrorAction Stop

        return [pscustomobject]@{
            status = [int]$response.StatusCode
            body = [string]$response.Content
            elapsed_ms = $timer.ElapsedMilliseconds
        }
    }
    finally { $timer.Stop() }
}

function Invoke-BearerGet {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$AccessToken
    )

    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest `
            -Method GET `
            -Uri $Uri `
            -Headers @{ Authorization = "Bearer $AccessToken"; Accept = 'application/json' } `
            -TimeoutSec $TimeoutSeconds `
            -MaximumRedirection 0 `
            -SkipHttpErrorCheck `
            -ErrorAction Stop

        return [pscustomobject]@{
            status = [int]$response.StatusCode
            body = [string]$response.Content
            elapsed_ms = $timer.ElapsedMilliseconds
        }
    }
    finally { $timer.Stop() }
}

if ([string]::IsNullOrWhiteSpace($ClientId)) { Fail 'TELEFONICA_CLIENT_ID is not set.' }
if ([string]::IsNullOrWhiteSpace($ClientSecret)) { Fail 'TELEFONICA_CLIENT_SECRET is not set.' }
if ($LoginHint -notmatch '^(tel:\+[1-9][0-9]{7,14}|ipport:.+)$') { Fail 'LoginHint must be a tel:+E164 or ipport: value.' }
if ($Scope -notmatch '^dpv:[A-Za-z0-9]+#qod$') { Fail 'Unexpected QoD scope format.' }

$addresses = [Net.Dns]::GetHostAddresses('sandbox.opengateway.telefonica.com') |
    ForEach-Object { $_.ToString() } | Sort-Object -Unique

Write-Host '==> Telefonica QoD CIBA authentication probe'
Write-Host "Gateway: $Gateway"
Write-Host "Scope: $Scope"
Write-Host "Login hint: $LoginHint"
Write-Host '[PASS] Client credentials loaded from environment (values not printed).'
Write-Host "[PASS] DNS: $($addresses -join ', ')"

$records = @()
$authReqId = $null
$accessToken = $null
$tokenExpiresIn = $null

Write-Host '==> POST /bc-authorize'
$auth = Invoke-FormPost -Uri "$Gateway/bc-authorize" -Form @{ login_hint = $LoginHint; scope = $Scope }
$authRecord = [ordered]@{
    name = 'ciba_authorization_request'
    method = 'POST'
    path = '/bc-authorize'
    http_status = $auth.status
    passed = ($auth.status -eq 200)
    elapsed_ms = $auth.elapsed_ms
    response_body_retained = $false
    response_body_sha256 = Get-Sha256Hex -Value $auth.body
    sanitized_error_preview = if ($auth.status -eq 200) { $null } else { Get-SanitizedPreview -Body $auth.body }
}
$records += $authRecord
Write-Host "[$(if ($authRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($auth.status)"
if (-not $authRecord.passed) {
    if ($authRecord.sanitized_error_preview) { Write-Host "  body: $($authRecord.sanitized_error_preview)" }
}
else {
    try {
        $authJson = $auth.body | ConvertFrom-Json -Depth 20
        if ($null -ne $authJson.PSObject.Properties['auth_req_id']) {
            $authReqId = [string]$authJson.auth_req_id
        }
    } catch { }
    if ([string]::IsNullOrWhiteSpace($authReqId)) { Fail 'CIBA authorization returned HTTP 200 without auth_req_id.' }
}

if (-not [string]::IsNullOrWhiteSpace($authReqId)) {
    Write-Host '==> POST /token'
    $token = Invoke-FormPost -Uri "$Gateway/token" -Form @{
        grant_type = 'urn:openid:params:grant-type:ciba'
        auth_req_id = $authReqId
    }
    $tokenRecord = [ordered]@{
        name = 'ciba_token_exchange'
        method = 'POST'
        path = '/token'
        http_status = $token.status
        passed = ($token.status -eq 200)
        elapsed_ms = $token.elapsed_ms
        auth_req_id_sha256 = Get-Sha256Hex -Value $authReqId
        response_body_retained = $false
        response_body_sha256 = Get-Sha256Hex -Value $token.body
        sanitized_error_preview = if ($token.status -eq 200) { $null } else { Get-SanitizedPreview -Body $token.body }
    }
    $records += $tokenRecord
    Write-Host "[$(if ($tokenRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($token.status)"
    if (-not $tokenRecord.passed) {
        if ($tokenRecord.sanitized_error_preview) { Write-Host "  body: $($tokenRecord.sanitized_error_preview)" }
    }
    else {
        try {
            $tokenJson = $token.body | ConvertFrom-Json -Depth 20
            if ($null -ne $tokenJson.PSObject.Properties['access_token']) { $accessToken = [string]$tokenJson.access_token }
            if ($null -ne $tokenJson.PSObject.Properties['expires_in']) { $tokenExpiresIn = [int]$tokenJson.expires_in }
        } catch { }
        if ([string]::IsNullOrWhiteSpace($accessToken)) { Fail 'Token endpoint returned HTTP 200 without access_token.' }
        Write-Host "[PASS] Access token obtained in-memory only; expires_in=$tokenExpiresIn"
    }
}

if (-not [string]::IsNullOrWhiteSpace($accessToken)) {
    Write-Host '==> GET /ogw/qod/v0/qos-profiles/QOS_E'
    $qos = Invoke-BearerGet -Uri "$BaseUri/qos-profiles/QOS_E" -AccessToken $accessToken
    $qosRecord = [ordered]@{
        name = 'get_qos_profile_qos_e'
        method = 'GET'
        path = '/ogw/qod/v0/qos-profiles/QOS_E'
        http_status = $qos.status
        passed = ($qos.status -eq 200)
        elapsed_ms = $qos.elapsed_ms
        response_body_retained = $false
        response_body_sha256 = Get-Sha256Hex -Value $qos.body
        sanitized_error_preview = if ($qos.status -eq 200) { $null } else { Get-SanitizedPreview -Body $qos.body }
    }
    $records += $qosRecord
    Write-Host "[$(if ($qosRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($qos.status)"
    if (-not $qosRecord.passed -and $qosRecord.sanitized_error_preview) {
        Write-Host "  body: $($qosRecord.sanitized_error_preview)"
    }
}

$allPassed = ($records.Count -eq 3 -and @($records | Where-Object { -not $_.passed }).Count -eq 0)
$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-ciba-probe-summary.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-ciba-probe-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'sandbox'
    authorization_flow = 'CIBA'
    scope = $Scope
    login_hint = $LoginHint
    client_id_sha256 = Get-Sha256Hex -Value $ClientId
    client_secret_retained = $false
    access_token_retained = $false
    raw_credentials_retained = $false
    authenticated_sandbox_reachability_proven = $allPassed
    external_mock_sandbox_proven = $allPassed
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    operations = $records
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "Summary: $summaryPath"

$accessToken = $null
$authReqId = $null
$ClientSecret = $null

if ($allPassed) {
    Write-Host 'TELEFONICA QOD CIBA PROBE: PASS'
    Write-Host 'authenticated_sandbox_reachability_proven=true'
    Write-Host 'operator_network_qos_proven=false'
    Write-Host 'governed_camara_v1_1_provider_sandbox_proven=false'
    Write-Host 'runtime_connector_approved=false'
    Write-Host 'production_allowed=false'
    exit 0
}

Write-Host 'TELEFONICA QOD CIBA PROBE: FAIL'
Write-Host 'No provider/runtime/production authority was granted.'
exit 1
