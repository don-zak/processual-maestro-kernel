[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$BackupDirectory = "maestro-update-backup",
    [string]$ArchiveRoot = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "maestro-evidence-archive"),
    [string]$Timestamp = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$backupPath = Join-Path $rootPath $BackupDirectory
if (-not (Test-Path -LiteralPath $backupPath -PathType Container)) {
    throw "Backup directory not found: $backupPath"
}

$archiveRootFull = [System.IO.Path]::GetFullPath($ArchiveRoot)
$rootFull = [System.IO.Path]::GetFullPath($rootPath)
if ($archiveRootFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "ArchiveRoot must be outside the repository root: $archiveRootFull"
}

$archiveSet = Join-Path $archiveRootFull ("maestro-update-backup-{0}" -f $Timestamp)
$payloadRoot = Join-Path $archiveSet $BackupDirectory
New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null

$records = [System.Collections.Generic.List[object]]::new()
foreach ($source in (Get-ChildItem -LiteralPath $backupPath -File -Recurse -Force | Sort-Object FullName)) {
    $relative = $source.FullName.Substring($backupPath.Length).TrimStart('\','/')
    $destination = Join-Path $payloadRoot $relative
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $source.FullName -Destination $destination -Force

    $sourceHash = (Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $archiveHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $records.Add([pscustomobject][ordered]@{
        path = ($relative -replace '\\','/')
        size = $source.Length
        source_sha256 = $sourceHash
        archive_sha256 = $archiveHash
        verified = ($sourceHash -eq $archiveHash)
    })
}

$verifiedCount = @($records | Where-Object verified).Count
$allVerified = ($records.Count -gt 0 -and $verifiedCount -eq $records.Count)
$receipt = [pscustomobject][ordered]@{
    schema_version = 1
    mode = 'COPY_VERIFY_EXTERNAL_ARCHIVE'
    created_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_repository = $rootPath
    source_backup_directory = $backupPath
    archive_set = $archiveSet
    file_count = $records.Count
    verified_count = $verifiedCount
    all_files_verified = $allVerified
    source_deleted = $false
    deletion_authorized = $false
    unique_backup_content_resolved = $allVerified
    files = @($records)
}

$receiptPath = Join-Path $archiveSet 'archive-receipt.json'
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding utf8

if (-not $allVerified) {
    throw "Archive verification failed: $verifiedCount/$($records.Count) files matched."
}

[pscustomobject][ordered]@{
    ArchiveSet = $archiveSet
    Receipt = $receiptPath
    FileCount = $records.Count
    VerifiedCount = $verifiedCount
    UniqueBackupContentResolved = $allVerified
    SourceDeleted = $false
}
