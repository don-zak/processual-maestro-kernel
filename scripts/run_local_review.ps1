param(
    [int]$Port = 8000,
    [string]$DatabaseFile = ".pmk-local-review.sqlite3",
    [switch]$ResetDatabase,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

$envScript = Join-Path $PSScriptRoot "local_review_env.ps1"
$bootstrapScript = Join-Path $PSScriptRoot "bootstrap_local_review.ps1"
if (-not (Test-Path $envScript)) {
    throw "Missing local review environment script: $envScript"
}
if (-not (Test-Path $bootstrapScript)) {
    throw "Missing local review bootstrap script: $bootstrapScript"
}

. $envScript
$context = Set-PmkLocalReviewEnvironment -DatabaseFile $DatabaseFile

$bootstrapArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $bootstrapScript,
    "-DatabaseFile", $DatabaseFile
)
if ($ResetDatabase) {
    $bootstrapArgs += "-ResetDatabase"
}

Write-Host "Preparing Processual Maestro local review runtime..."
& powershell @bootstrapArgs
if ($LASTEXITCODE -ne 0) {
    throw "Local review bootstrap failed with exit code $LASTEXITCODE"
}

$consoleUrl = "http://127.0.0.1:$Port/console/"
$adminUrl = "http://127.0.0.1:$Port/admin"

Write-Host ""
Write-Host "Starting Processual Maestro local review runtime"
Write-Host "Repository: $($context.RepoRoot)"
Write-Host "Database:   $($context.DatabasePath)"
Write-Host "Console:    $consoleUrl"
Write-Host "Admin:      $adminUrl"
Write-Host "Login:      admin / admin (development-only fallback)"
Write-Host "Access log: disabled for a quieter browser/action audit; runtime errors remain visible"
Write-Host ""
Write-Host "This launcher grants no staging or production authority."
Write-Host "Stop the server with Ctrl+C."

if ($OpenBrowser) {
    Start-Process $consoleUrl
}

& python -m uvicorn processual_api.main:app --host 127.0.0.1 --port $Port --no-access-log
if ($LASTEXITCODE -ne 0) {
    throw "Uvicorn exited with code $LASTEXITCODE"
}
