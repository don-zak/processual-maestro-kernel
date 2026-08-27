param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$OutputPath = (Join-Path $PSScriptRoot "..\artifacts\splash-visual-acceptance.png"),
    [int]$Port = 8765,
    [int]$Width = 1672,
    [int]$Height = 941,
    [string]$BrowserPath = ""
)

$ErrorActionPreference = "Stop"

function Get-PngDimensions {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 24) {
        throw "PNG file is too small to contain a valid IHDR header: $Path"
    }

    $signature = @(137, 80, 78, 71, 13, 10, 26, 10)
    for ($i = 0; $i -lt $signature.Count; $i++) {
        if ($bytes[$i] -ne $signature[$i]) {
            throw "Screenshot is not a valid PNG file: $Path"
        }
    }

    $pngWidth = [System.BitConverter]::ToUInt32(@($bytes[19], $bytes[18], $bytes[17], $bytes[16]), 0)
    $pngHeight = [System.BitConverter]::ToUInt32(@($bytes[23], $bytes[22], $bytes[21], $bytes[20]), 0)

    [pscustomobject]@{
        Width = [int]$pngWidth
        Height = [int]$pngHeight
    }
}

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
        throw "Missing route layer: $candidate"
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
    throw "Python is required for the isolated visual-acceptance server."
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("maestro-splash-accept-" + [Guid]::NewGuid().ToString("N"))
$consoleDir = Join-Path $tempRoot "console"
New-Item -ItemType Directory -Force -Path $consoleDir | Out-Null

try {
    Copy-Item $splash (Join-Path $tempRoot "index.html")
    foreach ($route in $routeFiles) {
        Copy-Item (Join-Path $staticDir $route) (Join-Path $consoleDir $route)
    }

    $outDir = Split-Path -Parent $OutputPath
    if ($outDir) {
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    }
    if (Test-Path $OutputPath) {
        Remove-Item $OutputPath -Force
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
        throw "Visual-acceptance HTTP server did not become ready."
    }

    $browserArgs = @(
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--window-size=$Width,$Height",
        "--screenshot=$OutputPath",
        $url
    )
    $browser = Start-Process -FilePath $BrowserPath -ArgumentList $browserArgs -PassThru -Wait -NoNewWindow
    if ($browser.ExitCode -ne 0) {
        throw "Browser screenshot command failed with exit code $($browser.ExitCode)."
    }
    if (-not (Test-Path $OutputPath)) {
        throw "Browser did not produce screenshot: $OutputPath"
    }

    $dimensions = Get-PngDimensions -Path $OutputPath
    if ($dimensions.Width -ne $Width -or $dimensions.Height -ne $Height) {
        throw "Unexpected screenshot dimensions: $($dimensions.Width)x$($dimensions.Height); expected ${Width}x${Height}."
    }

    Write-Host "Splash visual acceptance capture complete." -ForegroundColor Green
    Write-Host "URL: $url"
    Write-Host "Viewport: ${Width}x${Height}"
    Write-Host "Screenshot: $OutputPath"
    Write-Host "Next gate: compare this screenshot with the approved reference image."
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
