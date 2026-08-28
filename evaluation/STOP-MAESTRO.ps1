[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$EnvFile = Join-Path $Root '.env.evaluation'
if (-not (Test-Path $EnvFile)) { throw '.env.evaluation not found. Start the evaluation runtime first.' }
docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml down
Write-Host 'Processual Maestro evaluation runtime stopped.' -ForegroundColor Green
