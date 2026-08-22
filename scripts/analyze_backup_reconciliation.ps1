[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$BackupDirectory = "maestro-update-backup",
    [string]$OutputDirectory = ".pmk-repo-audit",
    [string]$Timestamp = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$backupPath = Join-Path $rootPath $BackupDirectory
$outputPath = Join-Path $rootPath $OutputDirectory
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

function Invoke-GitText {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = & git -C $rootPath @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return (($output | Out-String).Trim())
}

function Get-Classification {
    param([Parameter(Mandatory = $true)][System.IO.FileInfo]$File)

    switch ($File.Name) {
        'postgres-before-update.sql' { return 'PRESERVE_DATABASE_BACKUP' }
        'docker-containers-before.txt' { return 'ARCHIVE_OPERATIONAL_SNAPSHOT' }
        'docker-images-before.txt' { return 'ARCHIVE_OPERATIONAL_SNAPSHOT' }
        'docker-volumes-before.txt' { return 'ARCHIVE_OPERATIONAL_SNAPSHOT' }
        'health-live-before.json' { return 'ARCHIVE_OPERATIONAL_SNAPSHOT' }
        'health-ready-before.json' { return 'ARCHIVE_OPERATIONAL_SNAPSHOT' }
        'git-status-before.txt' { return 'ARCHIVE_REPOSITORY_STATE_SNAPSHOT' }
        'git-remotes.txt' { return 'ARCHIVE_REPOSITORY_STATE_SNAPSHOT' }
        'previous-branch.txt' { return 'ARCHIVE_REPOSITORY_PROVENANCE' }
        'previous-sha.txt' { return 'ARCHIVE_REPOSITORY_PROVENANCE' }
        'update-started-at.txt' { return 'ARCHIVE_OPERATION_EVENT_METADATA' }
        default { return 'REVIEW_REQUIRED' }
    }
}

if (-not (Test-Path -LiteralPath $backupPath -PathType Container)) {
    throw "Backup directory not found: $backupPath"
}

$head = Invoke-GitText -Arguments @('rev-parse', 'HEAD')
$records = [System.Collections.Generic.List[object]]::new()

foreach ($file in (Get-ChildItem -LiteralPath $backupPath -File -Recurse -Force | Sort-Object FullName)) {
    $sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $classification = Get-Classification -File $file
    $relative = $file.FullName.Substring($backupPath.Length).TrimStart('\','/') -replace '\\','/'

    $historicalProof = $null
    if ($file.Name -eq 'previous-sha.txt') {
        $candidate = (Get-Content -LiteralPath $file.FullName -Raw).Trim()
        if ($candidate -match '^[0-9a-fA-F]{40}$') {
            $verified = Invoke-GitText -Arguments @('cat-file', '-e', "$candidate^{commit}")
            $historicalProof = ($null -ne $verified)
        }
    }

    $records.Add([pscustomobject][ordered]@{
        path = "$BackupDirectory/$relative"
        size = $file.Length
        sha256 = $sha256
        classification = $classification
        observed_at_head = $head
        historical_git_proof = $historicalProof
        archive_required = ($classification -like 'ARCHIVE_*' -or $classification -eq 'PRESERVE_DATABASE_BACKUP')
        deletion_authorized = $false
        repository_reconciliation_credit = $false
        reason = switch ($classification) {
            'PRESERVE_DATABASE_BACKUP' { 'Database backup is unique recovery evidence and must remain preserved or be externally archived.' }
            'ARCHIVE_OPERATIONAL_SNAPSHOT' { 'Operational pre-update state is unique historical evidence; archive before any local retirement.' }
            'ARCHIVE_REPOSITORY_STATE_SNAPSHOT' { 'Repository state snapshot is historical evidence; archive before any local retirement.' }
            'ARCHIVE_REPOSITORY_PROVENANCE' { 'Repository provenance evidence must be preserved; git proof may corroborate but does not authorize deletion.' }
            'ARCHIVE_OPERATION_EVENT_METADATA' { 'Operation timestamp metadata is historical evidence; archive before any local retirement.' }
            default { 'No safe automatic disposition is known.' }
        }
    })
}

$reviewRequired = @($records | Where-Object classification -eq 'REVIEW_REQUIRED').Count
$archiveRequired = @($records | Where-Object archive_required).Count
$databaseBackups = @($records | Where-Object classification -eq 'PRESERVE_DATABASE_BACKUP').Count

$summary = [pscustomobject][ordered]@{
    observed_at_head = $head
    backup_file_count = $records.Count
    archive_required_count = $archiveRequired
    database_backup_count = $databaseBackups
    review_required_count = $reviewRequired
    unique_backup_content_resolved = $false
    deletion_authorized_count = 0
    repository_reconciliation_complete = $false
}

$result = [pscustomobject][ordered]@{
    schema_version = 1
    policy = [pscustomobject][ordered]@{
        mode = 'READ_ONLY_BACKUP_RECONCILIATION'
        deletion_authorized = $false
        archive_before_retirement = $true
        database_backup_preservation_required = $true
        git_proof_is_not_deletion_authority = $true
    }
    summary = $summary
    files = @($records)
}

$jsonPath = Join-Path $outputPath ("backup-reconciliation-{0}.json" -f $Timestamp)
$csvPath = Join-Path $outputPath ("backup-reconciliation-{0}.csv" -f $Timestamp)
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding utf8
$records | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

[pscustomobject][ordered]@{
    Json = $jsonPath
    Csv = $csvPath
    Summary = $summary
}
