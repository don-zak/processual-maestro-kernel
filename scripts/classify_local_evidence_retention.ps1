param(
    [string]$AuditDirectory = ".pmk-repo-audit"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $audit = Get-ChildItem -LiteralPath $AuditDirectory -Filter 'repository-retirement-audit-*.json' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $audit) { throw "No repository retirement audit JSON found in $AuditDirectory." }

    $report = Get-Content -LiteralPath $audit.FullName -Raw | ConvertFrom-Json
    $items = @($report.local_residue_candidates)
    $rows = [System.Collections.Generic.List[object]]::new()

    $regenerableCachePatterns = @(
        '^\.mypy_cache/',
        '^\.pytest_cache/',
        '^\.ruff_cache/',
        '^(?:.+/)?__pycache__/$'
    )
    # Compatibility signature retained for the audit contract; matching uses the stricter timestamp pattern below.
    $historicalRetirementEvidenceLegacyPattern = '^cgt17_branch_retirement_audit_\d+\.json$'
    $historicalRetirementEvidencePattern = '^cgt17_branch_retirement_audit_[0-9]{8}_[0-9]{6}[.]json$'

    foreach ($item in $items) {
        $path = [string]$item.path
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        $normalized = $path.Replace('\\','/')

        $category = 'REVIEW_REQUIRED'
        $retention = 'HOLD'
        $reason = 'No deterministic retention policy matched.'
        $regenerable = $false
        $archive_candidate = $false
        $deletion_candidate = $false

        $isRegenerableCache = $false
        foreach ($pattern in $regenerableCachePatterns) {
            if ($normalized -match $pattern) {
                $isRegenerableCache = $true
                break
            }
        }

        if ($normalized -match '^\.coverage$' -or $normalized -match '^coverage\.xml$') {
            $category = 'REGENERABLE_COVERAGE_EVIDENCE'
            $retention = 'REGENERABLE'
            $reason = 'Coverage runtime output can be reproduced from tests; keep only while it is needed as local qualification evidence.'
            $regenerable = $true
        } elseif ($isRegenerableCache) {
            $category = 'REGENERABLE_TOOL_CACHE'
            $retention = 'SAFE_TO_REGENERATE'
            $reason = 'Tool/runtime cache is generated state and can be recreated from source and tooling.'
            $regenerable = $true
            $deletion_candidate = $true
        } elseif ($normalized -match '^\.venv/$') {
            $category = 'REGENERABLE_LOCAL_ENVIRONMENT'
            $retention = 'SAFE_TO_REGENERATE'
            $reason = 'Local virtual environment is reproducible from dependency declarations and should stay outside repository authority.'
            $regenerable = $true
            $deletion_candidate = $true
        } elseif ($normalized -match '^\.pmk-local-review(?:/|\.sqlite3$)' -or $normalized -match '^\.pmk-validation/') {
            $category = 'ACTIVE_LOCAL_QUALIFICATION_EVIDENCE'
            $retention = 'PRESERVE'
            $reason = 'Current local review/validation state may be needed to reproduce or audit qualification results.'
        } elseif ($normalized -match $historicalRetirementEvidencePattern) {
            $category = 'HISTORICAL_RETIREMENT_EVIDENCE'
            $retention = 'ARCHIVE_CANDIDATE'
            $reason = 'Timestamped branch-retirement evidence is historical and should be consolidated before deletion.'
            $archive_candidate = $true
        } elseif ($normalized -match '^pmk-review-decisions-v\d+\.json$') {
            $category = 'HISTORICAL_REVIEW_DECISION'
            $retention = 'ARCHIVE_CANDIDATE'
            $reason = 'Versioned review decisions are historical evidence; consolidate newest/final state before retiring earlier copies.'
            $archive_candidate = $true
        } elseif ($normalized -match '^pytest-.*\.log$') {
            $category = 'TEST_RUN_EVIDENCE'
            $retention = 'ARCHIVE_CANDIDATE'
            $reason = 'Test execution logs are evidence, not runtime state; archive after qualification closeout rather than deleting blindly.'
            $archive_candidate = $true
        } elseif ($normalized -match '^local-qualification-results/') {
            $category = 'LOCAL_QUALIFICATION_RESULT_SET'
            $retention = 'PRESERVE'
            $reason = 'Named qualification result set may contain acceptance evidence and requires content review before archival.'
        } elseif ($normalized -match '^wave.*\.patch$') {
            $category = 'PATCH_PROVENANCE_EVIDENCE'
            $retention = 'VERIFY_APPLIED_THEN_RETIRE'
            $reason = 'Patch files are removable only after proving their hunks are already represented in tracked history or superseded.'
        } elseif ($normalized -match '^PMK_Transition_Handoff_Report_.*\.docx$') {
            $category = 'HANDOFF_EVIDENCE'
            $retention = 'ARCHIVE_CANDIDATE'
            $reason = 'Transition handoff is documentation evidence and should be archived outside the working root before deletion.'
            $archive_candidate = $true
        } elseif ($normalized -match '^maestro-update-backup/') {
            $category = 'BACKUP_SNAPSHOT'
            $retention = 'ARCHIVE_CANDIDATE'
            $reason = 'Backup material should be validated and moved outside the active repository root rather than deleted by audit tooling.'
            $archive_candidate = $true
        } elseif ($normalized -match '^Invoke-PMKRepoAudit-v20\.ps1$' -or $normalized -match '^Retire-Safe-CGT17Branches-v3\.ps1$') {
            $category = 'CANONICAL_LOCAL_OPERATOR_TOOL'
            $retention = 'PRESERVE'
            $reason = 'Current canonical local operator tooling retained for repository review closeout.'
        }

        $rows.Add([pscustomobject]@{
            path = $path
            category = $category
            retention = $retention
            reason = $reason
            regenerable = $regenerable
            archive_candidate = $archive_candidate
            deletion_candidate = $deletion_candidate
            deletion_authorized = $false
        })
    }

    $summary = @($rows | Group-Object category | Sort-Object Name | ForEach-Object {
        [pscustomobject]@{ category = $_.Name; count = $_.Count }
    })

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "local-evidence-retention-$stamp.json"
    [ordered]@{
        source_audit = $audit.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'local evidence retention classification only; no deletion authority'
        cache_patterns = $regenerableCachePatterns
        historical_retirement_evidence_legacy_pattern = $historicalRetirementEvidenceLegacyPattern
        historical_retirement_evidence_pattern = $historicalRetirementEvidencePattern
        summary = $summary
        items = @($rows)
    } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Local evidence retention classification completed."
    Write-Host "Items classified: $($rows.Count)"
    foreach ($entry in $summary) {
        Write-Host "$($entry.category): $($entry.count)"
    }
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
