<#
.SYNOPSIS
    Splits the monorepo into a public-only tree at ../processual-maestro-public/
    Strips cgtlib/private/, cgtlib/pyproject.toml, and any secrets/ directory.
#>

param(
    [string]$TargetDir = "../processual-maestro-public",
    [string]$Branch = "main",
    [switch]$Push
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TargetDir = Resolve-Path (Join-Path $RepoRoot $TargetDir) -ErrorAction SilentlyContinue
if (-not $TargetDir) {
    $TargetDir = Join-Path $RepoRoot $TargetDir
}

Write-Host "=== Splitting public repo -> $TargetDir ==="

# 1. Create the public repo directory
if (Test-Path $TargetDir) {
    Write-Host "Removing existing target directory..."
    Remove-Item -Recurse -Force $TargetDir
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

# 2. Copy everything except private directories
Write-Host "Copying tree (excluding cgtlib/private/, secrets/, dist/)..."
Get-ChildItem -Path $RepoRoot -Exclude "cgtlib", "secrets", "dist", "__pycache__", ".git", ".venv" |
    Where-Object { $_.Name -notin @("cgtlib", "secrets", "dist", "__pycache__", ".git", ".venv") -and $_.Name -notmatch '\.pyc$' } |
    ForEach-Object {
        $dest = Join-Path $TargetDir $_.Name
        if ($_.PSIsContainer) {
            Copy-Item -Recurse -Path $_.FullName -Destination $dest
        } else {
            Copy-Item -Path $_.FullName -Destination $dest
        }
    }

# 3. Manually copy cgtlib/ but strip cgtlib/private/
Write-Host "Stripping cgtlib/private/ from public tree..."
$cgtlibDest = Join-Path $TargetDir "cgtlib"
New-Item -ItemType Directory -Path $cgtlibDest -Force | Out-Null
Get-ChildItem -Path (Join-Path $RepoRoot "cgtlib") -Exclude "private", "__pycache__" |
    Where-Object { $_.Name -notin @("private", "__pycache__") } |
    ForEach-Object {
        $dest = Join-Path $cgtlibDest $_.Name
        if ($_.PSIsContainer) {
            Copy-Item -Recurse -Path $_.FullName -Destination $dest
        } else {
            Copy-Item -Path $_.FullName -Destination $dest
        }
    }

# 4. Remove cgtlib/pyproject.toml (private-only)
$privatePyproject = Join-Path $cgtlibDest "pyproject.toml"
if (Test-Path $privatePyproject) { Remove-Item -Force $privatePyproject }

# 5. Strip ci-private-only workflows
$publicWorkflows = Join-Path $TargetDir ".github\workflows"
if (Test-Path $publicWorkflows) {
    # keep ci-public.yml, docker.yml, security.yml; remove ci.yml (private)
    $ciPrivate = Join-Path $publicWorkflows "ci.yml"
    if (Test-Path $ciPrivate) { Remove-Item -Force $ciPrivate }
    # rename ci-public.yml -> ci.yml for the public repo
    $ciPublic = Join-Path $publicWorkflows "ci-public.yml"
    if (Test-Path $ciPublic) {
        Rename-Item -Path $ciPublic -NewName "ci.yml" -Force
    }
    # remove tools/ directory
    $toolsDir = Join-Path $TargetDir "tools"
    if (Test-Path $toolsDir) { Remove-Item -Recurse -Force $toolsDir }
}

Write-Host "=== Public tree ready at $TargetDir ==="
Write-Host "Next: cd '$TargetDir' && git init && git add . && git commit -m 'initial public release'"

if ($Push) {
    Write-Host "Push flag set — use: git remote add origin <public-repo-url> && git push -u origin $Branch"
}
