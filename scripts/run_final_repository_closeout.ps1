[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$ArchiveReceiptPath = "",
    [string]$OutputDirectory = ".pmk-repo-audit",
    [string]$Timestamp = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$outputPath = Join-Path $rootPath $OutputDirectory
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

function Invoke-GitLines {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = @(& git -C $rootPath @Arguments 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed" }
    return @($output)
}

function Test-KnownLocalEvidencePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $patterns = @(
        '^\.pmk-validation(?:/|$)',
        '^\.pmk-local-review(?:/|\.sqlite3$)',
        '^local-qualification-results(?:/|$)',
        '^\.coverage$',
        '^coverage\.xml$',
        '^pytest-.*\.(log|txt)$',
        '^pmk-review-decisions-v\d+\.json$',
        '^cgt17_branch_retirement_audit_\d{8}_\d{6}\.json$',
        '^PMK_Transition_Handoff_Report_.*\.docx$',
        '^wave.*\.patch$',
        '^maestro-update-backup(?:/|$)',
        '^\.pmk-repo-audit(?:/|$)'
    )
    foreach ($pattern in $patterns) {
        if ($Path -match $pattern) { return $true }
    }
    return $false
}

function Test-KnownLocalToolingPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return ($Path -match '^Invoke-PMKRepoAudit-.*\.ps1$' -or
            $Path -match '^Retire-Safe-CGT17Branches.*\.ps1$')
}

function Test-SafeGeneratedResidue {
    param([Parameter(Mandatory = $true)][string]$Path)
    return ($Path -match '(?i)(^|/)(__pycache__|\.pytest_cache|\.hypothesis|build|dist|tmp|temp)(/|$)' -or
            $Path -match '(?i)(^|/)[^/]+\.egg-info(/|$)' -or
            $Path -match '(?i)\.(pyc|pyo|log|bak|tmp|zip)$' -or
            $Path -match '(?i)\.bak_')
}

$head = (Invoke-GitLines -Arguments @('rev-parse', 'HEAD') | Select-Object -First 1).Trim()
$statusPath = Join-Path $rootPath 'governance/repository_closeout_status.json'
$quarantinePath = Join-Path $rootPath 'governance/repository_retirement_quarantine.json'
if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) { throw "Missing closeout status governance file." }
if (-not (Test-Path -LiteralPath $quarantinePath -PathType Leaf)) { throw "Missing retirement quarantine governance file." }

$closeout = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$quarantine = Get-Content -LiteralPath $quarantinePath -Raw | ConvertFrom-Json

$reviewRequired = 0
if ($closeout.phase_a.a6_tracked_candidate_review.status -ne 'CLOSED_KEEP_HOLDS') {
    $reviewRequired += 1
}
$reviewRequired += [int]$closeout.phase_a.a6_tracked_candidate_review.review_required_count

$tracked = @(Invoke-GitLines -Arguments @('ls-files'))
$unprotectedRetired = [System.Collections.Generic.List[string]]::new()
foreach ($retired in @($quarantine.local_tooling_quarantine.retired_exact_paths)) {
    if ($tracked -contains [string]$retired) { $unprotectedRetired.Add([string]$retired) }
}
foreach ($canonical in @($quarantine.local_tooling_quarantine.canonical_local_only)) {
    if ($tracked -contains [string]$canonical) { $unprotectedRetired.Add([string]$canonical) }
}

$safeResidue = [System.Collections.Generic.List[string]]::new()
$unexplained = [System.Collections.Generic.List[string]]::new()
$statusLines = @(Invoke-GitLines -Arguments @('status', '--porcelain=v1', '--ignored'))
foreach ($line in $statusLines) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) { continue }
    $code = $line.Substring(0, 2)
    if ($code -ne '??' -and $code -ne '!!') { continue }
    $path = $line.Substring(3) -replace '\\','/'

    if (Test-KnownLocalEvidencePath -Path $path) { continue }
    if (Test-KnownLocalToolingPath -Path $path) { continue }
    if (Test-SafeGeneratedResidue -Path $path) {
        $safeResidue.Add($path)
        continue
    }
    $unexplained.Add($path)
}

$uniqueBackupContent = 1
$archiveReceiptVerified = $false
$archiveReceipt = $null
if (-not [string]::IsNullOrWhiteSpace($ArchiveReceiptPath) -and
    (Test-Path -LiteralPath $ArchiveReceiptPath -PathType Leaf)) {
    $archiveReceipt = Get-Content -LiteralPath $ArchiveReceiptPath -Raw | ConvertFrom-Json
    $archiveReceiptVerified = (
        $archiveReceipt.all_files_verified -eq $true -and
        [int]$archiveReceipt.file_count -eq 11 -and
        [int]$archiveReceipt.verified_count -eq 11 -and
        $archiveReceipt.unique_backup_content_resolved -eq $true -and
        $archiveReceipt.source_deleted -eq $false -and
        $archiveReceipt.deletion_authorized -eq $false
    )
    if ($archiveReceiptVerified) { $uniqueBackupContent = 0 }
}

$exitCriteria = [pscustomobject][ordered]@{
    REVIEW_REQUIRED = $reviewRequired
    SAFE_LOCAL_RESIDUE = @($safeResidue).Count
    UNEXPLAINED_LOCAL_ARTIFACT = @($unexplained).Count
    UNPROTECTED_RETIRED_TOOL = @($unprotectedRetired).Count
    UNIQUE_BACKUP_CONTENT = $uniqueBackupContent
}

$allZero = (
    $exitCriteria.REVIEW_REQUIRED -eq 0 -and
    $exitCriteria.SAFE_LOCAL_RESIDUE -eq 0 -and
    $exitCriteria.UNEXPLAINED_LOCAL_ARTIFACT -eq 0 -and
    $exitCriteria.UNPROTECTED_RETIRED_TOOL -eq 0 -and
    $exitCriteria.UNIQUE_BACKUP_CONTENT -eq 0
)

$result = [pscustomobject][ordered]@{
    schema_version = 2
    mode = 'READ_ONLY_FINAL_REPOSITORY_RECONCILIATION_GATE'
    observed_at_head = $head
    archive_receipt_path = if ($archiveReceiptVerified) { $ArchiveReceiptPath } else { $null }
    archive_receipt_verified = $archiveReceiptVerified
    exit_criteria = $exitCriteria
    details = [pscustomobject][ordered]@{
        safe_local_residue = @($safeResidue)
        unexplained_local_artifacts = @($unexplained)
        unprotected_retired_tools = @($unprotectedRetired)
    }
    repository_reconciliation_complete = $allZero
    deletion_authorized = $false
    real_staging_qualified = $false
    production_authority_granted = $false
}

$jsonPath = Join-Path $outputPath ("final-repository-closeout-{0}.json" -f $Timestamp)
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding utf8

[pscustomobject][ordered]@{
    Json = $jsonPath
    ObservedAtHead = $head
    ExitCriteria = $exitCriteria
    ArchiveReceiptVerified = $archiveReceiptVerified
    RepositoryReconciliationComplete = $allZero
    DeletionAuthorized = $false
}
