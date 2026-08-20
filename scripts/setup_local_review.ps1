param(
    [switch]$UpgradePip
)

$ErrorActionPreference = "Stop"

$envScript = Join-Path $PSScriptRoot "local_review_env.ps1"
if (-not (Test-Path $envScript)) {
    throw "Missing local review environment script: $envScript"
}
. $envScript

$context = Set-PmkLocalReviewEnvironment
Write-Host "Preparing Python dependencies for local review..."
Write-Host "Python: $($context.PythonVersion)"

if ($UpgradePip) {
    & python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed with exit code $LASTEXITCODE"
    }
}

& python -m pip install -e ".[api,security,database]"
if ($LASTEXITCODE -ne 0) {
    throw "Local review dependency installation failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Local review dependencies are installed."
Write-Host "Next: .\scripts\run_local_review.ps1 -ResetDatabase -OpenBrowser"
