[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputDirectory = ".pmk-repo-audit",
    [string]$Timestamp = (Get-Date -Format "yyyyMMdd-HHmmss")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$outputPath = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory
} else {
    Join-Path $rootPath $OutputDirectory
}
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

function Get-VersionNumber {
    param([Parameter(Mandatory = $true)][System.IO.FileInfo]$File)
    if ($File.Name -match '^pmk-review-decisions-v(\d+)\.json$') {
        return [int]$Matches[1]
    }
    throw "Unexpected review decision filename: $($File.Name)"
}

function Get-Identity {
    param([Parameter(Mandatory = $true)]$Item)
    return @(
        [string]$Item.Repo,
        [string]$Item.Path,
        [string]$Item.BlobSha,
        [string]$Item.MatchType
    ) -join "`u{001f}"
}

function Get-Payload {
    param([Parameter(Mandatory = $true)]$Item)
    return @(
        [string]$Item.Classification,
        [string]$Item.Decision,
        [string]$Item.Reason
    ) -join "`u{001f}"
}

$files = @(Get-ChildItem -LiteralPath $rootPath -Filter 'pmk-review-decisions-v*.json' -File |
    Sort-Object @{ Expression = { Get-VersionNumber -File $_ } })

$versions = [System.Collections.Generic.List[object]]::new()
foreach ($file in $files) {
    $version = Get-VersionNumber -File $file
    $parsed = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
    $map = @{}
    $itemCount = 0

    # Enumerate the parsed root directly. This avoids wrapping a JSON root array
    # as a single pipeline object on Windows PowerShell 5.1.
    foreach ($item in $parsed) {
        $itemCount += 1
        $identity = Get-Identity -Item $item
        if ($map.ContainsKey($identity)) {
            throw "Duplicate decision identity inside $($file.Name): $identity"
        }
        $map[$identity] = $item
    }

    $versions.Add([pscustomobject]@{
        version = $version
        file = $file.Name
        item_count = $itemCount
        map = $map
    })
}

$transitions = [System.Collections.Generic.List[object]]::new()
for ($i = 1; $i -lt @($versions).Count; $i++) {
    $previous = $versions[$i - 1]
    $current = $versions[$i]
    $previousKeys = @($previous.map.Keys)
    $currentKeys = @($current.map.Keys)

    $added = @($currentKeys | Where-Object { -not $previous.map.ContainsKey($_) })
    $removed = @($previousKeys | Where-Object { -not $current.map.ContainsKey($_) })
    $shared = @($currentKeys | Where-Object { $previous.map.ContainsKey($_) })
    $changed = @($shared | Where-Object {
        (Get-Payload -Item $previous.map[$_]) -ne (Get-Payload -Item $current.map[$_])
    })
    $unchanged = @($shared | Where-Object {
        (Get-Payload -Item $previous.map[$_]) -eq (Get-Payload -Item $current.map[$_])
    })

    $addedCount = @($added).Count
    $removedCount = @($removed).Count
    $changedCount = @($changed).Count
    $unchangedCount = @($unchanged).Count

    $transitions.Add([pscustomobject][ordered]@{
        from_version = $previous.version
        to_version = $current.version
        previous_count = $previous.item_count
        current_count = $current.item_count
        added = $addedCount
        removed = $removedCount
        changed = $changedCount
        unchanged = $unchangedCount
        previous_is_identity_subset = ($removedCount -eq 0)
        previous_is_exact_subset = (($removedCount -eq 0) -and ($changedCount -eq 0))
    })
}

$versionCount = @($versions).Count
$latest = if ($versionCount -gt 0) { $versions[$versionCount - 1] } else { $null }
$allHistoricalIdentities = @{}
foreach ($version in $versions) {
    foreach ($identity in $version.map.Keys) {
        $allHistoricalIdentities[$identity] = $true
    }
}
$missingFromLatest = @(
    if ($null -ne $latest) {
        $allHistoricalIdentities.Keys | Where-Object { -not $latest.map.ContainsKey($_) }
    }
)

$missingFromLatestCount = @($missingFromLatest).Count
$nonIdentityMonotonic = @($transitions | Where-Object { -not $_.previous_is_identity_subset })
$nonExactMonotonic = @($transitions | Where-Object { -not $_.previous_is_exact_subset })

$summary = [pscustomobject][ordered]@{
    version_count = $versionCount
    latest_version = if ($null -ne $latest) { $latest.version } else { $null }
    latest_item_count = if ($null -ne $latest) { $latest.item_count } else { 0 }
    all_historical_identity_count = @($allHistoricalIdentities.Keys).Count
    identities_missing_from_latest = $missingFromLatestCount
    every_transition_identity_monotonic = (@($nonIdentityMonotonic).Count -eq 0)
    every_transition_exact_monotonic = (@($nonExactMonotonic).Count -eq 0)
    deletion_authorized = $false
}

$result = [pscustomobject][ordered]@{
    schema_version = 3
    policy = [pscustomobject][ordered]@{
        mode = 'READ_ONLY_REVIEW_DECISION_LINEAGE'
        deletion_authorized = $false
        version_number_is_not_supersession_authority = $true
        exact_subset_proof_required = $true
        windows_powershell_scalar_safe_counts = $true
    }
    summary = $summary
    versions = @($versions | ForEach-Object {
        [pscustomobject]@{ version = $_.version; file = $_.file; item_count = $_.item_count }
    })
    transitions = @($transitions)
}

$jsonPath = Join-Path $outputPath ("review-decision-lineage-{0}.json" -f $Timestamp)
$csvPath = Join-Path $outputPath ("review-decision-lineage-{0}.csv" -f $Timestamp)
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding utf8
$transitions | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

[pscustomobject][ordered]@{
    Json = $jsonPath
    Csv = $csvPath
    Summary = $summary
    Transitions = @($transitions)
}
