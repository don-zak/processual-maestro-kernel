param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [int]$Port = 8765,
    [int]$Width = 1672,
    [int]$Height = 941,
    [string]$BrowserPath = "",
    [switch]$Incognito,
    [switch]$VisualReset,
    [switch]$FurnishReview,
    [switch]$SurfaceRouteReview,
    [switch]$CanonicalNetworkReview,
    [switch]$RouteMapV2Review,
    [switch]$FullViewport
)

$ErrorActionPreference = "Stop"

$staticDir = Join-Path $RepoPath "processual_api\static"
$splash = Join-Path $staticDir "splash.html"
if (-not (Test-Path $splash)) {
    throw "Splash not found: $splash"
}

if ($SurfaceRouteReview -or $CanonicalNetworkReview -or $RouteMapV2Review) {
    $FullViewport = $true
}

$visualAssets = @(
    "splash_reference_board.svg",
    "splash_routes_cyan.svg",
    "splash_routes_teal.svg",
    "splash_routes_lime.svg",
    "splash_routes_amber.svg",
    "splash_routes_violet.svg",
    "splash_surface_routes_review.svg"
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

    if ($VisualReset -or $FurnishReview -or $SurfaceRouteReview -or $CanonicalNetworkReview -or $RouteMapV2Review -or $FullViewport) {
        $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
        $html = [System.IO.File]::ReadAllText($previewIndex, $utf8)

        $previewCss = @'
<style id="maestro-preview-overrides">
html,body,.viewport { width:100% !important; height:100% !important; margin:0 !important; overflow:hidden !important; }
'@
        if ($VisualReset) {
            $previewCss += @'
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
'@
        }
        if ($FurnishReview) {
            $previewCss += @'
#pcb-reference,
.route-layer,
.pulse-layer { display:none !important; }
'@
        }
        if ($SurfaceRouteReview) {
            $previewCss += @'
#pcb-reference,
.route-layer,
.pulse-layer { display:none !important; }
.card.c1,.card.c2,.card.c3,.card.c4 { left:40px !important; }
.card.r1,.card.r2,.card.r3,.card.r4 { right:49px !important; }
.surface-route-review-layer {
    position:absolute !important;
    inset:0 !important;
    width:1672px !important;
    height:941px !important;
    z-index:4 !important;
    pointer-events:none !important;
    user-select:none !important;
}
'@
        }
        if ($CanonicalNetworkReview) {
            $previewCss += @'
#pcb-reference,
.pulse-layer,
.surface-route-review-layer { display:none !important; }
.card.c1,.card.c2,.card.c3,.card.c4 { left:40px !important; }
.card.r1,.card.r2,.card.r3,.card.r4 { right:49px !important; }
.route-layer {
    display:block !important;
    position:absolute !important;
    inset:0 !important;
    width:1672px !important;
    height:941px !important;
    z-index:4 !important;
    pointer-events:none !important;
    user-select:none !important;
    object-fit:contain !important;
    opacity:.86 !important;
    mix-blend-mode:screen !important;
}
'@
        }
        if ($RouteMapV2Review) {
            $previewCss += @'
/* Approved Route Map v2 review: direct route assets, expanded card spacing, original MAESTRO logo. */
#pcb-reference,
.surface-route-review-layer { display:none !important; }
.card.c1,.card.c2,.card.c3,.card.c4 { left:40px !important; }
.card.r1,.card.r2,.card.r3,.card.r4 { right:49px !important; }
.route-layer {
    display:block !important;
    position:absolute !important;
    inset:0 !important;
    width:1672px !important;
    height:941px !important;
    z-index:4 !important;
    pointer-events:none !important;
    user-select:none !important;
    object-fit:contain !important;
    opacity:.92 !important;
    mix-blend-mode:screen !important;
}
.route-layer.cyan { opacity:.90 !important; filter:drop-shadow(0 0 1.1px #16d9ff) !important; }
.route-layer.teal { filter:drop-shadow(0 0 1.1px #18f5e9) !important; }
.route-layer.lime { filter:drop-shadow(0 0 1.1px #a6ff43) !important; }
.route-layer.amber { filter:drop-shadow(0 0 1.15px #ffad1f) !important; }
.route-layer.violet { filter:drop-shadow(0 0 1.1px #d36cff) !important; }
.brand { gap:10px !important; }
.brand-mark {
    width:34px !important;
    height:34px !important;
    border:1px solid rgba(255,173,31,.42) !important;
    border-radius:6px !important;
    clip-path:none !important;
    display:grid !important;
    place-items:center !important;
    color:#f3f7ff !important;
    background:linear-gradient(145deg,rgba(255,173,31,.08),rgba(4,14,28,.72)) !important;
    filter:drop-shadow(0 0 7px rgba(255,173,31,.24)) !important;
}
.brand-mark:before {
    content:"♔" !important;
    position:static !important;
    inset:auto !important;
    clip-path:none !important;
    border:0 !important;
    font:700 22px/1 Georgia,"Times New Roman",serif !important;
    color:#f4f7fb !important;
    text-shadow:0 0 6px rgba(255,255,255,.28) !important;
}
.brand-mark:after,.brand-mark i { display:none !important; }
'@
        }
        if ($FullViewport) {
            $previewCss += @'
.viewport { display:block !important; background:#020712 !important; }
.stage { position:absolute !important; left:0 !important; top:0 !important; width:1672px !important; height:941px !important; transform-origin:0 0 !important; }
'@
        }
        $previewCss += "`r`n</style>"
        $html = $html.Replace('</head>', $previewCss + "`r`n</head>")

        $coreShadowMarkup = '<div class="core-shadow"></div>'
        if ($SurfaceRouteReview) {
            $routeLayer = @'
<img class="surface-route-review-layer" src="/console/splash_surface_routes_review.svg" alt="" aria-hidden="true">
'@
            $html = $html.Replace($coreShadowMarkup, $routeLayer + "`r`n" + $coreShadowMarkup)
        }

        if ($FullViewport) {
            $fullViewportScript = @'
<script id="maestro-full-viewport-preview">
(() => {
  const applyFullViewport = () => {
    const stage = document.getElementById('stage');
    if (!stage) return;
    const sx = window.innerWidth / 1672;
    const sy = window.innerHeight / 941;
    stage.style.setProperty('transform', `scale(${sx}, ${sy})`, 'important');
    stage.style.setProperty('transform-origin', '0 0', 'important');
  };
  window.addEventListener('resize', applyFullViewport, { passive: true });
  requestAnimationFrame(() => requestAnimationFrame(applyFullViewport));
})();
</script>
'@
            $html = $html.Replace('</body>', $fullViewportScript + "`r`n</body>")
        }

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

    $browserArgs = @("--force-device-scale-factor=1")
    if ($FullViewport) {
        $browserArgs += @("--app=$url", "--start-maximized")
    } else {
        $browserArgs += @("--new-window", "--window-size=$Width,$Height")
        if ($Incognito) {
            $browserArgs += "--incognito"
        }
        $browserArgs += $url
    }

    Start-Process -FilePath $BrowserPath -ArgumentList $browserArgs | Out-Null

    Write-Host "MAESTRO living splash preview is running." -ForegroundColor Green
    Write-Host "URL: $url"
    Write-Host "Device scale factor: 1"
    Write-Host "Browser: $BrowserPath"
    if ($RouteMapV2Review) {
        Write-Host "Preview mode: ROUTE MAP V2 + FULL VIEWPORT." -ForegroundColor Yellow
        Write-Host "Approved clean route network enabled; side cards expanded; original MAESTRO logo restored." -ForegroundColor Yellow
    } elseif ($CanonicalNetworkReview) {
        Write-Host "Preview mode: CANONICAL NETWORK REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($SurfaceRouteReview) {
        Write-Host "Preview mode: SURFACE ROUTE REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($FurnishReview -and $FullViewport) {
        Write-Host "Preview mode: FURNISH REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($FurnishReview) {
        Write-Host "Preview mode: FURNISH REVIEW." -ForegroundColor Yellow
    } elseif ($VisualReset -and $FullViewport) {
        Write-Host "Preview mode: VISUAL RESET + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($VisualReset) {
        Write-Host "Preview mode: VISUAL RESET." -ForegroundColor Yellow
    } elseif ($FullViewport) {
        Write-Host "Preview mode: FULL VIEWPORT." -ForegroundColor Yellow
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
