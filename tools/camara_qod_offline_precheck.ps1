#requires -Version 7.2
<#
.SYNOPSIS
Offline precheck for the approved CAMARA Quality on Demand request plan.

.DESCRIPTION
Performs no DNS lookup, TLS connection, authentication, or provider network I/O.
It validates only the pinned governance/source contract and the approved QoD
operation mapping, then writes sanitized evidence that explicitly leaves all
provider/runtime/production authority false.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RequestPlanPath,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,

    [string]$ExpectedGovernanceVersion = 'camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee',

    [string]$ExpectedSourceRevision = '9cb179fd3b63f43d564c76689295cd681e723548'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

function Fail {
    param([string]$Message)
    throw $Message
}

function Get-Sha256Hex {
    param([AllowEmptyString()][string]$Value)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return ([Convert]::ToHexString($hash)).ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $RequestPlanPath -PathType Leaf)) {
    Fail "request plan not found: $RequestPlanPath"
}

$rawPlan = Get-Content -LiteralPath $RequestPlanPath -Raw -Encoding UTF8
$plan = $rawPlan | ConvertFrom-Json -Depth 30

if ([string]$plan.governance_version -ne $ExpectedGovernanceVersion) {
    Fail 'request plan governance_version does not match the approved governance version.'
}
if ([string]$plan.source_revision -ne $ExpectedSourceRevision) {
    Fail 'request plan source_revision does not match the pinned CAMARA source revision.'
}

$steps = @($plan.operations)
if ($steps.Count -eq 0) {
    Fail 'request plan must contain at least one operation.'
}

$operationEvidence = @()
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

    $approvalReferencePresent = $false
    if ($null -ne $step.PSObject.Properties['approval_reference']) {
        $approvalReference = [string]$step.approval_reference
        $approvalReferencePresent = -not [string]::IsNullOrWhiteSpace($approvalReference)
        if ($approvalReference -match '(?i)(token=|secret=|password=|bearer |api[_-]?key=|client[_-]?secret=)') {
            Fail "approval_reference for '$operationId' appears to contain raw secret material."
        }
    }

    if ($contract.approval_required -and -not $approvalReferencePresent) {
        Fail "'$operationId' requires approval_reference in the request plan."
    }

    $operationEvidence += [ordered]@{
        operation_id = $operationId
        method = $contract.method
        path = $contract.path
        approval_required = [bool]$contract.approval_required
        approval_reference_present = $approvalReferencePresent
        entitlement_id = $contract.entitlement
        quota_meter = $contract.quota_meter
        contract_validated = $true
    }
}

$evidencePath = [System.IO.Path]::GetFullPath($EvidenceDirectory)
[System.IO.Directory]::CreateDirectory($evidencePath) | Out-Null
$summaryPath = Join-Path $evidencePath 'camara-qod-offline-precheck-summary.json'

$summary = [ordered]@{
    schema_version = 'camara-qod-offline-precheck-r1'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    execution_mode = 'offline_precheck'
    governance_version = $ExpectedGovernanceVersion
    source_revision = $ExpectedSourceRevision
    request_plan_sha256 = Get-Sha256Hex -Value $rawPlan
    contract_precheck_passed = $true
    dns_checked = $false
    tls_checked = $false
    credentials_resolved = $false
    provider_network_proof = $false
    provider_sandbox_proven = $false
    runtime_connector_approved = $false
    request_execution_allowed = $false
    production_allowed = $false
    operations = $operationEvidence
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host ''
Write-Host 'CAMARA QoD OFFLINE PRECHECK: PASS'
Write-Host "Governance: $ExpectedGovernanceVersion"
Write-Host "Source revision: $ExpectedSourceRevision"
Write-Host "Validated operations: $($operationEvidence.Count)"
Write-Host 'DNS/TLS/auth/provider network were not evaluated.'
Write-Host 'provider_sandbox_proven=false'
Write-Host 'runtime_connector_approved=false'
Write-Host 'production_allowed=false'
Write-Host "Summary: $summaryPath"
exit 0
