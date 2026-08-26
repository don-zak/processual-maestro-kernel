param(
    [string]$DatabaseFile = ".pmk-local-review.sqlite3",
    [switch]$ResetDatabase
)

$ErrorActionPreference = "Stop"

$envScript = Join-Path $PSScriptRoot "local_review_env.ps1"
if (-not (Test-Path $envScript)) {
    throw "Missing local review environment script: $envScript"
}
. $envScript

$context = Set-PmkLocalReviewEnvironment -DatabaseFile $DatabaseFile

if ($ResetDatabase -and (Test-Path $context.DatabasePath)) {
    Write-Host "Removing existing local review database: $($context.DatabasePath)"
    Remove-Item -LiteralPath $context.DatabasePath -Force
}

Write-Host "Repository: $($context.RepoRoot)"
Write-Host "Python:     $($context.PythonVersion)"
Write-Host "Database:   $($context.DatabasePath)"
Write-Host ""
Write-Host "[1/2] Applying Alembic migrations..."
& python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Alembic migration failed with exit code $LASTEXITCODE"
}

Write-Host "[2/2] Seeding local-review subscription state..."
& python qualification/local_review_subscription_seed.py
if ($LASTEXITCODE -ne 0) {
    throw "Local review subscription seed failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Local review bootstrap completed successfully."
Write-Host "Customer:  $($context.CustomerRef)"
Write-Host "Authority: local-review only; staging/production authority remains false"
