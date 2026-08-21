param(
    [int]$Port = 8000,
    [string]$DatabaseFile = ".pmk-local-review.sqlite3",
    [switch]$ResetDatabase,
    [switch]$NoBrowser,
    [switch]$IncludeAuthenticatedSurfaces,
    [int]$ReadyTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envScript = Join-Path $PSScriptRoot "local_review_env.ps1"
$bootstrapScript = Join-Path $PSScriptRoot "bootstrap_local_review.ps1"

if (-not (Test-Path $envScript)) { throw "Missing local review environment script: $envScript" }
if (-not (Test-Path $bootstrapScript)) { throw "Missing local review bootstrap script: $bootstrapScript" }

. $envScript
$context = Set-PmkLocalReviewEnvironment -DatabaseFile $DatabaseFile

function Stop-StaleLocalReviewServers {
    $stopped = [System.Collections.Generic.List[int]]::new()
    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.Name -match '^python(\.exe)?$' -and
            $_.CommandLine -match 'uvicorn' -and
            $_.CommandLine -match 'processual_api\.main:app' -and
            $_.CommandLine -match '--no-access-log'
        }
    } catch {
        Write-Host "Unable to enumerate prior local-review processes; continuing without automatic cleanup." -ForegroundColor Yellow
        return @()
    }

    foreach ($process in @($processes)) {
        $pidValue = [int]$process.ProcessId
        if ($pidValue -eq $PID) { continue }
        Write-Host "Stopping stale local-review server PID $pidValue before database reset..."
        try {
            Stop-Process -Id $pidValue -Force -ErrorAction Stop
            $stopped.Add($pidValue)
        } catch {
            throw "Unable to stop stale local-review server PID $pidValue. Stop it manually and retry."
        }
    }

    if ($stopped.Count -gt 0) { Start-Sleep -Milliseconds 800 }
    return @($stopped)
}

if ($ResetDatabase) {
    $releasedPids = @(Stop-StaleLocalReviewServers)
    if ($releasedPids.Count -gt 0) {
        Write-Host "Released $($releasedPids.Count) stale local-review server process(es)."
    }
}

$bootstrapArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $bootstrapScript, "-DatabaseFile", $DatabaseFile)
if ($ResetDatabase) { $bootstrapArgs += "-ResetDatabase" }

Write-Host "=== Processual Maestro Full Local Web Review ==="
Write-Host "Preparing the local review database and application state..."
& powershell @bootstrapArgs
if ($LASTEXITCODE -ne 0) { throw "Local review bootstrap failed with exit code $LASTEXITCODE" }

$base = "http://127.0.0.1:$Port"
$serverArgs = @("-m", "uvicorn", "processual_api.main:app", "--host", "127.0.0.1", "--port", "$Port", "--no-access-log")
Write-Host "Starting the web server on $base ..."
$server = Start-Process -FilePath "python" -ArgumentList $serverArgs -WorkingDirectory $repoRoot -PassThru

function Stop-ReviewServer {
    if ($null -ne $server -and -not $server.HasExited) {
        try { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
}

try {
    $readyUrl = "$base/health/ready"
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($server.HasExited) { throw "Local review server exited before becoming ready." }
        try {
            $response = Invoke-WebRequest -Uri $readyUrl -UseBasicParsing -TimeoutSec 3
            if ([int]$response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 750 }
    }
    if (-not $ready) { throw "Local review server did not become ready within $ReadyTimeoutSeconds seconds." }

    $publicPages = [System.Collections.Generic.List[object]]::new()
    $publicPages.Add([pscustomobject]@{ Name = "Public entry / splash"; Path = "/" })
    $publicPages.Add([pscustomobject]@{ Name = "Plans"; Path = "/plans" })
    $publicPages.Add([pscustomobject]@{ Name = "Pricing"; Path = "/pricing" })
    $publicPages.Add([pscustomobject]@{ Name = "Registration"; Path = "/register" })
    $publicPages.Add([pscustomobject]@{ Name = "Registration MFA layout review"; Path = "/register?review_mfa=1" })
    $publicPages.Add([pscustomobject]@{ Name = "Email verification"; Path = "/verify-email" })
    $publicPages.Add([pscustomobject]@{ Name = "Sign in"; Path = "/login" })

    $catalogUrl = "$base/billing/public-plan-journey"
    $catalog = Invoke-RestMethod -Uri $catalogUrl -Method Get -TimeoutSec 10
    foreach ($plan in @($catalog.plans)) {
        if ($null -eq $plan.plan_id -or [string]::IsNullOrWhiteSpace([string]$plan.plan_id)) { continue }
        $encodedPlan = [System.Uri]::EscapeDataString([string]$plan.plan_id)
        $publicPages.Add([pscustomobject]@{ Name = "Offer: $($plan.display_name)"; Path = "/offer/$encodedPlan" })
        if ($plan.requires_assessment -or -not $plan.registration_available) {
            $publicPages.Add([pscustomobject]@{
                Name = "Assessment request: $($plan.display_name)"
                Path = "/console/apply.html?plan_id=$encodedPlan&journey=assessment"
            })
        }
    }

    $reviewPages = [System.Collections.Generic.List[object]]::new()
    foreach ($item in $publicPages) { $reviewPages.Add($item) }
    if ($IncludeAuthenticatedSurfaces) {
        $reviewPages.Add([pscustomobject]@{ Name = "Console shell (requires normal sign-in session)"; Path = "/console/" })
        $reviewPages.Add([pscustomobject]@{ Name = "Admin shell (requires normal sign-in session)"; Path = "/admin" })
    }

    $results = [System.Collections.Generic.List[object]]::new()
    Write-Host ""
    Write-Host "HTTP review inventory"
    foreach ($item in $reviewPages) {
        $url = "$base$($item.Path)"
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 10
            $status = [int]$response.StatusCode
            $ok = $status -eq 200
            $results.Add([pscustomobject]@{ name=$item.Name; path=$item.Path; url=$url; status=$status; ok=$ok })
            if ($ok) { Write-Host "[OK]   $($item.Name) -> HTTP $status" }
            else { Write-Host "[FAIL] $($item.Name) -> HTTP $status" -ForegroundColor Red }
        } catch {
            $results.Add([pscustomobject]@{ name=$item.Name; path=$item.Path; url=$url; status=$null; ok=$false; error=$_.Exception.Message })
            Write-Host "[FAIL] $($item.Name) -> $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    $failed = @($results | Where-Object { -not $_.ok })
    if ($failed.Count -gt 0) { throw "Full local web review found $($failed.Count) HTTP page failure(s). Browser launch was stopped." }

    $evidenceDir = Join-Path $repoRoot ".pmk-local-review"
    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $reportPath = Join-Path $evidenceDir "full-web-review-$stamp.json"
    $head = (& git -C $repoRoot rev-parse HEAD 2>$null)
    $report = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        source_head = $head
        base_url = $base
        server_pid = $server.Id
        mode = "local_public_web_acceptance"
        browser_policy = "normal public entry; no authentication/session bypass"
        authority = [ordered]@{ real_staging_qualified=$false; production_authority_granted=$false }
        pages = @($results)
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8

    Write-Host ""
    Write-Host "All declared review pages returned HTTP 200."
    Write-Host "Evidence report: $reportPath"
    Write-Host "Server PID:      $($server.Id)"
    Write-Host ""
    Write-Host "Browser review policy:"
    Write-Host "- The first page is the public root URL, exactly as a normal visitor enters the site."
    Write-Host "- No token, session state, role, or authentication state is injected by this script."
    Write-Host "- Assessment request pages are discovered only for assessment-only offers."
    Write-Host "- Registration MFA review is layout-only; real enrollment remains after email verification and authenticated sign-in."
    Write-Host "- Console/Admin are only added when -IncludeAuthenticatedSurfaces is supplied and still require normal sign-in."
    Write-Host "- This is local public-web acceptance only; it grants no Real Staging or production authority."

    if (-not $NoBrowser) {
        Write-Host ""
        Write-Host "Opening public review pages in the default browser..."
        foreach ($item in $publicPages) { Start-Process "$base$($item.Path)"; Start-Sleep -Milliseconds 180 }
        if ($IncludeAuthenticatedSurfaces) { Start-Process "$base/console/"; Start-Sleep -Milliseconds 180; Start-Process "$base/admin" }
    }

    Write-Host ""
    Write-Host "Review checklist:"
    Write-Host "1. Start at the splash/root page and follow the public journey without using direct authenticated URLs."
    Write-Host "2. Inspect every plan card, price, discount, quota statement, CTA, BYOK statement, and responsive layout."
    Write-Host "3. Open every generated offer tab and verify its plan-specific price/capacity/assessment language."
    Write-Host "4. For every assessment-only offer, open its assessment request page and verify selected-plan context and form behavior."
    Write-Host "5. Compare normal registration with the review_mfa=1 tab; the MFA preview must stay inside the card without overlap or horizontal overflow."
    Write-Host "6. Follow registration and email verification flows; real MFA enrollment remains after verified sign-in."
    Write-Host "7. Sign in normally and review Console/Admin; in Admin API Keys confirm External Evaluation Access is available in Category."
    Write-Host "8. Confirm the Console exposes no AR language control; Tutorial remains the only Arabic-capable surface."
    Write-Host "9. Expand Lost Access on short/narrow login viewports and confirm the full card remains reachable by vertical scrolling."
    Write-Host "10. Review a real MFA challenge only with your own local credentials; never copy MFA or recovery secrets into evidence."
    Write-Host "11. Record every defect against source HEAD $head before any Real Staging decision."
    Write-Host ""
    Write-Host "The server remains running after this script exits."
    Write-Host "Stop it when finished with: Stop-Process -Id $($server.Id)"
} catch {
    Stop-ReviewServer
    throw
}
