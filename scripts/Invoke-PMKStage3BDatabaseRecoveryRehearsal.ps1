param(
    [string]$EvidencePath = ".pmk-validation/stage3b-database-recovery.json",
    [string]$SnapshotPath = ".pmk-validation/stage3b-postgres.snapshot.dump",
    [switch]$KeepContainer
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Command {
    param([Parameter(Mandatory=$true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for Stage 3B database recovery rehearsal."
    }
}

function Invoke-Docker {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)

    # Windows PowerShell can promote ordinary native stderr (for example Docker pull
    # progress) into ErrorRecord objects when the caller uses ErrorActionPreference=Stop.
    # Docker success/failure authority is its process exit code, not whether stderr was used.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & docker @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $text = (($output | ForEach-Object { $_.ToString() }) | Out-String).Trim()
    if ($exitCode -ne 0) {
        throw "docker command failed: $($Arguments -join ' ')`n$text"
    }
    return $text
}

function Test-DockerCommand {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & docker @Arguments *> $null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return ($exitCode -eq 0)
}

Assert-Command -Name "docker"
Assert-Command -Name "python"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

$container = "pmk-stage3b-$([Guid]::NewGuid().ToString('N').Substring(0,12))"
$password = [Guid]::NewGuid().ToString("N")
$oldDatabaseUrl = $env:DATABASE_URL
$createdSnapshot = $false

try {
    Write-Host "Ensuring PostgreSQL 16 image is available..."
    Invoke-Docker -Arguments @("pull", "postgres:16") | Out-Null

    Invoke-Docker -Arguments @(
        "run", "--detach", "--rm",
        "--name", $container,
        "--env", "POSTGRES_PASSWORD=$password",
        "--publish", "127.0.0.1::5432",
        "postgres:16"
    ) | Out-Null

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (Test-DockerCommand -Arguments @("exec", $container, "pg_isready", "-U", "postgres")) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        throw "PostgreSQL 16 rehearsal container did not become ready."
    }

    $portText = Invoke-Docker -Arguments @("port", $container, "5432/tcp")
    if ($portText -notmatch ':(\d+)\s*$') {
        throw "Unable to resolve mapped PostgreSQL port: $portText"
    }
    $port = [int]$Matches[1]

    Invoke-Docker -Arguments @("exec", $container, "createdb", "-U", "postgres", "maestro_source") | Out-Null
    $env:DATABASE_URL = "postgresql+asyncpg://postgres:$password@127.0.0.1:$port/maestro_source"

    & python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic upgrade head failed during Stage 3B rehearsal."
    }

    $alembicVersion = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_source",
        "-Atc", "SELECT version_num FROM alembic_version LIMIT 1;"
    )
    if ([string]::IsNullOrWhiteSpace($alembicVersion)) {
        throw "Alembic head could not be read from the migrated source database."
    }

    Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_source", "-v", "ON_ERROR_STOP=1",
        "-c", "CREATE TABLE stage3b_rehearsal_sentinel (id integer PRIMARY KEY, value text NOT NULL); INSERT INTO stage3b_rehearsal_sentinel(id,value) VALUES (1,'snapshot-ok');"
    ) | Out-Null

    $snapshotDirectory = Split-Path -Parent $SnapshotPath
    if (-not [string]::IsNullOrWhiteSpace($snapshotDirectory)) {
        New-Item -ItemType Directory -Path $snapshotDirectory -Force | Out-Null
    }
    $snapshotFullPath = [System.IO.Path]::GetFullPath((Join-Path $root $SnapshotPath))

    Invoke-Docker -Arguments @(
        "exec", $container, "pg_dump", "-U", "postgres", "-d", "maestro_source",
        "--format=custom", "--file=/tmp/stage3b.snapshot.dump"
    ) | Out-Null
    Invoke-Docker -Arguments @("cp", "$container`:/tmp/stage3b.snapshot.dump", $snapshotFullPath) | Out-Null
    $createdSnapshot = $true

    $snapshotHash = (Get-FileHash -Algorithm SHA256 -Path $snapshotFullPath).Hash.ToLowerInvariant()
    if ((Get-Item $snapshotFullPath).Length -le 0) {
        throw "Stage 3B snapshot is empty."
    }

    Invoke-Docker -Arguments @("exec", $container, "createdb", "-U", "postgres", "maestro_restore") | Out-Null
    Invoke-Docker -Arguments @("cp", $snapshotFullPath, "$container`:/tmp/stage3b.restore.dump") | Out-Null
    Invoke-Docker -Arguments @(
        "exec", $container, "pg_restore", "-U", "postgres", "-d", "maestro_restore",
        "--exit-on-error", "/tmp/stage3b.restore.dump"
    ) | Out-Null

    $restoreSentinel = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_restore",
        "-Atc", "SELECT value FROM stage3b_rehearsal_sentinel WHERE id=1;"
    )
    $restoreAlembicVersion = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_restore",
        "-Atc", "SELECT version_num FROM alembic_version LIMIT 1;"
    )
    if ($restoreSentinel -ne "snapshot-ok" -or $restoreAlembicVersion -ne $alembicVersion) {
        throw "Backup/restore verification failed closed."
    }

    Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_source", "-v", "ON_ERROR_STOP=1",
        "-c", "CREATE TABLE stage3b_post_snapshot_mutation (id integer PRIMARY KEY); UPDATE stage3b_rehearsal_sentinel SET value='mutated-after-snapshot' WHERE id=1;"
    ) | Out-Null

    Invoke-Docker -Arguments @("exec", $container, "createdb", "-U", "postgres", "maestro_rollback") | Out-Null
    Invoke-Docker -Arguments @(
        "exec", $container, "pg_restore", "-U", "postgres", "-d", "maestro_rollback",
        "--exit-on-error", "/tmp/stage3b.restore.dump"
    ) | Out-Null

    $rollbackSentinel = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_rollback",
        "-Atc", "SELECT value FROM stage3b_rehearsal_sentinel WHERE id=1;"
    )
    $mutationCount = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_rollback",
        "-Atc", "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename='stage3b_post_snapshot_mutation';"
    )
    $rollbackAlembicVersion = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-d", "maestro_rollback",
        "-Atc", "SELECT version_num FROM alembic_version LIMIT 1;"
    )
    if ($rollbackSentinel -ne "snapshot-ok" -or $mutationCount -ne "0" -or $rollbackAlembicVersion -ne $alembicVersion) {
        throw "Rollback-to-snapshot recovery drill failed closed."
    }

    $postgresVersion = Invoke-Docker -Arguments @(
        "exec", $container, "psql", "-U", "postgres", "-Atc", "SHOW server_version;"
    )

    $evidence = [ordered]@{
        schema_version = 1
        qualification = "STAGE_3B_DATABASE_RECOVERY_REHEARSAL"
        qualified = $false
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        environment = "ephemeral_local_postgresql"
        postgres_version = $postgresVersion
        alembic_head = $alembicVersion
        migration_rehearsal = "PASS"
        backup_snapshot = "PASS"
        backup_sha256 = $snapshotHash
        restore_verification = "PASS"
        rollback_to_snapshot = "PASS"
        rollback_mutation_absent = $true
        synthetic_rehearsal_only = $true
        real_staging_qualified = $false
        remaining_required_gates = @(
            "real_gcp_preflight_execution",
            "real_staging_managed_database_migration",
            "real_staging_backup_restore",
            "real_staging_rollback",
            "metrics_alerts",
            "external_provider_integration",
            "browser_e2e",
            "load_endurance",
            "security_review",
            "named_human_approvals",
            "signed_go_no_go"
        )
    }

    $evidenceDirectory = Split-Path -Parent $EvidencePath
    if (-not [string]::IsNullOrWhiteSpace($evidenceDirectory)) {
        New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
    }
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -Path $EvidencePath -Encoding UTF8

    Write-Host "PASS: Stage 3B migration, backup/restore, and rollback rehearsal completed."
    Write-Host "Evidence: $EvidencePath"
    Write-Host "Snapshot: $SnapshotPath"
    Write-Host "NOTE: synthetic rehearsal does not set RealStagingQualified=true."
}
finally {
    if ($null -eq $oldDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    } else {
        $env:DATABASE_URL = $oldDatabaseUrl
    }
    if (-not $KeepContainer) {
        $null = Test-DockerCommand -Arguments @("rm", "-f", $container)
    } else {
        Write-Host "Rehearsal container retained: $container"
    }
    Pop-Location
}
