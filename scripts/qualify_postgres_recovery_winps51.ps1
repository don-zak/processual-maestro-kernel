[CmdletBinding()]
param(
    [string]$ExpectedSha = '',
    [string]$PythonBin = 'python',
    [string]$SourceUrlEnvName = 'DATABASE_URL',
    [string]$RestoreTargetUrlEnvName = 'PMK_RESTORE_TEST_DATABASE_URL',
    [string]$ResultsDir = 'launch-hardening-results/postgres-recovery',
    [string]$BackupPath = '',
    [switch]$IncludeBackup,
    [switch]$IncludeRestoreSmoke
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
if (-not $BackupPath) {
    $BackupPath = Join-Path $ResultsDir 'processual-maestro-qualification.dump'
}
$ReportPath = Join-Path $ResultsDir 'postgres-recovery-report.txt'
$JsonPath = Join-Path $ResultsDir 'postgres-recovery-report.json'
$Results = New-Object System.Collections.ArrayList

function Add-Entry {
    param([string]$Name, [string]$Status, [string]$Detail)
    $safe = ($Detail -replace '(?i)(postgres(?:ql)?(?:\+asyncpg)?://)[^\s]+', '$1<redacted>')
    $safe = ($safe -replace '(?i)(password|token|secret|api[_-]?key)=[^\s;]+', '$1=<redacted>')
    [void]$Results.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $safe })
    Write-Host ("[{0}] {1} - {2}" -f $Status, $Name, $safe)
}

function Add-Pass { param([string]$Name,[string]$Detail) Add-Entry $Name 'PASS' $Detail }
function Add-Fail { param([string]$Name,[string]$Detail) Add-Entry $Name 'FAIL' $Detail }
function Add-Skip { param([string]$Name,[string]$Detail) Add-Entry $Name 'SKIP' $Detail }
function Add-Blocked { param([string]$Name,[string]$Detail) Add-Entry $Name 'BLOCKED' $Detail }

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Captured {
    param([string]$Command, [string[]]$Arguments)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Command @Arguments 2>&1
        $code = $LASTEXITCODE
        $text = ($output | ForEach-Object { $_.ToString() } | Out-String).Trim()
        return [pscustomobject]@{ code = $code; text = $text }
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Get-EnvValue {
    param([string]$Name)
    return [Environment]::GetEnvironmentVariable($Name, 'Process')
}

function ConvertTo-PostgresParts {
    param([string]$RawUrl)
    if ([string]::IsNullOrWhiteSpace($RawUrl)) {
        throw 'PostgreSQL connection URL is missing.'
    }

    $normalized = $RawUrl.Trim()
    $normalized = $normalized -replace '^postgresql\+asyncpg://', 'postgresql://'
    $normalized = $normalized -replace '^postgres\+asyncpg://', 'postgresql://'
    $normalized = $normalized -replace '^postgres://', 'postgresql://'
    if (-not $normalized.StartsWith('postgresql://')) {
        throw 'Only PostgreSQL URLs are supported by this qualification harness.'
    }

    $uriText = 'http://' + $normalized.Substring('postgresql://'.Length)
    $uri = [Uri]$uriText
    $userInfo = $uri.UserInfo.Split(':', 2)
    if ($userInfo.Count -lt 1 -or [string]::IsNullOrWhiteSpace($userInfo[0])) {
        throw 'PostgreSQL URL does not contain a user.'
    }

    $database = $uri.AbsolutePath.TrimStart('/')
    if ([string]::IsNullOrWhiteSpace($database)) {
        throw 'PostgreSQL URL does not contain a database name.'
    }

    $password = ''
    if ($userInfo.Count -eq 2) { $password = [Uri]::UnescapeDataString($userInfo[1]) }

    return [pscustomobject]@{
        host = $uri.Host
        port = $(if ($uri.IsDefaultPort) { '5432' } else { [string]$uri.Port })
        database = [Uri]::UnescapeDataString($database)
        user = [Uri]::UnescapeDataString($userInfo[0])
        password = $password
    }
}

function Invoke-WithPgEnvironment {
    param(
        [pscustomobject]$Connection,
        [scriptblock]$Script
    )
    $names = @('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD')
    $before = @{}
    foreach ($name in $names) { $before[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
    try {
        $env:PGHOST = $Connection.host
        $env:PGPORT = $Connection.port
        $env:PGDATABASE = $Connection.database
        $env:PGUSER = $Connection.user
        $env:PGPASSWORD = $Connection.password
        & $Script
    }
    finally {
        foreach ($name in $names) {
            [Environment]::SetEnvironmentVariable($name, $before[$name], 'Process')
        }
    }
}

Require-Command 'git'
Require-Command $PythonBin

$head = (& git rev-parse HEAD).Trim()
$branch = (& git branch --show-current).Trim()
if ($ExpectedSha) {
    if ($head -eq $ExpectedSha) { Add-Pass 'exact-sha' ("HEAD={0}; expected={1}" -f $head, $ExpectedSha) }
    else { Add-Fail 'exact-sha' ("HEAD={0}; expected={1}" -f $head, $ExpectedSha) }
} else {
    Add-Pass 'exact-sha' ("HEAD={0}; no expected SHA supplied" -f $head)
}

$porcelain = (& git status --porcelain | Out-String).Trim()
if ($porcelain) { Add-Fail 'working-tree-clean' ($porcelain -replace "`r?`n", '; ') }
else { Add-Pass 'working-tree-clean' 'clean' }

$sourceUrl = Get-EnvValue $SourceUrlEnvName
if ([string]::IsNullOrWhiteSpace($sourceUrl)) {
    Add-Blocked 'database-url' ("Environment variable {0} is not loaded." -f $SourceUrlEnvName)
} else {
    Add-Pass 'database-url' ("{0} is loaded; value redacted" -f $SourceUrlEnvName)

    $heads = Invoke-Captured $PythonBin @('-m','alembic','heads')
    if ($heads.code -ne 0) {
        Add-Fail 'alembic-heads' ("exit_code={0}; {1}" -f $heads.code, $heads.text)
    } else {
        $headIds = @()
        foreach ($line in ($heads.text -split "`r?`n")) {
            $trimmed = $line.Trim()
            if ($trimmed -match '^([0-9A-Za-z_]+)\s+\(head\)') { $headIds += $Matches[1] }
        }
        if ($headIds.Count -eq 0) {
            Add-Fail 'alembic-heads' 'No Alembic head revision could be parsed.'
        } else {
            Add-Pass 'alembic-heads' ("head_count={0}; heads={1}" -f $headIds.Count, ($headIds -join ','))

            $current = Invoke-Captured $PythonBin @('-m','alembic','current')
            if ($current.code -ne 0) {
                Add-Fail 'alembic-current' ("exit_code={0}; database revision query failed" -f $current.code)
            } else {
                $missing = @($headIds | Where-Object { $current.text -notmatch [regex]::Escape($_) })
                if ($missing.Count -eq 0) {
                    Add-Pass 'alembic-current' 'Database revision includes every repository head.'
                } else {
                    Add-Fail 'alembic-current' ("Database is not at repository head; missing_head_count={0}" -f $missing.Count)
                }
            }
        }
    }
}

if ($IncludeBackup) {
    Require-Command 'pg_dump'
    Require-Command 'pg_restore'
    if ([string]::IsNullOrWhiteSpace($sourceUrl)) {
        Add-Skip 'postgres-backup' 'DATABASE_URL is unavailable; backup not attempted.'
        Add-Skip 'postgres-backup-readability' 'Backup was not created.'
    } else {
        try {
            $source = ConvertTo-PostgresParts $sourceUrl
            $backupResult = $null
            Invoke-WithPgEnvironment $source {
                $backupResult = Invoke-Captured 'pg_dump' @('--format=custom','--no-owner','--no-privileges','--file', $BackupPath)
                Set-Variable -Name backupResult -Value $backupResult -Scope 1
            }
            if ($backupResult.code -ne 0) {
                Add-Fail 'postgres-backup' ("pg_dump exit_code={0}" -f $backupResult.code)
                Add-Skip 'postgres-backup-readability' 'Backup creation failed.'
            } elseif (-not (Test-Path $BackupPath)) {
                Add-Fail 'postgres-backup' 'pg_dump exited successfully but the expected backup file is absent.'
                Add-Skip 'postgres-backup-readability' 'Backup file absent.'
            } else {
                $size = (Get-Item $BackupPath).Length
                Add-Pass 'postgres-backup' ("custom-format backup created; bytes={0}" -f $size)
                $list = Invoke-Captured 'pg_restore' @('--list', $BackupPath)
                if ($list.code -eq 0 -and -not [string]::IsNullOrWhiteSpace($list.text)) {
                    Add-Pass 'postgres-backup-readability' 'pg_restore --list successfully parsed the backup archive.'
                } else {
                    Add-Fail 'postgres-backup-readability' ("pg_restore --list exit_code={0}" -f $list.code)
                }
            }
        }
        catch {
            Add-Fail 'postgres-backup' $_.Exception.GetType().Name
            Add-Skip 'postgres-backup-readability' 'Backup qualification raised an error.'
        }
    }
} else {
    Add-Skip 'postgres-backup' 'Use -IncludeBackup to create and validate a custom-format qualification backup.'
    Add-Skip 'postgres-backup-readability' 'Backup not requested.'
}

if ($IncludeRestoreSmoke) {
    Require-Command 'pg_restore'
    Require-Command 'psql'
    $targetUrl = Get-EnvValue $RestoreTargetUrlEnvName
    if ([string]::IsNullOrWhiteSpace($targetUrl)) {
        Add-Blocked 'postgres-restore-smoke' ("Environment variable {0} is not loaded." -f $RestoreTargetUrlEnvName)
    } elseif ([string]::IsNullOrWhiteSpace($sourceUrl)) {
        Add-Blocked 'postgres-restore-smoke' 'Source database URL is unavailable.'
    } elseif ($targetUrl.Trim() -eq $sourceUrl.Trim()) {
        Add-Fail 'postgres-restore-smoke' 'Restore target must be a separate database; source and target URLs are identical.'
    } elseif (-not (Test-Path $BackupPath)) {
        Add-Fail 'postgres-restore-smoke' 'Backup archive does not exist. Run with -IncludeBackup or provide -BackupPath.'
    } else {
        try {
            $target = ConvertTo-PostgresParts $targetUrl
            $restoreResult = $null
            Invoke-WithPgEnvironment $target {
                $restoreResult = Invoke-Captured 'pg_restore' @('--clean','--if-exists','--no-owner','--no-privileges','--exit-on-error','--dbname', $target.database, $BackupPath)
                Set-Variable -Name restoreResult -Value $restoreResult -Scope 1
            }
            if ($restoreResult.code -ne 0) {
                Add-Fail 'postgres-restore-smoke' ("pg_restore exit_code={0}" -f $restoreResult.code)
            } else {
                $verifyResult = $null
                Invoke-WithPgEnvironment $target {
                    $verifyResult = Invoke-Captured 'psql' @('--no-psqlrc','--tuples-only','--no-align','--command','SELECT version_num FROM alembic_version ORDER BY version_num;')
                    Set-Variable -Name verifyResult -Value $verifyResult -Scope 1
                }
                if ($verifyResult.code -eq 0 -and -not [string]::IsNullOrWhiteSpace($verifyResult.text)) {
                    Add-Pass 'postgres-restore-smoke' 'Restore completed and alembic_version is readable in the separate restore target.'
                } else {
                    Add-Fail 'postgres-restore-smoke' ("restore completed but verification query exit_code={0}" -f $verifyResult.code)
                }
            }
        }
        catch {
            Add-Fail 'postgres-restore-smoke' $_.Exception.GetType().Name
        }
    }
} else {
    Add-Skip 'postgres-restore-smoke' ("Use -IncludeRestoreSmoke only with a disposable target in {0}." -f $RestoreTargetUrlEnvName)
}

$failed = @($Results | Where-Object { $_.status -eq 'FAIL' })
$blocked = @($Results | Where-Object { $_.status -eq 'BLOCKED' })
if ($failed.Count -gt 0) { $summary = "OVERALL FAIL ($($failed.Count) failed checks)" }
elseif ($blocked.Count -gt 0) { $summary = "OVERALL BLOCKED ($($blocked.Count) infrastructure/external blockers)" }
else { $summary = 'OVERALL PASS FOR REQUESTED CHECKS' }

$lines = @('PostgreSQL recovery qualification', "HEAD: $head", "Branch: $branch", "Result: $summary", '')
$lines += @($Results | ForEach-Object { "[$($_.status)] $($_.name): $($_.detail)" })
$lines | Set-Content -Path $ReportPath -Encoding UTF8

$report = [pscustomobject]@{
    head = $head
    branch = $branch
    overall = $summary
    backup_path = $(if (Test-Path $BackupPath) { $BackupPath } else { $null })
    checks = @($Results | ForEach-Object { $_ })
}
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $JsonPath -Encoding UTF8

Write-Host $summary
Write-Host "Evidence: $ReportPath"
Write-Host "JSON: $JsonPath"
if ($failed.Count -gt 0) { exit 1 }
if ($blocked.Count -gt 0) { exit 2 }
exit 0
