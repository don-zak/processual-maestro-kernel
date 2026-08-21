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
    $tooling = @($report.local_residue_candidates | Where-Object classification -eq 'LOCAL_TOOLING_REVIEW')
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
            parameter_count = $parameterNames.Count
            parameters = $parameterNames
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
                $supersetRows.Add([pscustomobject]@{
                    candidate_path = $candidate.path
                    latest_path = $latest.path
                    latest_contains_all_candidate_functions = $missingFunctions.Count -eq 0
                    latest_contains_all_candidate_parameters = $missingParameters.Count -eq 0
                    missing_functions_in_latest = $missingFunctions
                    missing_parameters_in_latest = $missingParameters
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
            rationale = 'Structural containment is supporting evidence only. Review behavior, side effects, command invocation, and historical use before deleting local tools.'
        })
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "local-tooling-supersession-$stamp.json"
    [ordered]@{
        source_audit = $audit.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'local structural comparison only; no deletion authority'
        tooling = @($records)
        families = @($families)
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Local tooling structural analysis completed."
    Write-Host "Tooling files: $($records.Count)"
    Write-Host "Families: $($families.Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
