#requires -Version 7.2
<#
.SYNOPSIS
Diagnoses Telefonica Open Gateway QoD mock routing without creating a session.

.DESCRIPTION
Uses the documented public mock convenience token only. Performs read-only GET
requests against the exact current QoD v0 reference paths and records a short,
sanitized response preview to distinguish route/access-policy failures from
payload failures. No user credentials are accepted or retained.
#>

[CmdletBinding()]
param(
    [string]$EvidenceDirectory = './telefonica-qod-mock-evidence',
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Gateway = 'https://sandbox.opengateway.telefonica.com/apigateway'
$BaseUri = "$Gateway/ogw/qod/v0"
$MockToken = 'mock_sandbox_access_token'

function Get-Sha256Hex {
    param([AllowEmptyString()][string]$Value)
    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $hash = [Security.Cryptography.SHA256]::HashData($bytes)
    return ([Convert]::ToHexString($hash)).ToLowerInvariant()
}

function Get-SanitizedPreview {
    param([AllowNull()][string]$Body)

    if ([string]::IsNullOrWhiteSpace($Body)) {
        return $null
    }

    $preview = $Body
    $preview = $preview -replace [Regex]::Escape($MockToken), '<redacted-mock-token>'
    $preview = $preview -replace '(?i)Bearer\s+[A-Za-z0-9._~-]+', 'Bearer <redacted>'
    $preview = $preview -replace '(?i)(client_secret|access_token|refresh_token|password)\s*[=:]\s*[^\s,}\"]+', '$1=<redacted>'

    if ($preview.Length -gt 2048) {
        $preview = $preview.Substring(0, 2048) + '...<truncated>'
    }
    return $preview
}

function Get-HeaderValue {
    param(
        [Parameter(Mandatory = $true)]$Headers,
        [Parameter(Mandatory = $true)][string]$Name
    )

    try {
        $value = $Headers[$Name]
        if ($null -eq $value) {
            return $null
        }
        return [string]($value -join ', ')
    }
    catch {
        return $null
    }
}

function Invoke-Probe {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri
    )

    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest `
            -Method GET `
            -Uri $Uri `
            -Headers @{ Authorization = "Bearer $MockToken"; Accept = 'application/json' } `
            -TimeoutSec $TimeoutSeconds `
            -MaximumRedirection 0 `
            -SkipHttpErrorCheck `
            -ErrorAction Stop

        $body = [string]$response.Content
        $contentType = Get-HeaderValue -Headers $response.Headers -Name 'Content-Type'
        $server = Get-HeaderValue -Headers $response.Headers -Name 'Server'

        return [ordered]@{
            name = $Name
            method = 'GET'
            uri = $Uri
            http_status = [int]$response.StatusCode
            elapsed_ms = $timer.ElapsedMilliseconds
            content_type = $contentType
            server = $server
            response_body_sha256 = Get-Sha256Hex -Value $body
            sanitized_body_preview = Get-SanitizedPreview -Body $body
        }
    }
    finally {
        $timer.Stop()
    }
}

Write-Host '==> Telefonica QoD mock route probe'
Write-Host "Gateway: $Gateway"
Write-Host 'Credential mode: documented public mock convenience token'
Write-Host 'No session will be created.'

$addresses = [Net.Dns]::GetHostAddresses('sandbox.opengateway.telefonica.com') |
    ForEach-Object { $_.ToString() } |
    Sort-Object -Unique
Write-Host "[PASS] DNS: $($addresses -join ', ')"

$probes = @(
    Invoke-Probe -Name 'qos_profile_qos_e' -Uri "$BaseUri/qos-profiles/QOS_E"
    Invoke-Probe -Name 'qos_profiles_collection' -Uri "$BaseUri/qos-profiles"
)

foreach ($probe in $probes) {
    Write-Host "[$($probe.http_status)] $($probe.name)"
    if ($null -ne $probe.sanitized_body_preview) {
        Write-Host "  body: $($probe.sanitized_body_preview)"
    }
}

$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
[IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'telefonica-qod-v0-mock-route-probe.json'

$summary = [ordered]@{
    schema_version = 'telefonica-qod-v0-mock-route-probe-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    provider = 'telefonica_open_gateway'
    environment = 'public_mock_sandbox'
    base_uri = $BaseUri
    user_credentials_used = $false
    session_created = $false
    provider_sandbox_proven = $false
    runtime_connector_approved = $false
    production_allowed = $false
    dns_addresses = @($addresses)
    probes = $probes
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "Summary: $summaryPath"

if (@($probes | Where-Object { $_.http_status -eq 200 }).Count -gt 0) {
    Write-Host 'TELEFONICA QOD MOCK ROUTE PROBE: PARTIAL PASS'
    exit 0
}

Write-Host 'TELEFONICA QOD MOCK ROUTE PROBE: ROUTE/ACCESS BLOCKED'
exit 2
