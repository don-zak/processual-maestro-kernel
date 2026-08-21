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
$reportPath = Join-Path $OutputDir "button_action_report.json"

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
Write-Host "Report:   $reportPath"
Write-Host "Mutating requests are dispatched then neutralized by the qualification harness."
Write-Host ""

Remove-Item $reportPath -ErrorAction SilentlyContinue
& python qualification/vq1_button_action_validator_v2.py
$exitCode = $LASTEXITCODE

if (Test-Path $reportPath) {
    Write-Host ""
    Write-Host "=== SAVED BUTTON ACTION REPORT ==="
    try {
        $report = Get-Content $reportPath -Raw | ConvertFrom-Json
        Write-Host ("ALL:         {0}" -f $report.totals.all)
        Write-Host ("PASS:        {0}" -f $report.totals.pass)
        Write-Host ("CONDITIONAL: {0}" -f $report.totals.conditional)
        Write-Host ("FAIL:        {0}" -f $report.totals.fail)
        if ($report.fatal_error) {
            Write-Host ("FATAL:       {0}" -f $report.fatal_error)
        }
        $failures = @($report.results | Where-Object { $_.status -eq "FAIL" })
        if ($failures.Count -gt 0) {
            Write-Host ""
            Write-Host "Failures:"
            foreach ($failure in $failures | Select-Object -First 40) {
                Write-Host ("- {0}/{1} :: {2} :: {3}" -f $failure.surface, $failure.section, $failure.label, $failure.notes)
            }
        }
    } catch {
        Write-Host "Report exists but could not be summarized as JSON."
        Get-Content $reportPath
    }
} else {
    Write-Host ""
    Write-Host "No button_action_report.json was produced."
}

if ($exitCode -ne 0) {
    throw "Button action audit failed with exit code $exitCode. Review $reportPath"
}

Write-Host ""
Write-Host "Button action audit PASSED."
Write-Host "Report: $reportPath"
Write-Host "This proves delivered UI wiring in the local review environment only; it grants no staging or production authority."
