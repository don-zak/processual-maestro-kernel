param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [int]$Port = 8765,
    [int]$Width = 1672,
    [int]$Height = 941,
    [string]$BrowserPath = "",
    [switch]$Incognito
)

$ErrorActionPreference = "Stop"

$staticDir = Join-Path $RepoPath "processual_api\static"
$splash = Join-Path $staticDir "splash.html"
if (-not (Test-Path $splash)) {
    throw "Splash not found: $splash"
}

$routeFiles = @(
    "splash_routes_cyan.svg",
    "splash_routes_teal.svg",
    "splash_routes_lime.svg",
    "splash_routes_amber.svg",
    "splash_routes_violet.svg"
)
foreach ($route in $routeFiles) {
    $candidate = Join-Path $staticDir $route
    if (-not (Test-Path $candidate)) {
        throw "Missing canonical route layer: $candidate"
    }
}

if ([string]::IsNullOrWhiteSpace($BrowserPath)) {
    $browserCandidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    $BrowserPath = $browserCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($BrowserPath) -or -not (Test-Path $BrowserPath)) {
    throw "Chrome/Edge not found. Pass -BrowserPath explicitly."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python is required for the local splash preview server."
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("maestro-splash-preview-" + [Guid]::NewGuid().ToString("N"))
$consoleDir = Join-Path $tempRoot "console"
New-Item -ItemType Directory -Force -Path $consoleDir | Out-Null

$server = $null
try {
    Copy-Item $splash (Join-Path $tempRoot "index.html")
    foreach ($route in $routeFiles) {
        Copy-Item (Join-Path $staticDir $route) (Join-Path $consoleDir $route)
    }

    $serverArgs = @()
    if ($python.Name -eq "py.exe") {
        $serverArgs += "-3"
    }
    $serverArgs += @("-m", "http.server", "$Port", "--bind", "127.0.0.1", "--directory", $tempRoot)
    $server = Start-Process -FilePath $python.Source -ArgumentList $serverArgs -PassThru -WindowStyle Hidden

    $url = "http://127.0.0.1:$Port/"
    $ready = $false
    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        Start-Sleep -Milliseconds 100
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
        }
    }
    if (-not $ready) {
        throw "Splash preview server did not become ready on $url"
    }

    $browserArgs = @(
        "--new-window",
        "--force-device-scale-factor=1",
        "--window-size=$Width,$Height"
    )
    if ($Incognito) {
        $browserArgs += "--incognito"
    }
    $browserArgs += $url

    Start-Process -FilePath $BrowserPath -ArgumentList $browserArgs | Out-Null

    Write-Host "MAESTRO splash preview is running." -ForegroundColor Green
    Write-Host "URL: $url"
    Write-Host "Requested browser window: ${Width}x${Height}"
    Write-Host "Device scale factor: 1"
    Write-Host "Browser: $BrowserPath"
    Write-Host ""
    Write-Host "Keep this PowerShell window open while reviewing the splash." -ForegroundColor Cyan
    Write-Host "Press ENTER here when you are finished to stop the local server."
    [void](Read-Host)
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
