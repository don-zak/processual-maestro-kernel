[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$EnvFile = Join-Path $Root '.env.evaluation'
if (-not (Test-Path $EnvFile)) { throw '.env.evaluation not found. Start the evaluation runtime first.' }
docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml ps
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/health/live' -TimeoutSec 5
    Write-Host "API health: $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host 'API health: unavailable' -ForegroundColor Red
    exit 1
}
