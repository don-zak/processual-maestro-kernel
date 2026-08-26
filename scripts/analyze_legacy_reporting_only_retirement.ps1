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

    $mutatingCommands = @(
        'Remove-Item','Move-Item','Copy-Item','Set-Content','Add-Content','Out-File','Export-Csv','New-Item',
        'Invoke-WebRequest','Invoke-RestMethod','Start-Process','git','gh','docker','docker-compose'
    )
    $reportingCommands = @('Write-Host','Write-Output','Write-Warning','Write-Verbose','Format-Table','Format-List')

    function Get-FunctionRole([string]$Path, [string]$FunctionName) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return [pscustomobject]@{ parse_ok = $false; function_found = $false }
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
            }
        }
        $fn = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $FunctionName }, $true) | Select-Object -First 1)[0]
        if (-not $fn) {
            return [pscustomobject]@{ parse_ok = $true; function_found = $false; parse_errors = @() }
        }

        $commands = @($fn.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) |
            ForEach-Object { $_.GetCommandName() } | Where-Object { $_ } | Sort-Object -Unique)
        $mutations = @($commands | Where-Object { $_ -in $mutatingCommands })
        $reporting = @($commands | Where-Object { $_ -in $reportingCommands })
        $returns = @($fn.FindAll({ param($n) $n -is [System.Management.Automation.Language.ReturnStatementAst] }, $true) |
            ForEach-Object { $_.Extent.Text })

        $allCalls = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq $FunctionName }, $true))
        $callRows = [System.Collections.Generic.List[object]]::new()
        foreach ($call in $allCalls) {
            $parent = $call.Parent
            $captured = $false
            while ($null -ne $parent) {
                if ($parent -is [System.Management.Automation.Language.AssignmentStatementAst]) { $captured = $true; break }
                if ($parent -is [System.Management.Automation.Language.PipelineAst] -or $parent -is [System.Management.Automation.Language.StatementBlockAst]) { break }
                $parent = $parent.Parent
            }
            $callRows.Add([pscustomobject]@{
                text = $call.Extent.Text
                result_captured = $captured
            })
        }

        $nonReportingCommands = @($commands | Where-Object { $_ -notin $reportingCommands -and $_ -notin @('Where-Object','Select-Object','Sort-Object','Group-Object','ForEach-Object','Join-Path','Test-Path','Get-Content','ConvertFrom-Json','ConvertTo-Json','Measure-Object') })

        return [pscustomobject]@{
            parse_ok = $true
            function_found = $true
            commands = $commands
            mutating_commands = $mutations
            reporting_commands = $reporting
            non_reporting_commands = $nonReportingCommands
            return_statements = $returns
            call_sites = @($callRows)
            has_state_mutation = $mutations.Count -gt 0
            any_result_captured = @($callRows | Where-Object result_captured).Count -gt 0
            reporting_only_candidate = ($mutations.Count -eq 0 -and @($callRows | Where-Object result_captured).Count -eq 0)
        }
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($group in @($report.missing_function_implementation_groups)) {
        foreach ($path in @($group.paths)) {
            $role = Get-FunctionRole ([string]$path) ([string]$group.function)
            $rows.Add([pscustomobject]@{
                path = [string]$path
                function = [string]$group.function
                body_sha256 = [string]$group.body_sha256
                parse_ok = $role.parse_ok
                function_found = $role.function_found
                commands = @($role.commands)
                mutating_commands = @($role.mutating_commands)
                reporting_commands = @($role.reporting_commands)
                non_reporting_commands = @($role.non_reporting_commands)
                return_statements = @($role.return_statements)
                call_sites = @($role.call_sites)
                has_state_mutation = [bool]$role.has_state_mutation
                any_result_captured = [bool]$role.any_result_captured
                reporting_only_candidate = [bool]$role.reporting_only_candidate
                retirement_safe_if_parent_script_unreferenced = ($role.parse_ok -and $role.function_found -and $role.reporting_only_candidate)
                deletion_authorized = $false
            })
        }
    }

    $byScript = [System.Collections.Generic.List[object]]::new()
    foreach ($group in ($rows | Group-Object path | Sort-Object Name)) {
        $members = @($group.Group)
        $allSafe = @($members | Where-Object { -not $_.retirement_safe_if_parent_script_unreferenced }).Count -eq 0
        $byScript.Add([pscustomobject]@{
            path = $group.Name
            analyzed_function_count = $members.Count
            all_missing_functions_reporting_only = $allSafe
            functions = @($members | Select-Object -ExpandProperty function)
            retirement_evidence_for_missing_functions_complete = $allSafe
            deletion_authorized = $false
        })
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outputPath = Join-Path $AuditDirectory "legacy-reporting-only-retirement-$stamp.json"
    [ordered]@{
        source_evidence = $evidence.FullName
        generated_at = (Get-Date).ToString('o')
        authority = 'local reporting-only role analysis; no deletion authority'
        function_roles = @($rows)
        script_summary = @($byScript)
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Legacy reporting-only retirement analysis completed."
    Write-Host "Function roles: $($rows.Count)"
    Write-Host "Scripts fully reporting-only: $(@($byScript | Where-Object all_missing_functions_reporting_only).Count)"
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
