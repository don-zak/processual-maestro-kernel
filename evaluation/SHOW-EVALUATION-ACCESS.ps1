[CmdletBinding()]
param(
    [switch]$ShowSecrets
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Root '.env.evaluation'

if (-not (Test-Path $EnvFile)) {
    throw 'Evaluation environment not found. Run .\START-MAESTRO.ps1 first.'
}

$values = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^(?<key>[A-Z0-9_]+)=(?<value>.*)$') {
        $values[$Matches.key] = $Matches.value
    }
}

Write-Host ''
Write-Host '=======================================================' -ForegroundColor Green
Write-Host ' Processual Maestro - Evaluation Access' -ForegroundColor Green
Write-Host '=======================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Evaluation URLs' -ForegroundColor Cyan
Write-Host '  Front / Console: http://localhost:8000/console'
Write-Host '  Admin:           http://localhost:8000/admin'
Write-Host '  API Docs:        http://localhost:8000/docs'
Write-Host '  Health:          http://localhost:8000/health/live'
Write-Host ''
Write-Host 'Local evaluation identity' -ForegroundColor Cyan
Write-Host "  Admin email: $($values['MAESTRO_ADMIN_EMAIL'])"

if ($ShowSecrets) {
    Write-Host ''
    Write-Host 'LOCAL EVALUATION SECRETS - do not publish or share.' -ForegroundColor Yellow
    Write-Host "  Admin password: $($values['MAESTRO_ADMIN_PASSWORD'])"
    Write-Host "  API key:        $($values['API_KEYS'])"
} else {
    Write-Host ''
    Write-Host 'Secrets are hidden by default.' -ForegroundColor Yellow
    Write-Host 'Run .\SHOW-EVALUATION-ACCESS.ps1 -ShowSecrets only on the local evaluator machine.'
}

Write-Host ''
Write-Host 'This bundle is evaluation-only. External billing, Tunisia top-up and external LLM execution are disabled.' -ForegroundColor Yellow
