param(
    [string]$AuditDirectory = ".pmk-repo-audit",
    [string[]]$PatchPaths = @(
        "wave2a-governance-tests.patch",
        "wave2a-governance-tests-round2.patch",
        "wave2a-round2-serialization-fix.patch"
    )
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath $AuditDirectory)) {
        New-Item -ItemType Directory -Path $AuditDirectory | Out-Null
    }

    function Invoke-GitApplyCheck {
        param(
            [Parameter(Mandatory=$true)][string]$PatchPath,
            [switch]$Reverse
        )

        $args = @("apply", "--check")
        if ($Reverse) { $args += "--reverse" }
        $args += "--"
        $args += $PatchPath

        # git apply --check returning non-zero is expected analysis data. Windows
        # PowerShell can surface native stderr as NativeCommandError when the
        # script-wide ErrorActionPreference is Stop, so temporarily downgrade
        # only this native probe and restore the original preference immediately.
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $output = & git @args 2>&1
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        return [pscustomobject]@{
            success = ($exitCode -eq 0)
            exit_code = $exitCode
            output = @($output | ForEach-Object { [string]$_ })
        }
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($patch in $PatchPaths) {
        if (-not (Test-Path -LiteralPath $patch -PathType Leaf)) {
            $rows.Add([pscustomobject]@{
                path = $patch
                exists = $false
                sha256 = $null
                size_bytes = $null
                forward_apply_check = $false
                reverse_apply_check = $false
                state = "MISSING_LOCAL_PATCH"
                retirement_candidate = $false
                deletion_authorized = $false
                forward_output = @()
                reverse_output = @()
            })
            continue
        }

        $hash = (Get-FileHash -LiteralPath $patch -Algorithm SHA256).Hash.ToLowerInvariant()
        $item = Get-Item -LiteralPath $patch
        $forward = Invoke-GitApplyCheck -PatchPath $patch
        $reverse = Invoke-GitApplyCheck -PatchPath $patch -Reverse

        $state = if ($reverse.success -and -not $forward.success) {
            "ALREADY_REPRESENTED_IN_CURRENT_TREE"
        } elseif ($forward.success -and -not $reverse.success) {
            "NOT_YET_APPLIED_TO_CURRENT_TREE"
        } elseif ($forward.success -and $reverse.success) {
            "AMBIGUOUS_BOTH_DIRECTIONS_APPLY"
        } else {
            "DIVERGED_OR_PARTIALLY_REPRESENTED"
        }

        $rows.Add([pscustomobject]@{
            path = $patch
            exists = $true
            sha256 = $hash
            size_bytes = $item.Length
            forward_apply_check = $forward.success
            reverse_apply_check = $reverse.success
            state = $state
            retirement_candidate = ($state -eq "ALREADY_REPRESENTED_IN_CURRENT_TREE")
            deletion_authorized = $false
            forward_output = $forward.output
            reverse_output = $reverse.output
        })
    }

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $outputPath = Join-Path $AuditDirectory "local-patch-provenance-$stamp.json"
    [ordered]@{
        generated_at = (Get-Date).ToString("o")
        head = (& git rev-parse HEAD).Trim()
        authority = "local patch provenance analysis only; no patch application or deletion authority"
        patches = @($rows)
    } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputPath -Encoding UTF8

    Write-Host "Local patch provenance analysis completed."
    foreach ($row in $rows) {
        Write-Host "$($row.path): $($row.state)"
    }
    Write-Host "JSON: $outputPath"
} finally {
    Pop-Location
}
