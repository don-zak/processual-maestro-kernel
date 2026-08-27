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
    [switch]$FullViewport
)

$ErrorActionPreference = "Stop"

$staticDir = Join-Path $RepoPath "processual_api\static"
$splash = Join-Path $staticDir "splash.html"
if (-not (Test-Path $splash)) {
    throw "Splash not found: $splash"
}

if ($SurfaceRouteReview -or $CanonicalNetworkReview) {
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

    if ($VisualReset -or $FurnishReview -or $SurfaceRouteReview -or $CanonicalNetworkReview -or $FullViewport) {
        $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
        $html = [System.IO.File]::ReadAllText($previewIndex, $utf8)

        $previewCss = @'
<style id="maestro-preview-overrides">
html,body,.viewport { width:100% !important; height:100% !important; margin:0 !important; overflow:hidden !important; }
'@
        if ($VisualReset) {
            $previewCss += @'
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
'@
        }
        if ($FurnishReview) {
            $previewCss += @'
/* Review actual furnished production layout with legacy route assets isolated. */
#pcb-reference,
.route-layer,
.pulse-layer { display:none !important; }
'@
        }
        if ($SurfaceRouteReview) {
            $previewCss += @'
/* Review the furnished layout with simplified surface routing only. */
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
/* Directly render the original five-family route assets with edge-only SVG filters. */
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
.route-layer.cyan {
    opacity:.72 !important;
    filter:url(#canonical-route-edge-cyan) drop-shadow(0 0 .6px #16d9ff) !important;
}
.route-layer.teal {
    filter:url(#canonical-route-edge) drop-shadow(0 0 .7px #18f5e9) !important;
}
.route-layer.lime {
    filter:url(#canonical-route-edge) drop-shadow(0 0 .7px #a6ff43) !important;
}
.route-layer.amber {
    filter:url(#canonical-route-edge) drop-shadow(0 0 .7px #ffad1f) !important;
}
.route-layer.violet {
    filter:url(#canonical-route-edge) drop-shadow(0 0 .7px #d36cff) !important;
}
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
        if ($CanonicalNetworkReview) {
            $filterDefs = @'
<svg id="canonical-route-filter-defs" aria-hidden="true" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden">
  <defs>
    <filter id="canonical-route-edge" x="0" y="0" width="1672" height="941" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
      <feMorphology in="SourceAlpha" operator="erode" radius="1.15" result="eroded"/>
      <feComposite in="SourceGraphic" in2="eroded" operator="out" result="edge"/>
      <feGaussianBlur in="edge" stdDeviation="0.2" result="soft"/>
      <feMerge><feMergeNode in="soft"/><feMergeNode in="edge"/></feMerge>
    </filter>
    <filter id="canonical-route-edge-cyan" x="0" y="0" width="1672" height="941" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
      <feMorphology in="SourceAlpha" operator="erode" radius="1.75" result="eroded"/>
      <feComposite in="SourceGraphic" in2="eroded" operator="out" result="edge"/>
      <feGaussianBlur in="edge" stdDeviation="0.16" result="soft"/>
      <feMerge><feMergeNode in="soft"/><feMergeNode in="edge"/></feMerge>
    </filter>
  </defs>
</svg>
'@
            $html = $html.Replace($coreShadowMarkup, $filterDefs + "`r`n" + $coreShadowMarkup)
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
    if ($CanonicalNetworkReview) {
        Write-Host "Preview mode: CANONICAL NETWORK REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
        Write-Host "Original five route SVGs are rendered directly; edge-only filtering suppresses filled blotches." -ForegroundColor Yellow
    } elseif ($SurfaceRouteReview) {
        Write-Host "Preview mode: SURFACE ROUTE REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
        Write-Host "Side cards: expanded outward; legacy route layers: isolated; simplified surface routes: enabled." -ForegroundColor Yellow
    } elseif ($FurnishReview -and $FullViewport) {
        Write-Host "Preview mode: FURNISH REVIEW + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($FurnishReview) {
        Write-Host "Preview mode: FURNISH REVIEW (legacy route layers hidden)." -ForegroundColor Yellow
    } elseif ($VisualReset -and $FullViewport) {
        Write-Host "Preview mode: VISUAL RESET + FULL VIEWPORT." -ForegroundColor Yellow
    } elseif ($VisualReset) {
        Write-Host "Preview mode: VISUAL RESET (UTF-8 preserved; legacy route layers hidden)." -ForegroundColor Yellow
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
