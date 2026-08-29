[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$home = Join-Path $Root 'EVALUATION_HOME.html'
$evidence = Join-Path $Root 'RECORDED-GOVERNANCE-EVIDENCE.html'

Write-Host ''
Write-Host '=======================================================' -ForegroundColor Green
Write-Host ' Processual Maestro - Guided Evaluation Demo' -ForegroundColor Green
Write-Host '=======================================================' -ForegroundColor Green
Write-Host ''
Write-Host '1. Confirm the runtime is healthy.' -ForegroundColor Cyan
& (Join-Path $Root 'CHECK-STATUS.ps1')
Write-Host ''
Write-Host '2. Open the reviewer home and follow the guided flow.' -ForegroundColor Cyan
Write-Host '3. Use recorded governance evidence when a live provider key is not configured.' -ForegroundColor Cyan
Write-Host '4. Keep all operational actions recommendation-only and synthetic.' -ForegroundColor Yellow
Write-Host ''

if (Test-Path $home) { Start-Process $home }
if (Test-Path $evidence) { Start-Process $evidence }
