#requires -Version 7.2
<#
.SYNOPSIS
Safely qualifies a real CAMARA Quality on Demand operator sandbox.

.DESCRIPTION
Dry-run by default. Live network execution requires -ExecuteLive.

The script accepts environment-variable NAMES as references for endpoint and
credential material. Raw bearer tokens, client secrets, API keys, certificates,
or provider payloads are never accepted as command-line parameters and are
never written to evidence.

The live path:
  1. validates the repository/governance boundary supplied by the caller;
  2. resolves a sandbox base URL from an environment-variable reference;
  3. enforces HTTPS and public-address DNS;
  4. resolves bearer-token or OAuth client-credentials auth from environment
     references without printing secret values;
  5. executes only the five governance-approved CAMARA QoD operations;
  6. validates HTTP success/failure behavior;
  7. writes sanitized deterministic evidence containing metadata and hashes,
     never raw request/response bodies or credentials.

This script does NOT grant runtime connector approval or production authority.

.EXAMPLE
$env:CAMARA_SANDBOX_BASE_URL = 'https://sandbox.example.test/qod/v1'
$env:CAMARA_BEARER_TOKEN = '<managed-token-value>'

pwsh ./tools/camara_qod_operator_sandbox_qualify.ps1 `
  -BaseUrlEnvVar CAMARA_SANDBOX_BASE_URL `
  -AuthMode BearerTokenReference `
  -BearerTokenEnvVar CAMARA_BEARER_TOKEN `
  -RequestPlanPath ./camara-request-plan.json `
  -EvidenceDirectory ./camara-operator-evidence

# Dry-run only; performs no network I/O.

.EXAMPLE
pwsh ./tools/camara_qod_operator_sandbox_qualify.ps1 `
  -BaseUrlEnvVar CAMARA_SANDBOX_BASE_URL `
  -AuthMode BearerTokenReference `
  -BearerTokenEnvVar CAMARA_BEARER_TOKEN `
  -RequestPlanPath ./camara-request-plan.json `
  -EvidenceDirectory ./camara-operator-evidence `
  -ExecuteLive

# Live sandbox execution. Never use production credentials.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$BaseUrlEnvVar,

    [Parameter(Mandatory = $true)]
    [ValidateSet('BearerTokenReference', 'OAuthClientCredentials')]
    [string]$AuthMode,

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$BearerTokenEnvVar,

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$TokenUrlEnvVar,

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$ClientIdEnvVar,

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$ClientSecretEnvVar,

    [string]$OAuthScope,

    [Parameter(Mandatory = $true)]
    [string]$RequestPlanPath,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [string]$ExpectedGovernanceVersion = 'camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee',

    [string]$ExpectedSourceRevision = '9cb179fd3b63f43d564c76689295cd681e723548',

    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 30,

    [switch]$ExecuteLive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ApprovedOperations = [ordered]@{
    createSession = [ordered]@{
        method = 'POST'
        path = '/sessions'
        approval_required = $true
        entitlement = 'camara_qod_session_manage'
        quota_meter = 'camara_qod_session_create'
    }
    getSession = [ordered]@{
        method = 'GET'
        path = '/sessions/{sessionId}'
        approval_required = $false
        entitlement = 'camara_qod_session_read'
        quota_meter = 'camara_qod_session_read'
    }
    deleteSession = [ordered]@{
        method = 'DELETE'
        path = '/sessions/{sessionId}'
        approval_required = $true
        entitlement = 'camara_qod_session_manage'
        quota_meter = 'camara_qod_session_delete'
    }
    extendQosSessionDuration = [ordered]@{
        method = 'POST'
        path = '/sessions/{sessionId}/extend'
        approval_required = $true
        entitlement = 'camara_qod_session_manage'
        quota_meter = 'camara_qod_session_update'
    }
    retrieveSessionsByDevice = [ordered]@{
        method = 'POST'
        path = '/retrieve-sessions'
        approval_required = $false
        entitlement = 'camara_qod_session_read'
        quota_meter = 'camara_qod_session_retrieve_by_device'
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

function Write-Pass {
    param([string]$Message)
    Write-Host "[PASS] $Message"
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Fail {
    param([string]$Message)
    throw $Message
}

function Get-ReferencedEnvironmentValue {
    param(
        [Parameter(Mandatory = $true)][string]$ReferenceName,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    if ($ReferenceName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        Fail "$Purpose reference must be an environment-variable name."
    }

    $value = [Environment]::GetEnvironmentVariable($ReferenceName, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($ReferenceName, 'User')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($ReferenceName, 'Machine')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        Fail "$Purpose reference '$ReferenceName' is not populated."
    }

    return $value
}

function Get-Sha256Hex {
    param([AllowEmptyString()][string]$Value)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return ([Convert]::ToHexString($hash)).ToLowerInvariant()
}

function Test-PrivateOrSpecialAddress {
    param([System.Net.IPAddress]$Address)

    if ([System.Net.IPAddress]::IsLoopback($Address)) {
        return $true
    }

    if ($Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
        $bytes = $Address.GetAddressBytes()
        $a = [int]$bytes[0]
        $b = [int]$bytes[1]

        if ($a -eq 10) { return $true }
        if ($a -eq 127) { return $true }
        if ($a -eq 169 -and $b -eq 254) { return $true }
        if ($a -eq 172 -and $b -ge 16 -and $b -le 31) { return $true }
        if ($a -eq 192 -and $b -eq 168) { return $true }
        if ($a -eq 0) { return $true }
        if ($a -ge 224) { return $true }
        return $false
    }

    if ($Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetworkV6) {
        if ($Address.IsIPv6LinkLocal -or $Address.IsIPv6Multicast -or $Address.IsIPv6SiteLocal) {
            return $true
        }

        $bytes = $Address.GetAddressBytes()
        # fc00::/7 unique local
        if (($bytes[0] -band 0xFE) -eq 0xFC) {
            return $true
        }
        # :: unspecified
        if ($Address.Equals([System.Net.IPAddress]::IPv6Any)) {
            return $true
        }
        return $false
    }

    return $true
}

function Assert-HttpsPublicUri {
    param(
        [Parameter(Mandatory = $true)][string]$RawUri,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $uri = $null
    if (-not [System.Uri]::TryCreate($RawUri, [System.UriKind]::Absolute, [ref]$uri)) {
        Fail "$Purpose must resolve to a valid absolute URI."
    }
    if ($uri.Scheme -ne 'https') {
        Fail "$Purpose must use HTTPS."
    }
    if (-not [string]::IsNullOrEmpty($uri.UserInfo)) {
        Fail "$Purpose must not contain userinfo."
    }
    if ($uri.IsLoopback) {
        Fail "$Purpose must not target loopback."
    }

    $addresses = [System.Net.Dns]::GetHostAddresses($uri.DnsSafeHost)
    if (-not $addresses -or $addresses.Count -eq 0) {
        Fail "$Purpose DNS resolution returned no addresses."
    }
    foreach ($address in $addresses) {
        if (Test-PrivateOrSpecialAddress -Address $address) {
            Fail "$Purpose resolved to a private, loopback, link-local, multicast, or otherwise non-public address."
        }
    }

    return [pscustomobject]@{
        Uri = $uri
        Addresses = @($addresses | ForEach-Object { $_.ToString() } | Sort-Object -Unique)
    }
}

function Get-AuthorizationHeader {
    if ($AuthMode -eq 'BearerTokenReference') {
        if ([string]::IsNullOrWhiteSpace($BearerTokenEnvVar)) {
            Fail '-BearerTokenEnvVar is required for BearerTokenReference auth.'
        }
        $token = Get-ReferencedEnvironmentValue -ReferenceName $BearerTokenEnvVar -Purpose 'bearer token'
        return "Bearer $token"
    }

    foreach ($requiredRef in @(
        @{ Name = 'TokenUrlEnvVar'; Value = $TokenUrlEnvVar },
        @{ Name = 'ClientIdEnvVar'; Value = $ClientIdEnvVar },
        @{ Name = 'ClientSecretEnvVar'; Value = $ClientSecretEnvVar }
    )) {
        if ([string]::IsNullOrWhiteSpace($requiredRef.Value)) {
            Fail "-$($requiredRef.Name) is required for OAuthClientCredentials auth."
        }
    }

    $tokenUrl = Get-ReferencedEnvironmentValue -ReferenceName $TokenUrlEnvVar -Purpose 'token URL'
    $tokenTarget = Assert-HttpsPublicUri -RawUri $tokenUrl -Purpose 'token URL'

    $clientId = Get-ReferencedEnvironmentValue -ReferenceName $ClientIdEnvVar -Purpose 'client ID'
    $clientSecret = Get-ReferencedEnvironmentValue -ReferenceName $ClientSecretEnvVar -Purpose 'client secret'

    $body = @{
        grant_type = 'client_credentials'
        client_id = $clientId
        client_secret = $clientSecret
    }
    if (-not [string]::IsNullOrWhiteSpace($OAuthScope)) {
        $body.scope = $OAuthScope
    }

    Write-Info "acquiring OAuth token from HTTPS host '$($tokenTarget.Uri.DnsSafeHost)' without logging credentials"
    $tokenResponse = Invoke-RestMethod `
        -Method Post `
        -Uri $tokenTarget.Uri.AbsoluteUri `
        -ContentType 'application/x-www-form-urlencoded' `
        -Body $body `
        -TimeoutSec $TimeoutSeconds `
        -MaximumRedirection 0 `
        -ErrorAction Stop

    $accessToken = [string]$tokenResponse.access_token
    if ([string]::IsNullOrWhiteSpace($accessToken)) {
        Fail 'OAuth token response did not contain access_token.'
    }

    return "Bearer $accessToken"
}

function Read-RequestPlan {
    if (-not (Test-Path -LiteralPath $RequestPlanPath -PathType Leaf)) {
        Fail "request plan not found: $RequestPlanPath"
    }

    $raw = Get-Content -LiteralPath $RequestPlanPath -Raw -Encoding UTF8
    $plan = $raw | ConvertFrom-Json -Depth 30

    if ($null -eq $plan.governance_version -or [string]$plan.governance_version -ne $ExpectedGovernanceVersion) {
        Fail 'request plan governance_version does not match the approved governance version.'
    }
    if ($null -eq $plan.source_revision -or [string]$plan.source_revision -ne $ExpectedSourceRevision) {
        Fail 'request plan source_revision does not match the pinned CAMARA source revision.'
    }

    $steps = @($plan.operations)
    if ($steps.Count -eq 0) {
        Fail 'request plan must contain at least one operation.'
    }

    foreach ($step in $steps) {
        $operationId = [string]$step.operation_id
        if (-not $ApprovedOperations.Contains($operationId)) {
            Fail "unapproved CAMARA QoD operation '$operationId'."
        }

        $contract = $ApprovedOperations[$operationId]
        if ($null -ne $step.method -and ([string]$step.method).ToUpperInvariant() -ne $contract.method) {
            Fail "method drift detected for '$operationId'."
        }
        if ($null -ne $step.path -and [string]$step.path -ne $contract.path) {
            Fail "path drift detected for '$operationId'."
        }

        if ($contract.approval_required) {
            $approvalReference = [string]$step.approval_reference
            if ([string]::IsNullOrWhiteSpace($approvalReference)) {
                Fail "'$operationId' requires approval_reference in the request plan."
            }
            if ($approvalReference -match '(?i)(token=|secret=|password=|bearer |api[_-]?key=|client[_-]?secret=)') {
                Fail "approval_reference for '$operationId' appears to contain raw secret material."
            }
        }
    }

    return $plan
}

function Get-SanitizedBody {
    param([object]$Step)

    $bodyFile = [string]$Step.body_file
    if ([string]::IsNullOrWhiteSpace($bodyFile)) {
        return $null
    }

    $planDirectory = Split-Path -Parent (Resolve-Path -LiteralPath $RequestPlanPath)
    $candidate = Join-Path $planDirectory $bodyFile
    $resolved = Resolve-Path -LiteralPath $candidate

    if (-not $resolved.Path.StartsWith($planDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail 'body_file must remain inside the request-plan directory.'
    }

    $raw = Get-Content -LiteralPath $resolved.Path -Raw -Encoding UTF8
    $null = $raw | ConvertFrom-Json -Depth 50

    if ($raw -match '(?i)"(access_token|client_secret|api_key|password|private_key|bearer_token)"\s*:') {
        Fail "request body file '$bodyFile' contains a prohibited secret-like field."
    }

    return $raw
}

function Resolve-OperationPath {
    param(
        [string]$PathTemplate,
        [object]$Step,
        [string]$CapturedSessionId
    )

    if ($PathTemplate -notmatch '\{sessionId\}') {
        return $PathTemplate
    }

    $sessionId = [string]$Step.session_id
    if ([string]::IsNullOrWhiteSpace($sessionId)) {
        $sessionId = $CapturedSessionId
    }
    if ([string]::IsNullOrWhiteSpace($sessionId)) {
        Fail "operation '$($Step.operation_id)' requires session_id or a prior createSession response containing sessionId."
    }
    if ($sessionId -notmatch '^[A-Za-z0-9._~-]{1,256}$') {
        Fail 'session_id contains unsafe characters.'
    }

    return $PathTemplate.Replace('{sessionId}', [System.Uri]::EscapeDataString($sessionId))
}

function New-EvidenceRecord {
    param(
        [object]$Step,
        [object]$Contract,
        [string]$ResolvedPath,
        [string]$RequestBody,
        [Nullable[int]]$StatusCode,
        [string]$ResponseBody,
        [long]$ElapsedMs,
        [string]$Outcome,
        [string]$ErrorCode
    )

    return [ordered]@{
        operation_id = [string]$Step.operation_id
        method = [string]$Contract.method
        path_template = [string]$Contract.path
        resolved_path_sha256 = Get-Sha256Hex -Value $ResolvedPath
        approval_required = [bool]$Contract.approval_required
        approval_reference_present = -not [string]::IsNullOrWhiteSpace([string]$Step.approval_reference)
        entitlement_id = [string]$Contract.entitlement
        quota_meter = [string]$Contract.quota_meter
        request_body_present = $null -ne $RequestBody
        request_body_sha256 = if ($null -ne $RequestBody) { Get-Sha256Hex -Value $RequestBody } else { $null }
        response_body_sha256 = if ($null -ne $ResponseBody) { Get-Sha256Hex -Value $ResponseBody } else { $null }
        http_status = $StatusCode
        elapsed_ms = $ElapsedMs
        outcome = $Outcome
        error_code = $ErrorCode
    }
}

Write-Step 'Validating request plan and authority boundary'
$plan = Read-RequestPlan
Write-Pass "governance version = $ExpectedGovernanceVersion"
Write-Pass "CAMARA source revision = $ExpectedSourceRevision"

Write-Step 'Resolving sandbox endpoint reference'
$baseUrlRaw = Get-ReferencedEnvironmentValue -ReferenceName $BaseUrlEnvVar -Purpose 'sandbox base URL'
$baseTarget = Assert-HttpsPublicUri -RawUri $baseUrlRaw -Purpose 'sandbox base URL'
$baseUri = $baseTarget.Uri.AbsoluteUri.TrimEnd('/')
Write-Pass "sandbox endpoint host = $($baseTarget.Uri.DnsSafeHost)"
Write-Pass "public DNS addresses = $($baseTarget.Addresses -join ', ')"

$evidencePath = [System.IO.Path]::GetFullPath($EvidenceDirectory)
[System.IO.Directory]::CreateDirectory($evidencePath) | Out-Null

$summary = [ordered]@{
    schema_version = 'camara-qod-operator-sandbox-evidence-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    execution_mode = if ($ExecuteLive) { 'live_sandbox' } else { 'dry_run' }
    governance_version = $ExpectedGovernanceVersion
    source_revision = $ExpectedSourceRevision
    provider_host = $baseTarget.Uri.DnsSafeHost
    provider_dns_addresses = $baseTarget.Addresses
    auth_mode = $AuthMode
    credential_reference_present = $true
    raw_credentials_retained = $false
    raw_request_bodies_retained = $false
    raw_response_bodies_retained = $false
    runtime_connector_approved = $false
    production_allowed = $false
    provider_network_proof = $false
    provider_sandbox_proven = $false
    operations = @()
}

if (-not $ExecuteLive) {
    Write-Step 'Dry-run validation'
    foreach ($step in @($plan.operations)) {
        $operationId = [string]$step.operation_id
        $contract = $ApprovedOperations[$operationId]
        $body = Get-SanitizedBody -Step $step
        $summary.operations += New-EvidenceRecord `
            -Step $step `
            -Contract $contract `
            -ResolvedPath $contract.path `
            -RequestBody $body `
            -StatusCode $null `
            -ResponseBody $null `
            -ElapsedMs 0 `
            -Outcome 'dry_run_validated' `
            -ErrorCode ''
        Write-Pass "$operationId contract validated"
    }

    $summaryPath = Join-Path $evidencePath 'camara-qod-operator-sandbox-summary.json'
    $summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    Write-Host ''
    Write-Host 'QUALIFICATION PRECHECK: PASS'
    Write-Host 'No network request was executed. Re-run with -ExecuteLive only in the authorized operator sandbox environment.'
    Write-Host "Summary: $summaryPath"
    exit 0
}

Write-Step 'Resolving managed authentication reference'
$authorization = Get-AuthorizationHeader
Write-Pass 'authentication material resolved without logging secret values'

$headers = @{
    Authorization = $authorization
    Accept = 'application/json'
}

$capturedSessionId = ''
$liveFailures = 0
$networkObserved = $false

foreach ($step in @($plan.operations)) {
    $operationId = [string]$step.operation_id
    $contract = $ApprovedOperations[$operationId]
    $resolvedPath = Resolve-OperationPath `
        -PathTemplate $contract.path `
        -Step $step `
        -CapturedSessionId $capturedSessionId
    $requestUri = "$baseUri$resolvedPath"
    $body = Get-SanitizedBody -Step $step

    Write-Step "Executing $operationId"
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $statusCode = $null
    $responseBody = $null
    $outcome = 'failed'
    $errorCode = ''

    try {
        $invokeArgs = @{
            Uri = $requestUri
            Method = $contract.method
            Headers = $headers
            TimeoutSec = $TimeoutSeconds
            MaximumRedirection = 0
            SkipHttpErrorCheck = $true
            ErrorAction = 'Stop'
        }
        if ($null -ne $body -and $contract.method -notin @('GET', 'DELETE')) {
            $invokeArgs.ContentType = 'application/json'
            $invokeArgs.Body = $body
        }

        $response = Invoke-WebRequest @invokeArgs
        $networkObserved = $true
        $statusCode = [int]$response.StatusCode
        $responseBody = [string]$response.Content

        if ($statusCode -ge 200 -and $statusCode -lt 300) {
            $outcome = 'success'
            Write-Pass "$operationId HTTP $statusCode"

            if ($operationId -eq 'createSession' -and -not [string]::IsNullOrWhiteSpace($responseBody)) {
                try {
                    $parsed = $responseBody | ConvertFrom-Json -Depth 50
                    $candidateSessionId = [string]$parsed.sessionId
                    if (-not [string]::IsNullOrWhiteSpace($candidateSessionId)) {
                        if ($candidateSessionId -notmatch '^[A-Za-z0-9._~-]{1,256}$') {
                            Fail 'provider createSession response returned an unsafe sessionId.'
                        }
                        $capturedSessionId = $candidateSessionId
                        Write-Info 'captured sessionId for subsequent operations without writing it to evidence'
                    }
                }
                catch {
                    Write-Info 'createSession response did not expose a reusable top-level sessionId; subsequent path operations must provide session_id in the request plan'
                }
            }
        }
        else {
            $outcome = 'http_failure'
            $errorCode = "http_$statusCode"
            $liveFailures++
            Write-Host "[FAIL] $operationId HTTP $statusCode"
        }
    }
    catch {
        $liveFailures++
        $errorCode = 'transport_or_validation_failure'
        Write-Host "[FAIL] $operationId transport/validation failure"
    }
    finally {
        $stopwatch.Stop()
    }

    $summary.operations += New-EvidenceRecord `
        -Step $step `
        -Contract $contract `
        -ResolvedPath $resolvedPath `
        -RequestBody $body `
        -StatusCode $statusCode `
        -ResponseBody $responseBody `
        -ElapsedMs $stopwatch.ElapsedMilliseconds `
        -Outcome $outcome `
        -ErrorCode $errorCode
}

$summary.provider_network_proof = $networkObserved
$summary.provider_sandbox_proven = $networkObserved -and $liveFailures -eq 0

$summaryPath = Join-Path $evidencePath 'camara-qod-operator-sandbox-summary.json'
$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Step 'Qualification result'
if ($summary.provider_sandbox_proven) {
    Write-Host 'QUALIFICATION: PASS'
    Write-Host 'Provider sandbox request/response reachability is proven for the executed operation plan.'
    Write-Host 'This does NOT grant runtime connector approval or production authority.'
    Write-Host "Summary: $summaryPath"
    exit 0
}

Write-Host 'QUALIFICATION: FAIL'
Write-Host 'Provider sandbox proof is incomplete. Review sanitized evidence and provider/network configuration.'
Write-Host 'No runtime connector or production authority was granted.'
Write-Host "Summary: $summaryPath"
exit 1
