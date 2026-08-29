[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$EnvFile = Join-Path $Root '.env.evaluation'
if (-not (Test-Path $EnvFile)) { throw '.env.evaluation not found. Start the evaluation runtime first.' }
if (-not $Force -and -not $PSCmdlet.ShouldProcess('local evaluation database and API data', 'Delete and rebuild')) { return }
docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml down -v
docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml up -d
Write-Host 'Evaluation data reset. Run CHECK-STATUS.ps1 after services become healthy.' -ForegroundColor Green
