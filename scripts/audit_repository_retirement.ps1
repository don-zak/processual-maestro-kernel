param(
    [string]$OutputDirectory = ".pmk-repo-audit",
    [switch]$ApplySafeLocalCleanup
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $head = (git rev-parse HEAD).Trim()
    $branch = (git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
        throw "Unable to resolve repository HEAD."
    }

    $tracked = @(git ls-files)
    if ($LASTEXITCODE -ne 0) { throw "git ls-files failed." }

    $statusLines = @(git status --porcelain=v1 --ignored)
    if ($LASTEXITCODE -ne 0) { throw "git status failed." }

    $protectedPatterns = @(
        '^alembic/versions/',
        '^tests/',
        '^docs/',
        '^qualification/',
        '^\.github/workflows/',
        '(^|/)__init__\.py$'
    )
    $localEvidencePatterns = @(
        '^\.pmk-validation/',
        '^\.pmk-local-review(?:/|\.sqlite3$)',
        '^\.coverage$',
        '^coverage\.xml$',
        '^pytest-.*\.log$',
        '^pmk-review-decisions-v\d+\.json$',
        '^cgt17_branch_retirement_audit_\d+\.json$',
        '^PMK_Transition_Handoff_Report_.*\.docx$',
        '^wave.*\.patch$',
        '^maestro-update-backup/'
    )
    $localToolingPatterns = @(
        '^Invoke-PMKRepoAudit-.*\.ps1$',
        '^Retire-Safe-CGT17Branches.*\.ps1$',
        '^crm_eval_sandbox\.py$',
        '^verify_local_password\.py$'
    )
    $auditInfrastructurePatterns = @(
        '^scripts/audit_repository_retirement\.ps1$',
        '^governance/repository_retirement_quarantine\.json$',
        '^\.pmk-repo-audit/'
    )
    $nameCandidatePattern = '(?i)(^|[._/-])(legacy|deprecated|retired|obsolete|archive|archived|backup|bak|old|unused|quarantine|generated|copy|temp|tmp)([._/-]|$)'
    $generatedResiduePattern = '(?i)(^|/)(__pycache__|\.pytest_cache|\.hypothesis|build|dist|tmp|temp)(/|$)|(^|/)[^/]+\.egg-info(/|$)|\.(pyc|pyo|log|bak|tmp|zip)$|\.bak_'
    $contentMarkers = @('deprecated', 'retired', 'obsolete', 'compatibility only', 'legacy compatibility', 'quarantine')

    function Test-PathAgainstPatterns([string]$Path, [string[]]$Patterns) {
        foreach ($pattern in $Patterns) {
            if ($Path -match $pattern) { return $true }
        }
        return $false
    }

    function Test-ProtectedPath([string]$Path) {
        return Test-PathAgainstPatterns $Path $protectedPatterns
    }

    function Test-LocalEvidencePath([string]$Path) {
        return Test-PathAgainstPatterns $Path $localEvidencePatterns
    }

    function Test-LocalToolingPath([string]$Path) {
        return Test-PathAgainstPatterns $Path $localToolingPatterns
    }

    function Test-AuditInfrastructurePath([string]$Path) {
        return Test-PathAgainstPatterns $Path $auditInfrastructurePatterns
    }

    function Get-LocalToolingMetadata([string]$Path) {
        if ($Path -match '^Invoke-PMKRepoAudit-v(?<version>\d+)(?<variant>-fixed)?\.ps1$') {
            return [pscustomobject]@{
                family = 'Invoke-PMKRepoAudit'
                version = [int]$Matches.version
                variant = if ($Matches.variant) { 'fixed' } else { 'standard' }
            }
        }
        if ($Path -match '^Retire-Safe-CGT17Branches-v(?<version>\d+)\.ps1$') {
            return [pscustomobject]@{
                family = 'Retire-Safe-CGT17Branches'
                version = [int]$Matches.version
                variant = 'standard'
            }
        }
        if ($Path -eq 'Retire-Safe-CGT17Branches-fixed.ps1') {
            return [pscustomobject]@{
                family = 'Retire-Safe-CGT17Branches'
                version = $null
                variant = 'fixed-unversioned'
            }
        }
        return [pscustomobject]@{
            family = [System.IO.Path]::GetFileNameWithoutExtension($Path)
            version = $null
            variant = 'standalone'
        }
    }

    function Get-LocalFileFingerprint([string]$Path) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return [pscustomobject]@{
                sha256 = $null
                size_bytes = $null
                line_count = $null
            }
        }
        $item = Get-Item -LiteralPath $Path
        $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        $lineCount = @(Get-Content -LiteralPath $Path -ErrorAction Stop).Count
        return [pscustomobject]@{
            sha256 = $hash
            size_bytes = [int64]$item.Length
            line_count = [int]$lineCount
        }
    }

    function Get-ReferenceEvidence([string]$Path) {
        $base = [System.IO.Path]::GetFileName($Path)
        $pathRefs = @()
        $nameRefs = @()
        if ($base) {
            $nameRefs = @(git grep -n -F -- "$base" -- ':!docs/**' ':!tests/**' 2>$null)
        }
        $pathRefs = @(git grep -n -F -- "$Path" 2>$null)
        [pscustomobject]@{
            path_reference_count = @($pathRefs).Count
            basename_reference_count = @($nameRefs).Count
            sample_path_references = @($pathRefs | Select-Object -First 5)
            sample_basename_references = @($nameRefs | Select-Object -First 5)
        }
    }

    $records = [System.Collections.Generic.List[object]]::new()

    foreach ($path in $tracked) {
        if (Test-AuditInfrastructurePath $path) { continue }

        $protected = Test-ProtectedPath $path
        $ignoredByPolicy = $false
        git check-ignore --no-index --quiet -- "$path" 2>$null
        if ($LASTEXITCODE -eq 0) { $ignoredByPolicy = $true }

        $nameCandidate = $path -match $nameCandidatePattern
        $contentHits = @()
        if (-not $protected -and (Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -lt 1048576) {
            try {
                $text = Get-Content -LiteralPath $path -Raw -ErrorAction Stop
                foreach ($marker in $contentMarkers) {
                    if ($text -match [regex]::Escape($marker)) { $contentHits += $marker }
                }
            } catch {}
        }

        if (-not ($ignoredByPolicy -or $nameCandidate -or $contentHits.Count -gt 0)) { continue }

        $refs = Get-ReferenceEvidence $path
        $classification = if ($protected) {
            'PROTECTED_HISTORY_OR_TEST'
        } elseif ($ignoredByPolicy) {
            'TRACKED_BUT_IGNORED_REVIEW'
        } elseif ($contentHits -contains 'compatibility only' -or $contentHits -contains 'legacy compatibility') {
            'COMPATIBILITY_HOLD'
        } else {
            'RETIREMENT_REVIEW'
        }

        $records.Add([pscustomobject]@{
            path = $path
            tracked = $true
            ignored_by_policy = $ignoredByPolicy
            protected = $protected
            classification = $classification
            name_candidate = $nameCandidate
            content_markers = @($contentHits)
            path_reference_count = $refs.path_reference_count
            basename_reference_count = $refs.basename_reference_count
            sample_path_references = $refs.sample_path_references
            sample_basename_references = $refs.sample_basename_references
            deletion_eligible = $false
            rationale = 'Tracked files are never auto-deleted by this audit. Review runtime references, compatibility, migrations, tests, and historical evidence first.'
        })
    }

    $localArtifacts = [System.Collections.Generic.List[object]]::new()
    foreach ($line in $statusLines) {
        if ($line.Length -lt 4) { continue }
        $code = $line.Substring(0, 2)
        $path = $line.Substring(3)
        if ($code -ne '!!' -and $code -ne '??') { continue }
        if (Test-AuditInfrastructurePath $path) { continue }

        $isIgnored = $code -eq '!!'
        $isGeneratedResidue = $path -match $generatedResiduePattern
        $isEvidence = Test-LocalEvidencePath $path
        $isTooling = Test-LocalToolingPath $path
        $isProtected = Test-ProtectedPath $path
        $tooling = if ($isTooling) { Get-LocalToolingMetadata $path } else { $null }
        $fingerprint = if ($isTooling) { Get-LocalFileFingerprint $path } else { $null }

        $eligible = $isGeneratedResidue -and -not $isEvidence -and -not $isTooling -and -not $isProtected
        $classification = if ($isEvidence) {
            'LOCAL_EVIDENCE_HOLD'
        } elseif ($isTooling) {
            'LOCAL_TOOLING_REVIEW'
        } elseif ($isProtected) {
            'LOCAL_REVIEW'
        } elseif ($eligible) {
            'SAFE_LOCAL_RESIDUE'
        } else {
            'LOCAL_REVIEW'
        }

        $localArtifacts.Add([pscustomobject]@{
            path = $path
            tracked = $false
            ignored = $isIgnored
            classification = $classification
            generated_residue = $isGeneratedResidue
            tooling_family = if ($tooling) { $tooling.family } else { $null }
            tooling_version = if ($tooling) { $tooling.version } else { $null }
            tooling_variant = if ($tooling) { $tooling.variant } else { $null }
            sha256 = if ($fingerprint) { $fingerprint.sha256 } else { $null }
            size_bytes = if ($fingerprint) { $fingerprint.size_bytes } else { $null }
            line_count = if ($fingerprint) { $fingerprint.line_count } else { $null }
            deletion_eligible = $eligible
        })
    }

    $toolingFamilySummary = [System.Collections.Generic.List[object]]::new()
    $toolingItems = @($localArtifacts | Where-Object classification -eq 'LOCAL_TOOLING_REVIEW')
    foreach ($group in ($toolingItems | Group-Object tooling_family | Sort-Object Name)) {
        $versioned = @($group.Group | Where-Object { $null -ne $_.tooling_version })
        $latestVersion = $null
        if ($versioned.Count -gt 0) {
            $latestVersion = ($versioned | Measure-Object -Property tooling_version -Maximum).Maximum
        }
        $duplicateGroups = [System.Collections.Generic.List[object]]::new()
        foreach ($hashGroup in ($group.Group | Where-Object { $_.sha256 } | Group-Object sha256)) {
            if ($hashGroup.Count -lt 2) { continue }
            $duplicateGroups.Add([pscustomobject]@{
                sha256 = $hashGroup.Name
                count = $hashGroup.Count
                paths = @($hashGroup.Group | Sort-Object path | Select-Object -ExpandProperty path)
            })
        }
        $toolingFamilySummary.Add([pscustomobject]@{
            family = $group.Name
            artifact_count = $group.Count
            latest_numeric_version_by_name = $latestVersion
            latest_numeric_paths = @($group.Group | Where-Object { $null -ne $latestVersion -and $_.tooling_version -eq $latestVersion } | Select-Object -ExpandProperty path)
            fixed_variant_paths = @($group.Group | Where-Object { $_.tooling_variant -like 'fixed*' } | Select-Object -ExpandProperty path)
            exact_duplicate_groups = @($duplicateGroups)
            paths = @($group.Group | Sort-Object tooling_version,path | Select-Object -ExpandProperty path)
            deletion_authorized = $false
            rationale = 'Exact duplicate hashes are strong local equivalence evidence, but deletion still requires choosing a canonical retained copy. Version ordering alone is not deletion authority.'
        })
    }

    $deleted = [System.Collections.Generic.List[string]]::new()
    if ($ApplySafeLocalCleanup) {
        foreach ($item in $localArtifacts) {
            if (-not $item.deletion_eligible) { continue }
            if (-not (Test-Path -LiteralPath $item.path)) { continue }
            Remove-Item -LiteralPath $item.path -Recurse -Force
            $deleted.Add($item.path)
        }
    }

    $output = Join-Path $repoRoot $OutputDirectory
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $jsonPath = Join-Path $output "repository-retirement-audit-$stamp.json"
    $csvPath = Join-Path $output "repository-retirement-candidates-$stamp.csv"
    $mdPath = Join-Path $output "repository-retirement-summary-$stamp.md"

    $report = [ordered]@{
        generated_at = (Get-Date).ToString('o')
        branch = $branch
        source_head = $head
        authority = 'local repository audit only; no staging/production authority'
        tracked_file_count = $tracked.Count
        tracked_candidates = @($records)
        local_residue_candidates = @($localArtifacts)
        local_tooling_families = @($toolingFamilySummary)
        deleted_safe_local_residue = @($deleted)
        policy = [ordered]@{
            tracked_auto_delete = $false
            migrations_tests_docs_qualification_protected = $true
            compatibility_shims_require_consumer_proof = $true
            generated_untracked_or_ignored_residue_may_be_cleaned = $true
            all_local_untracked_and_ignored_artifacts_are_inventoried = $true
            local_qualification_evidence_preserved = $true
            local_tooling_requires_manual_review = $true
            local_tooling_content_fingerprinted = $true
            tooling_version_order_is_not_deletion_authority = $true
            exact_duplicate_hash_requires_canonical_retained_copy = $true
            audit_infrastructure_excluded_from_candidates = $true
        }
    }
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
    @($records) | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# Repository Retirement / Quarantine Audit')
    $lines.Add('')
    $lines.Add("- Branch: $branch")
    $lines.Add("- HEAD: $head")
    $lines.Add("- Tracked files: $($tracked.Count)")
    $lines.Add("- Tracked candidates: $($records.Count)")
    $lines.Add("- Local artifacts: $($localArtifacts.Count)")
    $lines.Add("- Safe local residues deleted this run: $($deleted.Count)")
    $lines.Add('')
    $lines.Add('## Tracked classification totals')
    foreach ($group in ($records | Group-Object classification | Sort-Object Name)) {
        $lines.Add("- $($group.Name): $($group.Count)")
    }
    $lines.Add('')
    $lines.Add('## Local classification totals')
    foreach ($group in ($localArtifacts | Group-Object classification | Sort-Object Name)) {
        $lines.Add("- $($group.Name): $($group.Count)")
    }
    $lines.Add('')
    $lines.Add('## Local tooling families')
    foreach ($family in $toolingFamilySummary) {
        $latest = if ($null -eq $family.latest_numeric_version_by_name) { 'n/a' } else { $family.latest_numeric_version_by_name }
        $lines.Add("- $($family.family): $($family.artifact_count) artifacts; latest numeric version by name = $latest; exact duplicate groups = $(@($family.exact_duplicate_groups).Count); deletion authorized = false")
    }
    $lines.Add('')
    $lines.Add('## Safety rules')
    $lines.Add('- No tracked file is deleted automatically.')
    $lines.Add('- Alembic migrations, tests, docs, qualification evidence, workflows, and package initializers are protected by default.')
    $lines.Add('- Local qualification evidence, backups, review decisions, coverage evidence, and patch evidence are preserved from automatic cleanup.')
    $lines.Add('- Local audit/tooling scripts require manual review and are never auto-deleted.')
    $lines.Add('- Local tooling is fingerprinted by SHA-256, byte size, and line count to support supersession review.')
    $lines.Add('- Exact duplicate hashes are equivalence evidence but still require a canonical retained copy before deletion.')
    $lines.Add('- Tool version ordering is inventory evidence only and never grants deletion authority.')
    $lines.Add('- Audit/quarantine infrastructure is excluded from retirement candidacy.')
    $lines.Add('- Compatibility shims remain until consumer absence is proven.')
    $lines.Add('- Only recognized generated residue outside protected/evidence/tooling paths can be removed with -ApplySafeLocalCleanup.')
    $lines | Set-Content -LiteralPath $mdPath -Encoding UTF8

    Write-Host "Repository retirement audit completed."
    Write-Host "HEAD: $head"
    Write-Host "Tracked files: $($tracked.Count)"
    Write-Host "Tracked candidates: $($records.Count)"
    Write-Host "Local artifacts: $($localArtifacts.Count)"
    Write-Host "Local tooling families: $($toolingFamilySummary.Count)"
    Write-Host "Safe local residues deleted: $($deleted.Count)"
    Write-Host "JSON: $jsonPath"
    Write-Host "CSV:  $csvPath"
    Write-Host "MD:   $mdPath"
} finally {
    Pop-Location
}
