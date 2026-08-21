param(
    [string]$AuditDirectory = ".pmk-repo-audit"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $sup = Get-ChildItem -LiteralPath $AuditDirectory -Filter 'local-tooling-supersession-*.json' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $sup) { throw "No local tooling supersession JSON found in $AuditDirectory." }

    $report = Get-Content -LiteralPath $sup.FullName -Raw | ConvertFrom-Json

    function Get-FunctionEvidence([string]$Path, [string]$FunctionName) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
        $lines = @(Get-Content -LiteralPath $Path)
        $escaped = [regex]::Escape($FunctionName)
        $start = $null
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*function\s+$escaped\b") {
                $start = $i
                break
            }
        }
        if ($null -eq $start) {
            return [pscustomobject]@{
                path = $Path
                function = $FunctionName
                found = $false
                body_sha256 = $null
                body_line_count = 0
                body_preview = @()
            }
        }

        $captured = [System.Collections.Generic.List[string]]::new()
        $depth = 0
        $seenOpeningBrace = $false
        for ($i = $start; $i -lt $lines.Count; $i++) {
            $line = [string]$lines[$i]
            $captured.Add($line)
            foreach ($ch in $line.ToCharArray()) {
                if ($ch -eq '{') {
                    $depth++
                    $seenOpeningBrace = $true
                } elseif ($ch -eq '}') {
                    $depth--
                }
            }
            if ($seenOpeningBrace -and $depth -eq 0) { break }
        }

        $body = [string]::Join("`n", @($captured))
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
        } finally {
            $sha.Dispose()
        }
        return [pscustomobject]@{
            path = $Path
            function = $FunctionName
            found = $true
            body_sha256 = $hash
            body_line_count = $captured.Count
            body_preview = @($captured | Select-Object -First 40)
        }
    }

    $invokeFamily = @($report.families | Where-Object family -eq 'Invoke-PMKRepoAudit')[0]
    $invokeRows = @($invokeFamily.latest_superset_checks | Where-Object { -not $_.retirement_evidence_complete })
    $functionEvidence = [System.Collections.Generic.List[object]]::new()
    foreach ($row in $invokeRows) {
        foreach ($name in @($row.missing_functions_in_latest)) {
            $evidence = Get-FunctionEvidence ([string]$row.candidate_path) ([string]$name)
            if ($null -ne $evidence) { $functionEvidence.Add($evidence) }
        }
    }

    $functionGroups = [System.Collections.Generic.List[object]]::new()
    foreach ($group in ($functionEvidence | Where-Object found | Group-Object function,body_sha256)) {
        $members = @($group.Group)
        $functionGroups.Add([pscustomobject]@{
            function = $members[0].function
            body_sha256 = $members[0].body_sha256
            implementation_count = $members.Count
            paths = @($members | Select-Object -ExpandProperty path)
            body_line_count = $members[0].body_line_count
            body_preview = $members[0].body_preview
        })
    }

    $retireFamily = @($report.families | Where-Object family -eq 'Retire-Safe-CGT17Branches')[0]
    $fixedRow = @($retireFamily.latest_superset_checks | Where-Object candidate_path -eq 'Retire-Safe-CGT17Branches-fixed.ps1')[0]

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "local-tooling-retirement-evidence-$stamp.json"
    [ordered]@{
        source_supersession = $sup.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'focused local evidence extraction only; no deletion authority'
        unresolved_invoke_candidates = @($invokeRows | Select-Object candidate_path,missing_functions_in_latest,missing_function_call_evidence)
        missing_function_implementations = @($functionEvidence)
        missing_function_implementation_groups = @($functionGroups)
        retire_safe_fixed_reference = if ($fixedRow) {
            [ordered]@{
                candidate_path = $fixedRow.candidate_path
                tracked_reference_count = $fixedRow.candidate_tracked_reference_count
                tracked_reference_samples = $fixedRow.candidate_tracked_reference_samples
                local_tooling_reference_count = $fixedRow.candidate_local_tooling_reference_count
                retirement_evidence_complete = $fixedRow.retirement_evidence_complete
            }
        } else { $null }
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Focused local tooling retirement evidence extracted."
    Write-Host "Unresolved Invoke candidates: $($invokeRows.Count)"
    Write-Host "Distinct missing function implementations: $($functionGroups.Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
