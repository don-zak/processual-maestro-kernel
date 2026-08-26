#requires -Version 7.2
<#
.SYNOPSIS
Proves the Telefonica QoD v0.10 extend operation in sandbox/mock mode.

.DESCRIPTION
Uses TELEFONICA_CLIENT_ID and TELEFONICA_CLIENT_SECRET from the environment,
obtains a CIBA token, creates a short QoD session, extends it, verifies it, and
deletes it. Secrets, access tokens, auth_req_id values, raw response bodies, and
session identifiers are never retained in evidence.

A passing run extends external mock interoperability evidence only. It MUST NOT
set operator network proof, governed CAMARA v1.1 provider proof, runtime
connector approval, or production authority.
#>

[CmdletBinding()]
param(
    [string]$EvidenceDirectory = './telefonica-qod-ciba-evidence',
    [string]$LoginHint = 'tel:+34666666668',
    [string]$Scope = 'dpv:RequestedServiceProvision#qod',
    [ValidateRange(1, 3600)]
    [int]$RequestedAdditionalDuration = 60,
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

function Fail { param([string]$Message) throw $Message }
function Get-Sha256Hex {
    param([AllowEmptyString()][string]$Value)
    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $hash = [Security.Cryptography.SHA256]::HashData($bytes)
    ([Convert]::ToHexString($hash)).ToLowerInvariant()
}
function Get-SanitizedPreview {
    param([AllowNull()][string]$Body)
    if ([string]::IsNullOrWhiteSpace($Body)) { return $null }
    $preview = $Body
    if ($ClientId) { $preview = $preview -replace [Regex]::Escape($ClientId), '<redacted-client-id>' }
    if ($ClientSecret) { $preview = $preview -replace [Regex]::Escape($ClientSecret), '<redacted-client-secret>' }
    $preview = $preview -replace '(?i)"?(access_token|refresh_token|id_token|client_secret|auth_req_id)"?\s*:\s*"[^"]+"', '"$1":"<redacted>"'
    $preview = $preview -replace '(?i)Bearer\s+[A-Za-z0-9._~-]+', 'Bearer <redacted>'
    if ($preview.Length -gt 2048) { $preview = $preview.Substring(0, 2048) + '...<truncated>' }
    $preview
}
function New-BasicAuthorization {
    $raw = "$ClientId`:$ClientSecret"
    "Basic $([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw)))"
}
function Invoke-FormPost {
    param([string]$Uri, [hashtable]$Form)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $r = Invoke-WebRequest -Method POST -Uri $Uri `
            -Headers @{ Authorization = (New-BasicAuthorization); Accept = 'application/json' } `
            -ContentType 'application/x-www-form-urlencoded' -Body $Form `
            -TimeoutSec $TimeoutSeconds -MaximumRedirection 0 -SkipHttpErrorCheck
        [pscustomobject]@{ status = [int]$r.StatusCode; body = [string]$r.Content; elapsed_ms = $timer.ElapsedMilliseconds }
    } finally { $timer.Stop() }
}
function Invoke-BearerRequest {
    param([string]$Method, [string]$Uri, [string]$AccessToken, [string]$Body)
    $args = @{
        Method = $Method; Uri = $Uri
        Headers = @{ Authorization = "Bearer $AccessToken"; Accept = 'application/json' }
        TimeoutSec = $TimeoutSeconds; MaximumRedirection = 0; SkipHttpErrorCheck = $true
    }
    if ($Body) { $args.ContentType = 'application/json'; $args.Body = $Body }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $r = Invoke-WebRequest @args
        [pscustomobject]@{ status = [int]$r.StatusCode; body = [string]$r.Content; elapsed_ms = $timer.ElapsedMilliseconds }
    } finally { $timer.Stop() }
}
function New-Record {
    param([string]$Name, [string]$Method, [string]$Path, [object]$Result, [int[]]$ExpectedStatuses, [hashtable]$Extra)
    $passed = $ExpectedStatuses -contains [int]$Result.status
    $record = [ordered]@{
        name = $Name; method = $Method; path = $Path
        http_status = [int]$Result.status; expected_statuses = @($ExpectedStatuses)
        passed = $passed; elapsed_ms = [long]$Result.elapsed_ms
        response_body_retained = $false
        response_body_sha256 = Get-Sha256Hex -Value ([string]$Result.body)
        sanitized_error_preview = if ($passed) { $null } else { Get-SanitizedPreview -Body ([string]$Result.body) }
    }
    foreach ($key in $Extra.Keys) { $record[$key] = $Extra[$key] }
    $record
}

if ([string]::IsNullOrWhiteSpace($ClientId)) { Fail 'TELEFONICA_CLIENT_ID is not set.' }
if ([string]::IsNullOrWhiteSpace($ClientSecret)) { Fail 'TELEFONICA_CLIENT_SECRET is not set.' }

Write-Host '==> Telefonica QoD CIBA extend probe'
Write-Host "QoD base: $BaseUri"
Write-Host "Scope: $Scope"
Write-Host '[PASS] Client credentials loaded from environment (values not printed).'

$records = [System.Collections.ArrayList]::new()
$authReqId = $null
$accessToken = $null
$sessionId = $null

$auth = Invoke-FormPost -Uri "$Gateway/bc-authorize" -Form @{ login_hint = $LoginHint; scope = $Scope }
$record = New-Record -Name 'ciba_authorization_request' -Method 'POST' -Path '/bc-authorize' -Result $auth -ExpectedStatuses @(200) -Extra @{}
[void]$records.Add($record)
Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] POST /bc-authorize HTTP $($auth.status)"
if (-not $record.passed) { if ($record.sanitized_error_preview) { Write-Host "  body: $($record.sanitized_error_preview)" } }
else {
    $json = $auth.body | ConvertFrom-Json -Depth 20
    $authReqId = [string]$json.auth_req_id
}

if ($authReqId) {
    $token = Invoke-FormPost -Uri "$Gateway/token" -Form @{ grant_type = 'urn:openid:params:grant-type:ciba'; auth_req_id = $authReqId }
    $record = New-Record -Name 'ciba_token_exchange' -Method 'POST' -Path '/token' -Result $token -ExpectedStatuses @(200) -Extra @{ auth_req_id_sha256 = (Get-Sha256Hex -Value $authReqId) }
    [void]$records.Add($record)
    Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] POST /token HTTP $($token.status)"
    if ($record.passed) { $accessToken = [string](($token.body | ConvertFrom-Json -Depth 20).access_token) }
}

if ($accessToken) {
    $createBody = ([ordered]@{
        device = [ordered]@{ phoneNumber = '+34666666668' }
        applicationServer = [ordered]@{ ipv4Address = '0.0.0.0/0' }
        qosProfile = 'QOS_E'
        duration = 300
    } | ConvertTo-Json -Depth 10 -Compress)
    $create = Invoke-BearerRequest -Method POST -Uri "$BaseUri/sessions" -AccessToken $accessToken -Body $createBody
    $record = New-Record -Name 'create_qod_session' -Method 'POST' -Path '/qod/v0/sessions' -Result $create -ExpectedStatuses @(201) -Extra @{ request_body_sha256 = (Get-Sha256Hex -Value $createBody) }
    [void]$records.Add($record)
    Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] POST /qod/v0/sessions HTTP $($create.status)"
    if ($record.passed) { $sessionId = [string](($create.body | ConvertFrom-Json -Depth 30).sessionId) }
}

if ($sessionId) {
    $escaped = [Uri]::EscapeDataString($sessionId)
    $sessionHash = Get-Sha256Hex -Value $sessionId
    $extendBody = @{ requestedAdditionalDuration = $RequestedAdditionalDuration } | ConvertTo-Json -Compress
    $extend = Invoke-BearerRequest -Method POST -Uri "$BaseUri/sessions/$escaped/extend" -AccessToken $accessToken -Body $extendBody
    $record = New-Record -Name 'extend_qod_session' -Method 'POST' -Path '/qod/v0/sessions/{sessionId}/extend' -Result $extend -ExpectedStatuses @(200) -Extra @{ session_id_sha256 = $sessionHash; request_body_sha256 = (Get-Sha256Hex -Value $extendBody) }
    [void]$records.Add($record)
    Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] POST /qod/v0/sessions/{sessionId}/extend HTTP $($extend.status)"
    if (-not $record.passed -and $record.sanitized_error_preview) { Write-Host "  body: $($record.sanitized_error_preview)" }

    $get = Invoke-BearerRequest -Method GET -Uri "$BaseUri/sessions/$escaped" -AccessToken $accessToken
    $record = New-Record -Name 'get_extended_qod_session' -Method 'GET' -Path '/qod/v0/sessions/{sessionId}' -Result $get -ExpectedStatuses @(200) -Extra @{ session_id_sha256 = $sessionHash }
    [void]$records.Add($record)
    Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] GET /qod/v0/sessions/{sessionId} HTTP $($get.status)"

    $delete = Invoke-BearerRequest -Method DELETE -Uri "$BaseUri/sessions/$escaped" -AccessToken $accessToken
    $record = New-Record -Name 'delete_qod_session' -Method 'DELETE' -Path '/qod/v0/sessions/{sessionId}' -Result $delete -ExpectedStatuses @(204,200) -Extra @{ session_id_sha256 = $sessionHash }
    [void]$records.Add($record)
    Write-Host "[$(if ($record.passed) {'PASS'} else {'FAIL'})] DELETE /qod/v0/sessions/{sessionId} HTTP $($delete.status)"
}

$required = @('ciba_authorization_request','ciba_token_exchange','create_qod_session','extend_qod_session','get_extended_qod_session','delete_qod_session')
$allPassed = $true
foreach ($name in $required) {
    $matches = @($records | Where-Object { $_.name -eq $name })
    if ($matches.Count -ne 1 -or -not $matches[0].passed) { $allPassed = $false }
}

$dir = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($dir) | Out-Null
$summaryPath = Join-Path $dir 'telefonica-qod-ciba-extend-probe-summary.json'
([ordered]@{
    schema_version = 'telefonica-qod-ciba-extend-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    provider_api_version = 'v0.10'
    authorization_flow = 'CIBA'
    scope = $Scope
    requested_additional_duration_seconds = $RequestedAdditionalDuration
    client_id_sha256 = Get-Sha256Hex -Value $ClientId
    raw_credentials_retained = $false
    access_token_retained = $false
    external_mock_extend_proven = $allPassed
    operator_network_qos_proven = $false
    governed_camara_v1_1_provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    operations = @($records)
} | ConvertTo-Json -Depth 20) | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$accessToken = $null; $authReqId = $null; $ClientSecret = $null
Write-Host "Summary: $summaryPath"
if ($allPassed) {
    Write-Host 'TELEFONICA QOD CIBA EXTEND: PASS'
    Write-Host 'external_mock_extend_proven=true'
    Write-Host 'governed_camara_v1_1_provider_sandbox_proven=false'
    Write-Host 'runtime_connector_approved=false'
    Write-Host 'production_allowed=false'
    exit 0
}
Write-Host 'TELEFONICA QOD CIBA EXTEND: FAIL'
Write-Host 'No provider/runtime/production authority was granted.'
exit 1
