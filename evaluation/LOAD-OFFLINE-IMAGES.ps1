[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Images = Join-Path $Root 'images'
if (-not (Test-Path $Images)) { throw 'Offline images directory is missing.' }
$archives = Get-ChildItem -Path $Images -Filter '*.tar' | Sort-Object Name
if (-not $archives) { throw 'No Docker image archives were found.' }
foreach ($archive in $archives) {
    Write-Host "Loading $($archive.Name)..." -ForegroundColor Cyan
    docker load -i $archive.FullName
}
Write-Host 'Offline Docker images loaded.' -ForegroundColor Green
