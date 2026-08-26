param(
    [string]$AuditDirectory = ".pmk-repo-audit",
    [string]$CanonicalPath = "Invoke-PMKRepoAudit-v20.ps1"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $evidence = Get-ChildItem -LiteralPath $AuditDirectory -Filter 'local-tooling-retirement-evidence-*.json' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $evidence) { throw "No focused retirement evidence JSON found in $AuditDirectory." }
    if (-not (Test-Path -LiteralPath $CanonicalPath -PathType Leaf)) { throw "Canonical tooling file not found: $CanonicalPath" }

    $report = Get-Content -LiteralPath $evidence.FullName -Raw | ConvertFrom-Json
    $canonicalText = Get-Content -LiteralPath $CanonicalPath -Raw
    $tokens = $null
    $errors = $null
    $canonicalAst = [System.Management.Automation.Language.Parser]::ParseInput($canonicalText, [ref]$tokens, [ref]$errors)
    if (@($errors).Count -gt 0) { throw "Unable to parse canonical PowerShell file: $CanonicalPath" }

    function Get-AstSemanticSignature([string]$Path, [string]$FunctionName) {
        $text = Get-Content -LiteralPath $Path -Raw
        $tokensLocal = $null
        $errorsLocal = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokensLocal, [ref]$errorsLocal)
        if (@($errorsLocal).Count -gt 0) {
            return [pscustomobject]@{
                parse_ok = $false
                commands = @()
                literals = @()
                call_sites = @()
            }
        }
        $fn = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $FunctionName }, $true) | Select-Object -First 1)[0]
        if (-not $fn) {
            return [pscustomobject]@{
                parse_ok = $true
                commands = @()
                literals = @()
                call_sites = @()
            }
        }
        $commands = @($fn.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) |
            ForEach-Object { $_.GetCommandName() } |
            Where-Object { $_ } |
            Sort-Object -Unique)
        $literals = @($fn.FindAll({ param($n) $n -is [System.Management.Automation.Language.StringConstantExpressionAst] }, $true) |
            ForEach-Object { $_.Value } |
            Where-Object { $_ -and $_.Length -ge 4 } |
            Sort-Object -Unique)
        $calls = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq $FunctionName }, $true) |
            ForEach-Object { $_.Extent.Text } |
            Sort-Object -Unique)
        return [pscustomobject]@{
            parse_ok = $true
            commands = $commands
            literals = $literals
            call_sites = $calls
        }
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($group in @($report.missing_function_implementation_groups)) {
        $functionName = [string]$group.function
        foreach ($path in @($group.paths)) {
            $sig = Get-AstSemanticSignature ([string]$path) $functionName
            $missingCommands = @($sig.commands | Where-Object { $canonicalText -notmatch "(?i)(?<![A-Za-z0-9_-])$([regex]::Escape($_))(?![A-Za-z0-9_-])" })
            $missingLiterals = @($sig.literals | Where-Object { $canonicalText -notlike "*$($_)*" })
            $rows.Add([pscustomobject]@{
                path = [string]$path
                function = $functionName
                body_sha256 = [string]$group.body_sha256
                parse_ok = $sig.parse_ok
                command_count = @($sig.commands).Count
                commands = @($sig.commands)
                missing_commands_in_canonical = $missingCommands
                literal_count = @($sig.literals).Count
                literals = @($sig.literals)
                missing_literals_in_canonical = $missingLiterals
                call_sites = @($sig.call_sites)
                all_commands_present_in_canonical = $missingCommands.Count -eq 0
                all_literals_present_in_canonical = $missingLiterals.Count -eq 0
                semantic_replacement_proven = ($sig.parse_ok -and $missingCommands.Count -eq 0 -and $missingLiterals.Count -eq 0)
                deletion_authorized = $false
            })
        }
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "legacy-function-semantic-replacement-$stamp.json"
    [ordered]@{
        source_evidence = $evidence.FullName
        generated_at = (Get-Date).ToString('o')
        canonical_path = $CanonicalPath
        authority = 'local AST semantic comparison only; no deletion authority'
        comparisons = @($rows)
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Legacy function semantic replacement analysis completed."
    Write-Host "Comparisons: $($rows.Count)"
    Write-Host "Proven semantic replacements: $(@($rows | Where-Object semantic_replacement_proven).Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
