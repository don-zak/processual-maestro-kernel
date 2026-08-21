param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:$Port"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int[]]$ExpectedStatus = @(200)
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        $status = [int]$response.StatusCode
        if ($ExpectedStatus -notcontains $status) {
            throw "$Name returned HTTP $status; expected $($ExpectedStatus -join ', ')"
        }
        Write-Host "[OK] $Name -> HTTP $status"
        return $true
    }
    catch {
        Write-Host "[FAIL] $Name -> $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

$checks = @()
$checks += Test-Endpoint -Name "Live health" -Url "$base/health/live"
$checks += Test-Endpoint -Name "Ready health" -Url "$base/health/ready"
$checks += Test-Endpoint -Name "Console" -Url "$base/console/"
$checks += Test-Endpoint -Name "Admin" -Url "$base/admin"

if ($checks -contains $false) {
    throw "One or more local review HTTP checks failed."
}

Write-Host ""
Write-Host "Local review HTTP checks passed."
Write-Host "Console: $base/console/"
Write-Host "Admin:   $base/admin"
