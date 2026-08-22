[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputDirectory = ".pmk-repo-audit",
    [string]$Timestamp = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$outputPath = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory
} else {
    Join-Path $rootPath $OutputDirectory
}
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

function Invoke-GitText {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & git -C $rootPath @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return (($output | Out-String).Trim())
}

function Get-CompatibleRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $baseFullPath = [System.IO.Path]::GetFullPath($BasePath)
    $targetFullPath = [System.IO.Path]::GetFullPath($TargetPath)

    $getRelativePath = [System.IO.Path].GetMethod(
        'GetRelativePath',
        [type[]]@([string], [string])
    )
    if ($null -ne $getRelativePath) {
        return [System.IO.Path]::GetRelativePath($baseFullPath, $targetFullPath)
    }

    $separator = [System.IO.Path]::DirectorySeparatorChar
    if (-not $baseFullPath.EndsWith([string]$separator)) {
        $baseFullPath += $separator
    }

    $baseUri = New-Object System.Uri($baseFullPath)
    $targetUri = New-Object System.Uri($targetFullPath)
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()) -replace '/', [string]$separator
}

function Get-RelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $relative = Get-CompatibleRelativePath -BasePath $rootPath -TargetPath $Path
    return ($relative -replace "\\", "/")
}

function Get-EvidenceCategory {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    switch -Regex ($RelativePath) {
        '^pmk-review-decisions-v\d+\.json$' { return 'HISTORICAL_REVIEW_DECISION' }
        '^cgt17_branch_retirement_audit_.*\.json$' { return 'HISTORICAL_RETIREMENT_EVIDENCE' }
        '^(\.coverage|coverage\.xml)$' { return 'REGENERABLE_COVERAGE_EVIDENCE' }
        '^\.pmk-validation/' { return 'ACTIVE_LOCAL_QUALIFICATION_EVIDENCE' }
        '^\.pmk-local-review(\.sqlite3|/)' { return 'ACTIVE_LOCAL_QUALIFICATION_EVIDENCE' }
        '^local-qualification-results/' { return 'LOCAL_QUALIFICATION_RESULT_SET' }
        '^PMK_Transition_Handoff_Report_20260811_v2\.docx$' { return 'HANDOFF_EVIDENCE' }
        '^maestro-update-backup/' { return 'BACKUP_SNAPSHOT' }
        '(pytest|test[-_]?run).*\.(log|txt)$' { return 'TEST_RUN_EVIDENCE' }
        default { return 'QUALIFICATION_EVIDENCE' }
    }
}

function Get-QualificationDependency {
    param([Parameter(Mandatory = $true)][string]$Category)

    if ($Category -in @(
        'ACTIVE_LOCAL_QUALIFICATION_EVIDENCE',
        'LOCAL_QUALIFICATION_RESULT_SET',
        'REGENERABLE_COVERAGE_EVIDENCE',
        'TEST_RUN_EVIDENCE'
    )) {
        return $true
    }
    return $null
}

function Get-BackupClassification {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$File,
        [Parameter(Mandatory = $true)][string]$Sha256
    )

    $backupRoot = Join-Path $rootPath 'maestro-update-backup'
    $backupRelative = Get-CompatibleRelativePath -BasePath $backupRoot -TargetPath $File.FullName
    $currentPath = Join-Path $rootPath $backupRelative

    if (Test-Path -LiteralPath $currentPath -PathType Leaf) {
        $currentSha = (Get-FileHash -LiteralPath $currentPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($currentSha -eq $Sha256) {
            return 'EXACT_CURRENT_COPY'
        }

        return 'DIVERGENT_UNTRACKED'
    }

    if ($File.Extension -match '^\.(sql|dump|db|sqlite|sqlite3)$') {
        return 'DATABASE_BACKUP'
    }
    return 'UNIQUE_UNTRACKED'
}

function Test-JsonWithPython {
    param([Parameter(Mandatory = $true)][System.IO.FileInfo]$File)

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        return $null
    }

    $script = @'
import json, sys
path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8-sig") as fh:
        value = json.load(fh)
    if isinstance(value, list):
        root = "ARRAY"
        count = len(value)
        keys = sorted({k for item in value if isinstance(item, dict) for k in item.keys()})
        top = []
    elif isinstance(value, dict):
        root = "OBJECT"
        count = None
        keys = []
        top = sorted(value.keys())
    else:
        root = "SCALAR"
        count = None
        keys = []
        top = []
    print(json.dumps({"ok": True, "root": root, "count": count, "item_keys": keys, "top_keys": top}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
'@

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process -FilePath $python.Source `
            -ArgumentList @('-c', $script, $File.FullName) `
            -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $stdout = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
        $stderr = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue

        if ([string]::IsNullOrWhiteSpace($stdout)) {
            if (-not [string]::IsNullOrWhiteSpace($stderr)) {
                return [pscustomobject]@{ ok = $false; error = $stderr.Trim() }
            }
            return $null
        }

        try {
            $parsedOutput = $stdout | ConvertFrom-Json
            if ($process.ExitCode -ne 0 -and $parsedOutput.ok) {
                return [pscustomobject]@{ ok = $false; error = "Python exited with code $($process.ExitCode)." }
            }
            return $parsedOutput
        } catch {
            $message = if (-not [string]::IsNullOrWhiteSpace($stderr)) { $stderr.Trim() } else { $_.Exception.Message }
            return [pscustomobject]@{ ok = $false; error = $message }
        }
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-JsonMetadata {
    param([Parameter(Mandatory = $true)][System.IO.FileInfo]$File)

    $metadata = [ordered]@{
        json_parse_status = $null
        json_parse_error = $null
        json_validator = $null
        json_root_type = $null
        json_item_count = $null
        json_top_level_keys = @()
        json_item_keys = @()
    }

    if ($File.Extension -ne '.json') {
        return $metadata
    }

    $raw = Get-Content -LiteralPath $File.FullName -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        $metadata.json_parse_status = 'EMPTY'
        $metadata.json_parse_error = 'File is empty or whitespace-only.'
        $metadata.json_validator = 'NONE'
        return $metadata
    }

    try {
        $parsed = $raw | ConvertFrom-Json
        $metadata.json_parse_status = 'VALID'
        $metadata.json_validator = 'POWERSHELL'

        $trimmed = $raw.TrimStart()
        if ($trimmed.StartsWith('[')) {
            $metadata.json_root_type = 'ARRAY'
            $items = @($parsed)
            $metadata.json_item_count = $items.Count
            $itemKeys = [System.Collections.Generic.List[string]]::new()
            foreach ($item in $items) {
                if ($null -ne $item) {
                    foreach ($name in @($item.PSObject.Properties.Name)) {
                        if (-not $itemKeys.Contains($name)) {
                            $itemKeys.Add($name)
                        }
                    }
                }
            }
            $metadata.json_item_keys = @($itemKeys | Sort-Object -Unique)
        } elseif ($trimmed.StartsWith('{')) {
            $metadata.json_root_type = 'OBJECT'
            if ($null -ne $parsed) {
                $metadata.json_top_level_keys = @($parsed.PSObject.Properties.Name | Sort-Object -Unique)
            }
        } else {
            $metadata.json_root_type = 'SCALAR'
        }
    } catch {
        $powerShellError = $_.Exception.Message
        $pythonResult = Test-JsonWithPython -File $File
        if ($null -ne $pythonResult -and $pythonResult.ok) {
            $metadata.json_parse_status = 'VALID_PYTHON_FALLBACK'
            $metadata.json_parse_error = $powerShellError
            $metadata.json_validator = 'PYTHON'
            $metadata.json_root_type = $pythonResult.root
            $metadata.json_item_count = $pythonResult.count
            $metadata.json_item_keys = @($pythonResult.item_keys)
            $metadata.json_top_level_keys = @($pythonResult.top_keys)
        } else {
            $metadata.json_parse_status = 'INVALID'
            $metadata.json_parse_error = if ($null -ne $pythonResult -and $pythonResult.error) { $pythonResult.error } else { $powerShellError }
            $metadata.json_validator = if ($null -ne $pythonResult) { 'PYTHON' } else { 'POWERSHELL_ONLY' }
        }
    }
    return $metadata
}

$head = Invoke-GitText -Arguments @('rev-parse', 'HEAD')
$files = [System.Collections.Generic.List[System.IO.FileInfo]]::new()

$topLevelPatterns = @(
    'pmk-review-decisions-v*.json',
    'cgt17_branch_retirement_audit_*.json',
    '.coverage',
    'coverage.xml',
    'PMK_Transition_Handoff_Report_20260811_v2.docx',
    '*pytest*.log',
    '*pytest*.txt',
    '*test-run*.log',
    '*test-run*.txt'
)

foreach ($pattern in $topLevelPatterns) {
    Get-ChildItem -LiteralPath $rootPath -Filter $pattern -File -ErrorAction SilentlyContinue |
        ForEach-Object { $files.Add($_) }
}

$recursiveRoots = @(
    '.pmk-validation',
    '.pmk-local-review',
    'local-qualification-results',
    'maestro-update-backup'
)
foreach ($relativeRoot in $recursiveRoots) {
    $candidateRoot = Join-Path $rootPath $relativeRoot
    if (Test-Path -LiteralPath $candidateRoot -PathType Container) {
        Get-ChildItem -LiteralPath $candidateRoot -File -Recurse -Force -ErrorAction SilentlyContinue |
            ForEach-Object { $files.Add($_) }
    }
}

$localReviewDb = Join-Path $rootPath '.pmk-local-review.sqlite3'
if (Test-Path -LiteralPath $localReviewDb -PathType Leaf) {
    $files.Add((Get-Item -LiteralPath $localReviewDb -Force))
}

$uniqueFiles = @($files | Sort-Object FullName -Unique)
$records = [System.Collections.Generic.List[object]]::new()
foreach ($file in $uniqueFiles) {
    $relativePath = Get-RelativePath -Path $file.FullName
    $sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $category = Get-EvidenceCategory -RelativePath $relativePath
    $jsonMetadata = Get-JsonMetadata -File $file
    $backupClassification = $null
    if ($relativePath -like 'maestro-update-backup/*') {
        $backupClassification = Get-BackupClassification -File $file -Sha256 $sha256
    }

    $records.Add([pscustomobject][ordered]@{
        path = $relativePath
        category = $category
        size = $file.Length
        sha256 = $sha256
        created_timestamp = $file.CreationTimeUtc.ToString('o')
        modified_timestamp = $file.LastWriteTimeUtc.ToString('o')
        source_head = $null
        observed_at_head = $head
        duplicate_group = $null
        superseded_by = $null
        unique_information = $null
        runtime_dependency = $null
        qualification_dependency = Get-QualificationDependency -Category $category
        archive_candidate = ($category -in @('HISTORICAL_REVIEW_DECISION', 'HISTORICAL_RETIREMENT_EVIDENCE', 'HANDOFF_EVIDENCE', 'BACKUP_SNAPSHOT'))
        retirement_candidate = $false
        deletion_authorized = $false
        json_parse_status = $jsonMetadata.json_parse_status
        json_parse_error = $jsonMetadata.json_parse_error
        json_validator = $jsonMetadata.json_validator
        json_root_type = $jsonMetadata.json_root_type
        json_item_count = $jsonMetadata.json_item_count
        json_top_level_keys = @($jsonMetadata.json_top_level_keys)
        json_item_keys = @($jsonMetadata.json_item_keys)
        backup_classification = $backupClassification
    })
}

$duplicateIndex = 0
foreach ($group in ($records | Group-Object sha256 | Where-Object Count -gt 1)) {
    $duplicateIndex += 1
    $groupName = 'sha256-' + $duplicateIndex.ToString('D4')
    foreach ($record in $group.Group) { $record.duplicate_group = $groupName }
}

$backupRecords = @($records | Where-Object { $_.category -eq 'BACKUP_SNAPSHOT' })
$summary = [pscustomobject][ordered]@{
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    observed_at_head = $head
    artifact_count = $records.Count
    duplicate_artifact_count = @($records | Where-Object { $_.duplicate_group }).Count
    invalid_json_count = @($records | Where-Object { $_.json_parse_status -eq 'INVALID' }).Count
    empty_json_count = @($records | Where-Object { $_.json_parse_status -eq 'EMPTY' }).Count
    python_fallback_json_count = @($records | Where-Object { $_.json_parse_status -eq 'VALID_PYTHON_FALLBACK' }).Count
    unique_backup_content = @($backupRecords | Where-Object { $_.backup_classification -eq 'UNIQUE_UNTRACKED' }).Count
    divergent_backup_content = @($backupRecords | Where-Object { $_.backup_classification -eq 'DIVERGENT_UNTRACKED' }).Count
    deletion_authorized_count = @($records | Where-Object { $_.deletion_authorized }).Count
    repository_reconciliation_complete = $false
}

$manifest = [pscustomobject][ordered]@{
    schema_version = 5
    policy = [pscustomobject][ordered]@{
        mode = 'READ_ONLY_EVIDENCE_CONSOLIDATION'
        deletion_authorized = $false
        version_number_is_not_supersession_authority = $true
        exact_sha256_is_duplicate_authority = $true
        old_tracked_version_requires_historical_proof = $true
        unknown_provenance_is_null = $true
        unknown_dependency_is_null = $true
        python_fallback_stderr_isolated = $true
    }
    summary = $summary
    artifacts = @($records)
}

$jsonPath = Join-Path $outputPath ("evidence-consolidation-{0}.json" -f $Timestamp)
$csvPath = Join-Path $outputPath ("evidence-consolidation-{0}.csv" -f $Timestamp)
$markdownPath = Join-Path $outputPath ("evidence-consolidation-{0}.md" -f $Timestamp)
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding utf8
$records | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

$markdown = [System.Collections.Generic.List[string]]::new()
$markdown.Add('# Evidence Consolidation')
$markdown.Add('')
$markdown.Add("- Observed at HEAD: ``$head``")
$markdown.Add("- Artifacts: $($summary.artifact_count)")
$markdown.Add("- Exact-hash duplicate members: $($summary.duplicate_artifact_count)")
$markdown.Add("- Invalid JSON files: $($summary.invalid_json_count)")
$markdown.Add("- Empty JSON files: $($summary.empty_json_count)")
$markdown.Add("- Python-fallback JSON files: $($summary.python_fallback_json_count)")
$markdown.Add("- Unique backup content: $($summary.unique_backup_content)")
$markdown.Add("- Divergent backup content: $($summary.divergent_backup_content)")
$markdown.Add("- Deletion authorized: **false**")
$markdown.Add("- Repository reconciliation complete: **false**")
$markdown.Add('')
$markdown.Add('| Path | Category | SHA256 | Duplicate | Backup classification |')
$markdown.Add('| --- | --- | --- | --- | --- |')
foreach ($record in $records) {
    $markdown.Add("| ``$($record.path)`` | $($record.category) | ``$($record.sha256)`` | $($record.duplicate_group) | $($record.backup_classification) |")
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding utf8

[pscustomobject][ordered]@{
    Json = $jsonPath
    Csv = $csvPath
    Markdown = $markdownPath
    Summary = $summary
}