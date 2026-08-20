param(
    [string]$DatabaseFile = ".pmk-local-review.sqlite3"
)

$ErrorActionPreference = "Stop"

function Get-PmkRepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Assert-PmkPython {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python was not found on PATH. Processual Maestro requires Python 3.14+."
    }

    $versionText = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to execute Python."
    }

    $parts = $versionText.Split('.')
    if ($parts.Count -lt 2) {
        throw "Unable to determine Python version: $versionText"
    }
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 14)) {
        throw "Python 3.14+ is required; detected $versionText."
    }

    return $versionText
}

function Set-PmkLocalReviewEnvironment {
    param(
        [string]$DatabaseFile = ".pmk-local-review.sqlite3"
    )

    $repoRoot = Get-PmkRepoRoot
    Set-Location $repoRoot

    $pythonVersion = Assert-PmkPython
    $dbPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $DatabaseFile))
    $dbDirectory = [System.IO.Path]::GetDirectoryName($dbPath)
    if ($dbDirectory) {
        [System.IO.Directory]::CreateDirectory($dbDirectory) | Out-Null
    }
    $dbUrlPath = $dbPath.Replace("\", "/")

    $env:ENVIRONMENT = "development"
    $env:APP_ENV = "development"
    $env:DATABASE_URL = "sqlite+aiosqlite:///$dbUrlPath"
    $env:REDIS_URL = ""
    $env:RATE_LIMIT_ENABLED = "false"
    $env:AUDIT_ENABLED = "false"
    $env:CAPACITY_GUARD_ENABLED = "false"
    $env:PMK_LOCAL_REVIEW_CUSTOMER_REF = "admin"

    # Force the development-only fallback identity. This keeps the local JWT
    # subject aligned with the seeded local-review subscription customer_ref.
    Remove-Item Env:MAESTRO_ADMIN_EMAIL -ErrorAction SilentlyContinue
    Remove-Item Env:MAESTRO_ADMIN_PASSWORD -ErrorAction SilentlyContinue

    if (-not $env:JWT_SECRET) {
        $env:JWT_SECRET = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    }
    if (-not $env:API_KEYS) {
        $env:API_KEYS = "dev-public-test-key"
    }

    return [pscustomobject]@{
        RepoRoot = $repoRoot
        DatabasePath = $dbPath
        DatabaseUrl = $env:DATABASE_URL
        PythonVersion = $pythonVersion
        CustomerRef = $env:PMK_LOCAL_REVIEW_CUSTOMER_REF
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $context = Set-PmkLocalReviewEnvironment -DatabaseFile $DatabaseFile
    Write-Host "Local review environment configured."
    Write-Host "Repository: $($context.RepoRoot)"
    Write-Host "Python:     $($context.PythonVersion)"
    Write-Host "Database:   $($context.DatabasePath)"
    Write-Host "Customer:   $($context.CustomerRef)"
    Write-Host "Authority:  local-review only; staging/production authority remains false"
}
