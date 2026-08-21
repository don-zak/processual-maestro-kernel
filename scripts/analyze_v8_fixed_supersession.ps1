param(
    [string]$BrokenPath = "Invoke-PMKRepoAudit-v8.ps1",
    [string]$FixedPath = "Invoke-PMKRepoAudit-v8-fixed.ps1",
    [string]$AuditDirectory = ".pmk-repo-audit"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    foreach ($path in @($BrokenPath,$FixedPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing local tooling file: $path" }
    }

    function Parse-PowerShell([string]$Path) {
        $text = Get-Content -LiteralPath $Path -Raw
        $tokens = $null
        $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$errors)
        $functions = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) |
            ForEach-Object { $_.Name } | Sort-Object -Unique)
        $commands = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) |
            ForEach-Object { $_.GetCommandName() } | Where-Object { $_ } | Sort-Object -Unique)
        return [pscustomobject]@{
            path = $Path
            text = $text
            parse_ok = @($errors).Count -eq 0
            parse_errors = @($errors | ForEach-Object { $_.Message })
            functions = $functions
            commands = $commands
        }
    }

    function Normalize-Text([string]$Text) {
        $lines = @($Text -split "`r?`n")
        $normalized = @()
        foreach ($line in $lines) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
            if ($trimmed.StartsWith('#')) { continue }
            $normalized += ($trimmed -replace '\s+', ' ')
        }
        return [string]::Join("`n", $normalized)
    }

    $broken = Parse-PowerShell $BrokenPath
    $fixed = Parse-PowerShell $FixedPath
    $brokenNorm = Normalize-Text $broken.text
    $fixedNorm = Normalize-Text $fixed.text

    $brokenLines = @($brokenNorm -split "`n")
    $fixedLines = @($fixedNorm -split "`n")
    $onlyBroken = @($brokenLines | Where-Object { $_ -notin $fixedLines } | Sort-Object -Unique)
    $onlyFixed = @($fixedLines | Where-Object { $_ -notin $brokenLines } | Sort-Object -Unique)
    $missingFunctionsInFixed = @($broken.functions | Where-Object { $_ -notin $fixed.functions })
    $missingCommandsInFixed = @($broken.commands | Where-Object { $_ -notin $fixed.commands })

    $result = [ordered]@{
        generated_at = (Get-Date).ToString('o')
        authority = 'local v8-to-v8-fixed supersession evidence only; no deletion authority'
        broken_path = $BrokenPath
        fixed_path = $FixedPath
        broken_parse_ok = $broken.parse_ok
        fixed_parse_ok = $fixed.parse_ok
        broken_parse_errors = $broken.parse_errors
        fixed_parse_errors = $fixed.parse_errors
        broken_function_count = $broken.functions.Count
        fixed_function_count = $fixed.functions.Count
        missing_functions_in_fixed = $missingFunctionsInFixed
        missing_commands_in_fixed = $missingCommandsInFixed
        normalized_lines_only_in_broken = $onlyBroken
        normalized_lines_only_in_fixed = $onlyFixed
        fixed_contains_all_parseable_broken_functions = $missingFunctionsInFixed.Count -eq 0
        fixed_contains_all_parseable_broken_commands = $missingCommandsInFixed.Count -eq 0
        broken_is_syntax_invalid = -not $broken.parse_ok
        fixed_is_syntax_valid = $fixed.parse_ok
        direct_fixed_successor_evidence_complete = (
            (-not $broken.parse_ok) -and
            $fixed.parse_ok -and
            $missingFunctionsInFixed.Count -eq 0 -and
            $missingCommandsInFixed.Count -eq 0
        )
        deletion_authorized = $false
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "v8-fixed-supersession-$stamp.json"
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "v8 fixed supersession analysis completed."
    Write-Host "Broken parse ok: $($broken.parse_ok)"
    Write-Host "Fixed parse ok: $($fixed.parse_ok)"
    Write-Host "Missing functions in fixed: $($missingFunctionsInFixed.Count)"
    Write-Host "Missing commands in fixed: $($missingCommandsInFixed.Count)"
    Write-Host "Direct fixed successor evidence complete: $($result.direct_fixed_successor_evidence_complete)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
