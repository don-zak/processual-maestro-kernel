param(
    [string]$AuditDirectory = ".pmk-repo-audit"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $evidence = Get-ChildItem -LiteralPath $AuditDirectory -Filter 'local-tooling-retirement-evidence-*.json' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $evidence) { throw "No focused retirement evidence JSON found in $AuditDirectory." }

    $report = Get-Content -LiteralPath $evidence.FullName -Raw | ConvertFrom-Json
    $referenceExclusions = @(
        ':!scripts/audit_repository_retirement.ps1',
        ':!scripts/analyze_local_tooling_supersession.ps1',
        ':!scripts/extract_local_tooling_retirement_evidence.ps1',
        ':!scripts/analyze_legacy_function_semantic_replacement.ps1',
        ':!scripts/analyze_legacy_reporting_only_retirement.ps1',
        ':!scripts/analyze_legacy_report_output_consumers.ps1',
        ':!tests/**',
        ':!docs/**',
        ':!qualification/**'
    )

    function Get-OutputWriteEvidence([string]$Path, [string]$FunctionName) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return [pscustomobject]@{ parse_ok = $false; function_found = $false; writes = @() }
        }
        $text = Get-Content -LiteralPath $Path -Raw
        $tokens = $null
        $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$errors)
        if (@($errors).Count -gt 0) {
            return [pscustomobject]@{
                parse_ok = $false
                function_found = $false
                parse_errors = @($errors | ForEach-Object { $_.Message })
                writes = @()
            }
        }
        $fn = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $FunctionName }, $true) | Select-Object -First 1)[0]
        if (-not $fn) {
            return [pscustomobject]@{ parse_ok = $true; function_found = $false; parse_errors = @(); writes = @() }
        }

        $rows = [System.Collections.Generic.List[object]]::new()
        foreach ($cmd in @($fn.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -in @('Set-Content','Out-File','Export-Csv','Add-Content') }, $true))) {
            $stringLiterals = @($cmd.FindAll({ param($n) $n -is [System.Management.Automation.Language.StringConstantExpressionAst] }, $true) |
                ForEach-Object { $_.Value } |
                Where-Object { $_ -and $_.Length -ge 3 } |
                Sort-Object -Unique)
            $candidateNames = @($stringLiterals | Where-Object { $_ -match '(?i)\.(json|csv|md|txt|log)$' -or $_ -match '(?i)(report|audit|l1|reduction|queue|manifest)' })
            $consumerHits = [System.Collections.Generic.List[string]]::new()
            foreach ($needle in $candidateNames) {
                $args = @('grep','-n','-F','--',$needle) + $referenceExclusions
                $hits = @(& git @args 2>$null)
                if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
                    throw "git grep failed while checking output consumer for $needle"
                }
                foreach ($hit in $hits) { $consumerHits.Add($hit) }
            }
            $rows.Add([pscustomobject]@{
                command = $cmd.GetCommandName()
                extent = $cmd.Extent.Text
                string_literals = $stringLiterals
                candidate_output_names = $candidateNames
                tracked_consumer_count = $consumerHits.Count
                tracked_consumer_samples = @($consumerHits | Select-Object -First 20)
                output_unconsumed_by_tracked_runtime = $consumerHits.Count -eq 0
            })
        }
        return [pscustomobject]@{
            parse_ok = $true
            function_found = $true
            parse_errors = @()
            writes = @($rows)
        }
    }

    $comparisons = [System.Collections.Generic.List[object]]::new()
    foreach ($group in @($report.missing_function_implementation_groups | Where-Object function -eq 'Write-L1CrossRepoReport')) {
        foreach ($path in @($group.paths)) {
            $ev = Get-OutputWriteEvidence ([string]$path) ([string]$group.function)
            $writes = @($ev.writes)
            $comparisons.Add([pscustomobject]@{
                path = [string]$path
                function = [string]$group.function
                body_sha256 = [string]$group.body_sha256
                parse_ok = [bool]$ev.parse_ok
                function_found = [bool]$ev.function_found
                parse_errors = @($ev.parse_errors)
                write_count = $writes.Count
                writes = $writes
                all_outputs_unconsumed_by_tracked_runtime = ($ev.parse_ok -and $ev.function_found -and @($writes | Where-Object { -not $_.output_unconsumed_by_tracked_runtime }).Count -eq 0)
                retirement_output_consumer_evidence_complete = ($ev.parse_ok -and $ev.function_found -and $writes.Count -gt 0 -and @($writes | Where-Object { -not $_.output_unconsumed_by_tracked_runtime }).Count -eq 0)
                deletion_authorized = $false
            })
        }
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "legacy-report-output-consumers-$stamp.json"
    [ordered]@{
        source_evidence = $evidence.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'local legacy report output consumer analysis only; no deletion authority'
        reference_exclusions = $referenceExclusions
        comparisons = @($comparisons)
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Legacy report output consumer analysis completed."
    Write-Host "Comparisons: $($comparisons.Count)"
    Write-Host "Outputs with no tracked runtime consumers: $(@($comparisons | Where-Object retirement_output_consumer_evidence_complete).Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
