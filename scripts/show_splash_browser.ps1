param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [int]$Port = 8765,
    [int]$Width = 1672,
    [int]$Height = 941,
    [string]$BrowserPath = "",
    [switch]$Incognito,
    [switch]$VisualReset
)

$ErrorActionPreference = "Stop"

$staticDir = Join-Path $RepoPath "processual_api\static"
$splash = Join-Path $staticDir "splash.html"
if (-not (Test-Path $splash)) {
    throw "Splash not found: $splash"
}

$visualAssets = @(
    "splash_reference_board.svg",
    "splash_routes_cyan.svg",
    "splash_routes_teal.svg",
    "splash_routes_lime.svg",
    "splash_routes_amber.svg",
    "splash_routes_violet.svg"
)
foreach ($asset in $visualAssets) {
    $candidate = Join-Path $staticDir $asset
    if (-not (Test-Path $candidate)) {
        throw "Missing splash visual asset: $candidate"
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
    $previewIndex = Join-Path $tempRoot "index.html"
    Copy-Item $splash $previewIndex

    if ($VisualReset) {
        $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
        $html = [System.IO.File]::ReadAllText($previewIndex, $utf8)
        $resetCss = @'
<style id="maestro-visual-reset-preview">
/* Preview-only reset: do not mutate canonical route assets. */
#pcb-reference,
.route-layer,
.pulse-layer { display:none !important; }
.core-shadow { opacity:.35 !important; filter:blur(10px) !important; }
.card.c1,.card.c2,.card.c3,.card.c4 { left:54px !important; }
.card.r1,.card.r2,.card.r3,.card.r4 { right:54px !important; }
.card { width:320px !important; height:132px !important; }
.card.c1,.card.r1 { top:96px !important; }
.card.c2,.card.r2 { top:252px !important; }
.card.c3,.card.r3 { top:408px !important; }
.card.c4,.card.r4 { top:564px !important; }
.core { left:619px !important; top:214px !important; width:433px !important; height:408px !important; transform:none !important; }
.core-shadow { left:588px !important; top:184px !important; width:495px !important; height:468px !important; }
.execution { left:758px !important; top:656px !important; }
.telemetry { bottom:60px !important; }
</style>
'@
        $html = $html.Replace('</head>', $resetCss + "`r`n</head>")
        [System.IO.File]::WriteAllText($previewIndex, $html, $utf8)
    }

    foreach ($asset in $visualAssets) {
        Copy-Item (Join-Path $staticDir $asset) (Join-Path $consoleDir $asset)
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

    Write-Host "MAESTRO living splash preview is running." -ForegroundColor Green
    Write-Host "URL: $url"
    Write-Host "Requested browser window: ${Width}x${Height}"
    Write-Host "Device scale factor: 1"
    Write-Host "Browser: $BrowserPath"
    if ($VisualReset) {
        Write-Host "Preview mode: VISUAL RESET (UTF-8 preserved; legacy route layers hidden; layout spread for review)." -ForegroundColor Yellow
    } else {
        Write-Host "Preview mode: current branch presentation."
    }
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
