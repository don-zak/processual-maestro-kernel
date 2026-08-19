#requires -Version 7.2
<#
.SYNOPSIS
Performs a safe Telefonica Open Gateway QoD CIBA + session lifecycle probe.

.DESCRIPTION
Reads TELEFONICA_CLIENT_ID and TELEFONICA_CLIENT_SECRET from the process
environment. The secret and returned access token are never written to evidence
or stdout. This probe obtains a CIBA auth_req_id, exchanges it for an access
token, then exercises the subscribed QoD Mobile Request Service Provisioning
surface using a deterministic mock-safe session lifecycle.

This proves only authenticated external sandbox/mock interoperability. It does
NOT grant provider network proof, runtime connector approval, or production
authority, and it does not alter the governed CAMARA QoD v1.1.0 contract.
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

function Invoke-BearerRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$AccessToken,
        [string]$Body
    )

    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $args = @{
            Method = $Method
            Uri = $Uri
            Headers = @{ Authorization = "Bearer $AccessToken"; Accept = 'application/json' }
            TimeoutSec = $TimeoutSeconds
            MaximumRedirection = 0
            SkipHttpErrorCheck = $true
            ErrorAction = 'Stop'
        }
        if (-not [string]::IsNullOrWhiteSpace($Body)) {
            $args.ContentType = 'application/json'
            $args.Body = $Body
        }

        $response = Invoke-WebRequest @args
        return [pscustomobject]@{
            status = [int]$response.StatusCode
            body = [string]$response.Content
            elapsed_ms = $timer.ElapsedMilliseconds
        }
    }
    finally { $timer.Stop() }
}

function Add-Record {
    param(
        [System.Collections.ArrayList]$Records,
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [object]$Result,
        [int[]]$ExpectedStatuses,
        [hashtable]$Extra
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
        sanitized_error_preview = if ($ExpectedStatuses -contains [int]$Result.status) { $null } else { Get-SanitizedPreview -Body ([string]$Result.body) }
    }
    if ($null -ne $Extra) {
        foreach ($key in $Extra.Keys) { $record[$key] = $Extra[$key] }
    }
    [void]$Records.Add($record)
    return $record
}

if ([string]::IsNullOrWhiteSpace($ClientId)) { Fail 'TELEFONICA_CLIENT_ID is not set.' }
if ([string]::IsNullOrWhiteSpace($ClientSecret)) { Fail 'TELEFONICA_CLIENT_SECRET is not set.' }
if ($LoginHint -notmatch '^(tel:\+[1-9][0-9]{7,14}|ipport:.+)$') { Fail 'LoginHint must be a tel:+E164 or ipport: value.' }
if ($Scope -notmatch '^dpv:[A-Za-z0-9]+#qod$') { Fail 'Unexpected QoD scope format.' }

$addresses = [Net.Dns]::GetHostAddresses('sandbox.opengateway.telefonica.com') |
    ForEach-Object { $_.ToString() } | Sort-Object -Unique

Write-Host '==> Telefonica QoD CIBA + session lifecycle probe'
Write-Host "Gateway: $Gateway"
Write-Host "Scope: $Scope"
Write-Host "Login hint: $LoginHint"
Write-Host '[PASS] Client credentials loaded from environment (values not printed).'
Write-Host "[PASS] DNS: $($addresses -join ', ')"

$records = [System.Collections.ArrayList]::new()
$authReqId = $null
$accessToken = $null
$tokenExpiresIn = $null
$sessionId = $null

Write-Host '==> POST /bc-authorize'
$auth = Invoke-FormPost -Uri "$Gateway/bc-authorize" -Form @{ login_hint = $LoginHint; scope = $Scope }
$authRecord = Add-Record -Records $records -Name 'ciba_authorization_request' -Method 'POST' -Path '/bc-authorize' -Result $auth -ExpectedStatuses @(200) -Extra @{}
Write-Host "[$(if ($authRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($auth.status)"
if (-not $authRecord.passed) {
    if ($authRecord.sanitized_error_preview) { Write-Host "  body: $($authRecord.sanitized_error_preview)" }
}
else {
    try {
        $authJson = $auth.body | ConvertFrom-Json -Depth 20
        if ($null -ne $authJson.PSObject.Properties['auth_req_id']) { $authReqId = [string]$authJson.auth_req_id }
    } catch { }
    if ([string]::IsNullOrWhiteSpace($authReqId)) { Fail 'CIBA authorization returned HTTP 200 without auth_req_id.' }
}

if (-not [string]::IsNullOrWhiteSpace($authReqId)) {
    Write-Host '==> POST /token'
    $token = Invoke-FormPost -Uri "$Gateway/token" -Form @{
        grant_type = 'urn:openid:params:grant-type:ciba'
        auth_req_id = $authReqId
    }
    $tokenRecord = Add-Record -Records $records -Name 'ciba_token_exchange' -Method 'POST' -Path '/token' -Result $token -ExpectedStatuses @(200) -Extra @{ auth_req_id_sha256 = (Get-Sha256Hex -Value $authReqId) }
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
    # Keep device identity aligned with the CIBA login hint used above. The
    # suffix 8 is mock-safe according to Telefonica's deterministic mock rules.
    $createBodyObject = [ordered]@{
        device = [ordered]@{
            phoneNumber = '+34666666668'
        }
        applicationServer = [ordered]@{
            ipv4Address = '0.0.0.0/0'
        }
        qosProfile = 'QOS_E'
        duration = 300
    }
    $createBody = $createBodyObject | ConvertTo-Json -Depth 10 -Compress

    Write-Host '==> POST /ogw/qod/v0/sessions'
    $create = Invoke-BearerRequest -Method 'POST' -Uri "$BaseUri/sessions" -AccessToken $accessToken -Body $createBody
    $createRecord = Add-Record -Records $records -Name 'create_qod_session' -Method 'POST' -Path '/ogw/qod/v0/sessions' -Result $create -ExpectedStatuses @(201) -Extra @{ request_body_sha256 = (Get-Sha256Hex -Value $createBody); synthetic_mock_test_data = $true }
    Write-Host "[$(if ($createRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($create.status)"
    if (-not $createRecord.passed -and $createRecord.sanitized_error_preview) {
        Write-Host "  body: $($createRecord.sanitized_error_preview)"
    }

    if ($createRecord.passed) {
        try {
            $created = $create.body | ConvertFrom-Json -Depth 30
            if ($null -ne $created.PSObject.Properties['sessionId']) {
                $candidate = [string]$created.sessionId
                if ($candidate -match '^[A-Za-z0-9._~-]{1,256}$') { $sessionId = $candidate }
            }
        } catch { }
        if ([string]::IsNullOrWhiteSpace($sessionId)) { Fail 'Create session returned HTTP 201 without a safe sessionId.' }

        $escapedSessionId = [Uri]::EscapeDataString($sessionId)
        $sessionHash = Get-Sha256Hex -Value $sessionId

        Write-Host '==> GET /ogw/qod/v0/sessions/{sessionId}'
        $getSession = Invoke-BearerRequest -Method 'GET' -Uri "$BaseUri/sessions/$escapedSessionId" -AccessToken $accessToken
        $getRecord = Add-Record -Records $records -Name 'get_qod_session' -Method 'GET' -Path '/ogw/qod/v0/sessions/{sessionId}' -Result $getSession -ExpectedStatuses @(200) -Extra @{ session_id_sha256 = $sessionHash }
        Write-Host "[$(if ($getRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($getSession.status)"
        if (-not $getRecord.passed -and $getRecord.sanitized_error_preview) { Write-Host "  body: $($getRecord.sanitized_error_preview)" }

        Write-Host '==> DELETE /ogw/qod/v0/sessions/{sessionId}'
        $deleteSession = Invoke-BearerRequest -Method 'DELETE' -Uri "$BaseUri/sessions/$escapedSessionId" -AccessToken $accessToken
        $deleteRecord = Add-Record -Records $records -Name 'delete_qod_session' -Method 'DELETE' -Path '/ogw/qod/v0/sessions/{sessionId}' -Result $deleteSession -ExpectedStatuses @(204, 200) -Extra @{ session_id_sha256 = $sessionHash }
        Write-Host "[$(if ($deleteRecord.passed) { 'PASS' } else { 'FAIL' })] HTTP $($deleteSession.status)"
        if (-not $deleteRecord.passed -and $deleteRecord.sanitized_error_preview) { Write-Host "  body: $($deleteRecord.sanitized_error_preview)" }
    }
}

$requiredNames = @('ciba_authorization_request', 'ciba_token_exchange', 'create_qod_session', 'get_qod_session', 'delete_qod_session')
$allPassed = $true
foreach ($requiredName in $requiredNames) {
    $match = @($records | Where-Object { $_.name -eq $requiredName })
    if ($match.Count -ne 1 -or -not $match[0].passed) { $allPassed = $false }
}

$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-ciba-probe-summary.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-ciba-session-lifecycle-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'sandbox_mock_candidate'
    authorization_flow = 'CIBA'
    scope = $Scope
    login_hint = $LoginHint
    client_id_sha256 = Get-Sha256Hex -Value $ClientId
    client_secret_retained = $false
    access_token_retained = $false
    raw_credentials_retained = $false
    authenticated_sandbox_reachability_proven = ($records[0].passed -and $records[1].passed)
    external_mock_sandbox_proven = $allPassed
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    operations = @($records)
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "Summary: $summaryPath"

$accessToken = $null
$authReqId = $null
$ClientSecret = $null

if ($allPassed) {
    Write-Host 'TELEFONICA QOD CIBA SESSION LIFECYCLE: PASS'
    Write-Host 'authenticated_sandbox_reachability_proven=true'
    Write-Host 'external_mock_sandbox_proven=true'
    Write-Host 'operator_network_qos_proven=false'
    Write-Host 'governed_camara_v1_1_provider_sandbox_proven=false'
    Write-Host 'runtime_connector_approved=false'
    Write-Host 'production_allowed=false'
    exit 0
}

Write-Host 'TELEFONICA QOD CIBA SESSION LIFECYCLE: FAIL'
Write-Host 'No provider/runtime/production authority was granted.'
exit 1
