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

    function Get-BehavioralSignature([string]$Text) {
        $patterns = [ordered]@{
            git_commands = '(?im)^\s*(?:&\s*)?git\s+([^\r\n]+)'
            gh_commands = '(?im)^\s*(?:&\s*)?gh\s+([^\r\n]+)'
            pytest_commands = '(?im)^\s*(?:&\s*)?(?:python\s+-m\s+pytest|pytest)\b([^\r\n]*)'
            file_writes = '(?i)\b(Set-Content|Add-Content|Out-File|Export-Csv|ConvertTo-Json|Copy-Item|Move-Item|New-Item)\b'
            file_deletes = '(?i)\b(Remove-Item|del|erase|rmdir)\b'
            network_calls = '(?i)\b(Invoke-WebRequest|Invoke-RestMethod|curl|wget)\b'
            process_calls = '(?i)\b(Start-Process|docker|docker-compose|docker\s+compose)\b'
        }
        $result = [ordered]@{}
        foreach ($entry in $patterns.GetEnumerator()) {
            $values = @()
            foreach ($match in [regex]::Matches($Text, $entry.Value)) {
                $value = if ($match.Groups.Count -gt 1 -and $match.Groups[1].Success) {
                    $match.Groups[1].Value.Trim()
                } else {
                    $match.Groups[0].Value.Trim()
                }
                if (-not [string]::IsNullOrWhiteSpace($value)) { $values += $value }
            }
            $result[$entry.Key] = @($values | Sort-Object -Unique)
        }
        return [pscustomobject]$result
    }

    function Get-TrackedReferenceEvidence([string]$Path) {
        $base = [System.IO.Path]::GetFileName($Path)
        if ([string]::IsNullOrWhiteSpace($base)) {
            return [pscustomobject]@{ count = 0; samples = @() }
        }
        $hits = @(git grep -n -F -- "$base" 2>$null)
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
            throw "git grep failed while checking references for $Path"
        }
        return [pscustomobject]@{
            count = $hits.Count
            samples = @($hits | Select-Object -First 10)
        }
    }

    function Get-LocalToolingReferenceEvidence([string]$Path, [string[]]$ToolingPaths) {
        $base = [System.IO.Path]::GetFileName($Path)
        $hits = [System.Collections.Generic.List[string]]::new()
        foreach ($other in $ToolingPaths) {
            if ($other -eq $Path) { continue }
            if (-not (Test-Path -LiteralPath $other -PathType Leaf)) { continue }
            $otherText = Get-Content -LiteralPath $other -Raw
            if ($otherText.Contains($base)) {
                $hits.Add($other)
            }
        }
        return [pscustomobject]@{
            count = $hits.Count
            paths = @($hits)
        }
    }

    function Get-FunctionCallEvidence([string]$Text, [string[]]$FunctionNames) {
        $withoutDefinitions = [regex]::Replace($Text, '(?im)^\s*function\s+[A-Za-z0-9_-]+[^\r\n]*', '')
        $rows = [System.Collections.Generic.List[object]]::new()
        foreach ($name in $FunctionNames) {
            $escaped = [regex]::Escape($name)
            $count = [regex]::Matches($withoutDefinitions, "(?<![A-Za-z0-9_-])$escaped(?![A-Za-z0-9_-])", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase).Count
            $rows.Add([pscustomobject]@{
                function = $name
                call_count_outside_definition = $count
            })
        }
        return @($rows)
    }

    $report = Get-Content -LiteralPath $audit.FullName -Raw | ConvertFrom-Json
    $tooling = @($report.local_residue_candidates | Where-Object classification -eq 'LOCAL_TOOLING_REVIEW')
    $toolingPaths = @($tooling | Select-Object -ExpandProperty path)
    $records = [System.Collections.Generic.List[object]]::new()

    foreach ($item in $tooling) {
        $path = [string]$item.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $text = Get-Content -LiteralPath $path -Raw
        $lines = @(Get-Content -LiteralPath $path)
        $nonEmpty = @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

        $functionNames = @([regex]::Matches($text, '(?im)^\s*function\s+([A-Za-z0-9_-]+)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
        $parameterNames = @([regex]::Matches($text, '(?i)\[Parameter(?:\([^\]]*\))?\]\s*(?:\[[^\]]+\]\s*)?\$([A-Za-z_][A-Za-z0-9_]*)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
        if ($parameterNames.Count -eq 0 -and $text -match '(?is)\bparam\s*\((.*?)\)') {
            $parameterNames = @([regex]::Matches($Matches[1], '\$([A-Za-z_][A-Za-z0-9_]*)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
        }

        $normalizedLines = @()
        foreach ($line in $lines) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
            if ($trimmed.StartsWith('#')) { continue }
            $normalizedLines += ($trimmed -replace '\s+', ' ')
        }
        $normalized = [string]::Join("`n", $normalizedLines)
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $normalizedHash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
        } finally {
            $sha.Dispose()
        }

        $behavior = Get-BehavioralSignature $text
        $trackedRefs = Get-TrackedReferenceEvidence $path
        $localRefs = Get-LocalToolingReferenceEvidence $path $toolingPaths
        $functionCalls = Get-FunctionCallEvidence $text $functionNames
        $records.Add([pscustomobject]@{
            path = $path
            tooling_family = $item.tooling_family
            tooling_version = $item.tooling_version
            tooling_variant = $item.tooling_variant
            sha256 = $item.sha256
            normalized_sha256 = $normalizedHash
            size_bytes = $item.size_bytes
            line_count = $item.line_count
            nonempty_line_count = $nonEmpty.Count
            function_count = $functionNames.Count
            functions = $functionNames
            function_calls = $functionCalls
            parameter_count = $parameterNames.Count
            parameters = $parameterNames
            tracked_reference_count = $trackedRefs.count
            tracked_reference_samples = $trackedRefs.samples
            local_tooling_reference_count = $localRefs.count
            local_tooling_reference_paths = $localRefs.paths
            reference_free_in_repository_and_local_tooling = ($trackedRefs.count -eq 0 -and $localRefs.count -eq 0)
            git_commands = $behavior.git_commands
            gh_commands = $behavior.gh_commands
            pytest_commands = $behavior.pytest_commands
            file_writes = $behavior.file_writes
            file_deletes = $behavior.file_deletes
            network_calls = $behavior.network_calls
            process_calls = $behavior.process_calls
        })
    }

    $families = [System.Collections.Generic.List[object]]::new()
    foreach ($group in ($records | Group-Object tooling_family | Sort-Object Name)) {
        $versioned = @($group.Group | Where-Object { $null -ne $_.tooling_version })
        $latest = $null
        if ($versioned.Count -gt 0) {
            $maxVersion = ($versioned | Measure-Object tooling_version -Maximum).Maximum
            $latest = @($versioned | Where-Object tooling_version -eq $maxVersion | Sort-Object path | Select-Object -First 1)[0]
        }

        $supersetRows = [System.Collections.Generic.List[object]]::new()
        if ($latest) {
            foreach ($candidate in ($group.Group | Where-Object path -ne $latest.path | Sort-Object tooling_version,path)) {
                $missingFunctions = @($candidate.functions | Where-Object { $_ -notin $latest.functions })
                $missingParameters = @($candidate.parameters | Where-Object { $_ -notin $latest.parameters })
                $missingGit = @($candidate.git_commands | Where-Object { $_ -notin $latest.git_commands })
                $missingGh = @($candidate.gh_commands | Where-Object { $_ -notin $latest.gh_commands })
                $missingPytest = @($candidate.pytest_commands | Where-Object { $_ -notin $latest.pytest_commands })
                $missingWrites = @($candidate.file_writes | Where-Object { $_ -notin $latest.file_writes })
                $missingDeletes = @($candidate.file_deletes | Where-Object { $_ -notin $latest.file_deletes })
                $missingNetwork = @($candidate.network_calls | Where-Object { $_ -notin $latest.network_calls })
                $missingProcess = @($candidate.process_calls | Where-Object { $_ -notin $latest.process_calls })
                $behaviorMissingCount = @($missingGit + $missingGh + $missingPytest + $missingWrites + $missingDeletes + $missingNetwork + $missingProcess).Count
                $missingFunctionCalls = @($candidate.function_calls | Where-Object { $_.function -in $missingFunctions })
                $allMissingFunctionsUncalled = @($missingFunctionCalls | Where-Object { $_.call_count_outside_definition -gt 0 }).Count -eq 0

                $supersetRows.Add([pscustomobject]@{
                    candidate_path = $candidate.path
                    latest_path = $latest.path
                    latest_contains_all_candidate_functions = $missingFunctions.Count -eq 0
                    latest_contains_all_candidate_parameters = $missingParameters.Count -eq 0
                    latest_contains_all_candidate_behavioral_signals = $behaviorMissingCount -eq 0
                    candidate_reference_free_in_repository_and_local_tooling = $candidate.reference_free_in_repository_and_local_tooling
                    candidate_tracked_reference_count = $candidate.tracked_reference_count
                    candidate_tracked_reference_samples = $candidate.tracked_reference_samples
                    candidate_local_tooling_reference_count = $candidate.local_tooling_reference_count
                    candidate_local_tooling_reference_paths = $candidate.local_tooling_reference_paths
                    missing_functions_in_latest = $missingFunctions
                    missing_function_call_evidence = $missingFunctionCalls
                    missing_functions_are_uncalled_in_candidate = $allMissingFunctionsUncalled
                    missing_parameters_in_latest = $missingParameters
                    missing_git_commands_in_latest = $missingGit
                    missing_gh_commands_in_latest = $missingGh
                    missing_pytest_commands_in_latest = $missingPytest
                    missing_file_write_primitives_in_latest = $missingWrites
                    missing_file_delete_primitives_in_latest = $missingDeletes
                    missing_network_primitives_in_latest = $missingNetwork
                    missing_process_primitives_in_latest = $missingProcess
                    retirement_evidence_complete = (
                        $candidate.reference_free_in_repository_and_local_tooling -and
                        $missingParameters.Count -eq 0 -and
                        $behaviorMissingCount -eq 0 -and
                        ($missingFunctions.Count -eq 0 -or $allMissingFunctionsUncalled)
                    )
                    deletion_authorized = $false
                })
            }
        }

        $normalizedDuplicateGroups = [System.Collections.Generic.List[object]]::new()
        foreach ($hashGroup in ($group.Group | Group-Object normalized_sha256)) {
            if ($hashGroup.Count -lt 2) { continue }
            $normalizedDuplicateGroups.Add([pscustomobject]@{
                normalized_sha256 = $hashGroup.Name
                count = $hashGroup.Count
                paths = @($hashGroup.Group | Sort-Object path | Select-Object -ExpandProperty path)
            })
        }

        $families.Add([pscustomobject]@{
            family = $group.Name
            latest_path_by_numeric_version = if ($latest) { $latest.path } else { $null }
            normalized_duplicate_groups = @($normalizedDuplicateGroups)
            latest_superset_checks = @($supersetRows)
            deletion_authorized = $false
            rationale = 'Structural, behavioral, reference, and call-site evidence support retirement decisions but never delete files. A human must still choose the canonical retained copy and execute any local removal explicitly.'
        })
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "local-tooling-supersession-$stamp.json"
    [ordered]@{
        source_audit = $audit.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'local structural, behavioral, reference, and call-site comparison only; no deletion authority'
        tooling = @($records)
        families = @($families)
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Local tooling structural/behavioral/reference analysis completed."
    Write-Host "Tooling files: $($records.Count)"
    Write-Host "Families: $($families.Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
