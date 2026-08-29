[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Showcase = Join-Path $Root 'MAESTRO_SHOWCASE.html'

if (-not (Test-Path $Showcase)) {
    throw 'MAESTRO_SHOWCASE.html was not found beside this launcher.'
}

Write-Host ''
Write-Host '=======================================================' -ForegroundColor Cyan
Write-Host ' Maestro - Startup Tunisia Static Showcase' -ForegroundColor Cyan
Write-Host '=======================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Opening standalone demo UI...' -ForegroundColor Green
Write-Host 'No Docker, login, password, API key or runtime is required.' -ForegroundColor Yellow
Write-Host 'All interactive states are synthetic/demo states unless explicitly marked as recorded evidence.' -ForegroundColor Yellow
Write-Host ''

Start-Process $Showcase
