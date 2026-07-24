[CmdletBinding()]
param(
    [Parameter()]
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),

    [Parameter()]
    [string]$OutputPath,

    [Parameter()]
    [string]$CurrentPhase = 'UNSPECIFIED',

    [Parameter()]
    [string]$NextTask = 'UNSPECIFIED',

    [Parameter()]
    [string[]]$CompletedWork = @(),

    [Parameter()]
    [string[]]$ValidationEvidence = @(),

    [Parameter()]
    [string[]]$KnownRisks = @(),

    [Parameter()]
    [bool]$PushPerformed = $false,

    [Parameter()]
    [bool]$PullRequestOpened = $false,

    [Parameter()]
    [bool]$MergePerformed = $false,

    [Parameter()]
    [bool]$ProductionAuthorityGranted = $false,

    [Parameter()]
    [bool]$RealStagingQualified = $false
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-GitText {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    $Output = @(
        & git -C $RepositoryRoot @Arguments 2>&1
    )

    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw (
            "Git command failed with exit code $ExitCode.`n" +
            ($Output -join [Environment]::NewLine)
        )
    }

    return ($Output -join [Environment]::NewLine).TrimEnd()
}

function ConvertTo-MarkdownList {
    param(
        [Parameter()]
        [string[]]$Values
    )

    $UsableValues = @(
        $Values | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        }
    )

    if (@($UsableValues).Count -eq 0) {
        return '- None recorded.'
    }

    return (
        $UsableValues | ForEach-Object { "- $_" }
    ) -join [Environment]::NewLine
}

$RoadmapPath = Join-Path `
    $RepositoryRoot `
    'docs\MASTER_REMAINING_EXECUTION_ROADMAP.md'

if (-not (Test-Path -LiteralPath $RoadmapPath -PathType Leaf)) {
    throw "Canonical roadmap is missing: $RoadmapPath"
}

$Roadmap = Get-Content `
    -LiteralPath $RoadmapPath `
    -Raw `
    -Encoding utf8

$Branch = Invoke-GitText -Arguments @('branch', '--show-current')
$Head = Invoke-GitText -Arguments @('rev-parse', 'HEAD')
$Parent = Invoke-GitText -Arguments @('rev-parse', 'HEAD^')
$OriginUrl = Invoke-GitText -Arguments @('remote', 'get-url', 'origin')
$Status = Invoke-GitText -Arguments @('status', '--short')
$StagedFiles = Invoke-GitText -Arguments @('diff', '--cached', '--name-only')

$Timestamp = [DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $SafePhase = $CurrentPhase -replace '[^A-Za-z0-9._-]', '_'
    $FileName = (
        'TRANSITION_' +
        $SafePhase +
        '_' +
        [DateTime]::Now.ToString('yyyyMMdd_HHmmss') +
        '.md'
    )

    $OutputPath = Join-Path $RepositoryRoot $FileName
}

$Fence = '```'

$ReportLines = @(
    '# Processual Maestro Kernel - Transition Report',
    '',
    '## Generated',
    '',
    "Timestamp=$Timestamp",
    '',
    '## Repository state',
    '',
    "RepositoryRoot=$RepositoryRoot",
    "OriginUrl=$OriginUrl",
    "Branch=$Branch",
    "HEAD=$Head",
    "Parent=$Parent",
    '',
    '## Working-tree state',
    '',
    '### Git status',
    '',
    ($Fence + 'text'),
    $Status,
    $Fence,
    '',
    '### Staged files',
    '',
    ($Fence + 'text'),
    $StagedFiles,
    $Fence,
    '',
    '## Current execution position',
    '',
    "CurrentPhase=$CurrentPhase",
    "NextTask=$NextTask",
    '',
    '## Completed work',
    '',
    (ConvertTo-MarkdownList -Values $CompletedWork),
    '',
    '## Validation evidence',
    '',
    (ConvertTo-MarkdownList -Values $ValidationEvidence),
    '',
    '## Known risks and unresolved work',
    '',
    (ConvertTo-MarkdownList -Values $KnownRisks),
    '',
    '## Authority declarations',
    '',
    "PushPerformed=$PushPerformed",
    "PullRequestOpened=$PullRequestOpened",
    "MergePerformed=$MergePerformed",
    "ProductionAuthorityGranted=$ProductionAuthorityGranted",
    "RealStagingQualified=$RealStagingQualified",
    '',
    '---',
    '',
    '# Canonical remaining execution roadmap',
    '',
    $Roadmap
)

$Report = $ReportLines -join [Environment]::NewLine
$OutputDirectory = Split-Path -Parent $OutputPath

if (-not [string]::IsNullOrWhiteSpace($OutputDirectory)) {
    if (-not (Test-Path -LiteralPath $OutputDirectory)) {
        New-Item `
            -ItemType Directory `
            -Path $OutputDirectory `
            -Force |
            Out-Null
    }
}

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

[System.IO.File]::WriteAllText(
    $OutputPath,
    $Report,
    $Utf8NoBom
)

$OutputItem = Get-Item -LiteralPath $OutputPath

Write-Host 'TransitionReportCreated=True'
Write-Host "TransitionReportPath=$($OutputItem.FullName)"
Write-Host "TransitionReportLength=$($OutputItem.Length)"
Write-Host 'RoadmapEmbedded=True'