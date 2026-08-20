param(
    [int]$Port = 8000,
    [string]$DatabaseFile = ".pmk-local-review.sqlite3"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$dbPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DatabaseFile))
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

# Use the development-only admin/admin fallback so the JWT subject and the
# seeded subscription customer reference remain intentionally aligned.
$env:MAESTRO_ADMIN_EMAIL = $null
$env:MAESTRO_ADMIN_PASSWORD = $null

if (-not $env:JWT_SECRET) {
    $env:JWT_SECRET = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
}
if (-not $env:API_KEYS) {
    $env:API_KEYS = "dev-public-test-key"
}

Write-Host "Local review database: $dbPath"
Write-Host "Applying Alembic migrations..."
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Alembic migration failed with exit code $LASTEXITCODE"
}

Write-Host "Seeding local-review subscription state..."
python qualification/local_review_subscription_seed.py
if ($LASTEXITCODE -ne 0) {
    throw "Local review subscription seed failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Starting Processual Maestro local review runtime"
Write-Host "Console: http://127.0.0.1:$Port/console/"
Write-Host "Admin:   http://127.0.0.1:$Port/admin"
Write-Host "Login:   admin / admin (development-only fallback)"
Write-Host ""
Write-Host "This launcher grants no staging or production authority."

python -m uvicorn processual_api.main:app --host 127.0.0.1 --port $Port
