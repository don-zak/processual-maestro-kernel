param(
    [int]$Port = 8000,
    [string]$OutputDir = "artifacts/local-button-audit"
)

$ErrorActionPreference = "Stop"

$envScript = Join-Path $PSScriptRoot "local_review_env.ps1"
if (-not (Test-Path $envScript)) {
    throw "Missing local review environment script: $envScript"
}
. $envScript

$context = Set-PmkLocalReviewEnvironment
$baseUrl = "http://127.0.0.1:$Port"

Write-Host "Checking local runtime before button audit..."
try {
    $live = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/health/live" -TimeoutSec 5
    if ($live.StatusCode -ne 200) {
        throw "Unexpected /health/live status: $($live.StatusCode)"
    }
} catch {
    throw "Local runtime is not reachable at $baseUrl. Start it first with .\scripts\run_local_review.ps1. $($_.Exception.Message)"
}

try {
    & python -c "import playwright" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "missing" }
} catch {
    throw "Playwright is not installed. Run .\scripts\setup_local_review.ps1 -IncludeBrowserAudit first."
}

$env:VQ1_BASE_URL = $baseUrl
$env:VQ1_OUTPUT_DIR = $OutputDir
$env:VQ1_USERNAME = "admin"
$env:VQ1_PASSWORD = "admin"

Write-Host ""
Write-Host "Running exhaustive Console/Admin button action audit..."
Write-Host "Base URL: $baseUrl"
Write-Host "Report:   $OutputDir\button_action_report.json"
Write-Host "Mutating requests are dispatched then neutralized by the qualification harness."
Write-Host ""

& python qualification/vq1_button_action_validator.py
if ($LASTEXITCODE -ne 0) {
    throw "Button action audit failed with exit code $LASTEXITCODE. Review $OutputDir\button_action_report.json"
}

Write-Host ""
Write-Host "Button action audit PASSED."
Write-Host "Report: $OutputDir\button_action_report.json"
Write-Host "This proves delivered UI wiring in the local review environment only; it grants no staging or production authority."
