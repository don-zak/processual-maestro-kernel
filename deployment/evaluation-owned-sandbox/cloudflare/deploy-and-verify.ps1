param(
    [Parameter(Mandatory = $false)]
    [string]$ExpectedGitSha,

    [Parameter(Mandatory = $false)]
    [string]$WorkerUrl = 'https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-Equal {
    param([object]$Actual, [object]$Expected, [string]$Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected=[$Expected] Actual=[$Actual]"
    }
}

function Assert-False {
    param([object]$Value, [string]$Message)
    if ($Value -ne $false) {
        throw "$Message Expected=false Actual=[$Value]"
    }
}

function Assert-CloudflareCredential {
    param([string]$Name, [string]$Value, [string]$AllowedPattern)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required when environment-variable authentication is selected."
    }
    $normalized = $Value.Trim()
    if (
        $normalized.Contains('<') -or
        $normalized.Contains('>') -or
        $normalized -match '(?i)^(token|account-id|account_id|placeholder)$' -or
        $normalized -match '(?i)^(real[_-]?(token|api[_-]?token|account[_-]?id)[_-]?here)$' -or
        $normalized -match '(?i)^(paste[_-]?the[_-]?real[_-]?(token|api[_-]?token|account[_-]?id))$' -or
        $normalized -match '(?i)(replace|example|dummy|your[_-]?)(token|account[_-]?id)'
    ) {
        throw "$Name still contains an example/placeholder value. Set the real Cloudflare credential or remove both Cloudflare credential environment variables and use 'wrangler login'."
    }
    if ($AllowedPattern -and $normalized -notmatch $AllowedPattern) {
        throw "$Name has an invalid format for Cloudflare deployment."
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Push-Location $RepoRoot
try {
    $CurrentSha = (git rev-parse HEAD).Trim()
    if (-not $ExpectedGitSha) {
        $ExpectedGitSha = $CurrentSha
    }
    Assert-Equal $CurrentSha $ExpectedGitSha 'Refusing to deploy a checkout different from the approved exact SHA.'

    $WorkingTreeChanges = @(git status --porcelain)
    if ($WorkingTreeChanges.Count -ne 0) {
        throw 'Refusing to deploy from a dirty working tree.'
    }

    $HasApiToken = -not [string]::IsNullOrWhiteSpace($env:CLOUDFLARE_API_TOKEN)
    $HasAccountId = -not [string]::IsNullOrWhiteSpace($env:CLOUDFLARE_ACCOUNT_ID)

    if ($HasApiToken -or $HasAccountId) {
        if (-not ($HasApiToken -and $HasAccountId)) {
            throw "Cloudflare environment-variable authentication is incomplete. Set both CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID, or remove both and use 'wrangler login'."
        }
        Assert-CloudflareCredential -Name 'CLOUDFLARE_API_TOKEN' -Value $env:CLOUDFLARE_API_TOKEN -AllowedPattern '^[\x21-\x7E]+$'
        Assert-CloudflareCredential -Name 'CLOUDFLARE_ACCOUNT_ID' -Value $env:CLOUDFLARE_ACCOUNT_ID -AllowedPattern '^[0-9A-Fa-f]{32}$'
        Write-Host 'Cloudflare authentication: validated environment variables.'
    }
    else {
        Write-Host 'Cloudflare authentication: validating local Wrangler OAuth session...'
        npx --yes wrangler@4.131.1 whoami | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "No usable Cloudflare environment credentials and Wrangler OAuth is not authenticated. Run 'npx --yes wrangler@4.131.1 login' first."
        }
        Write-Host 'Cloudflare authentication: Wrangler OAuth session verified.'
    }

    Write-Host "[1/6] Exact source SHA verified: $CurrentSha"

    Write-Host '[2/6] Running verified owned scenario and Admin fail-closed regression tests...'
    python -m pytest `
        tests/test_external_evaluation_owned_crm_scenarios.py `
        tests/test_external_evaluation_owned_integration_scenarios.py `
        tests/test_admin_evaluation_owned_preset_catalog.py `
        -q
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; Worker was not deployed.' }

    Write-Host '[3/6] Deploying pinned Wrangler contract...'
    Push-Location (Join-Path $RepoRoot 'deployment\evaluation-owned-sandbox\cloudflare')
    try {
        npx --yes wrangler@4.131.1 deploy --config wrangler.jsonc
        if ($LASTEXITCODE -ne 0) { throw 'Wrangler deploy failed.' }
    } finally {
        Pop-Location
    }

    $Base = $WorkerUrl.TrimEnd('/')
    Write-Host "[4/6] Verifying live Worker health at $Base ..."
    $Health = Invoke-RestMethod -Method Get -Uri "$Base/health/live" -Headers @{ 'Cache-Control' = 'no-cache' }
    Assert-Equal $Health.status 'live' 'Worker health status mismatch.'
    Assert-False $Health.production_allowed 'Worker health unexpectedly permits production.'

    Write-Host '[5/6] Verifying CRM Summary and Integration Billing read fixtures...'
    $Customer = Invoke-RestMethod -Method Get -Uri "$Base/users/1"
    Assert-Equal $Customer.id 1 'CRM customer fixture id mismatch.'
    Assert-Equal $Customer.account_status 'active' 'CRM account_status mismatch.'
    Assert-Equal $Customer.segment 'evaluation' 'CRM segment mismatch.'

    $Billing = Invoke-RestMethod -Method Get -Uri "$Base/billing/accounts/1"
    Assert-Equal $Billing.account_id 'sandbox-account-001' 'Billing account fixture mismatch.'
    Assert-Equal $Billing.currency 'USD' 'Billing currency mismatch.'
    Assert-False $Billing.production_allowed 'Billing fixture unexpectedly permits production.'

    Write-Host '[6/6] Verifying CRM Draft is review-only and never applied...'
    $DraftBody = @{
        customer_id = 'sandbox-customer-001'
        proposed_changes = @{ segment = 'evaluation-review' }
    } | ConvertTo-Json -Depth 6
    $Draft = Invoke-RestMethod -Method Post -Uri "$Base/users/1/update-draft" -ContentType 'application/json' -Body $DraftBody
    Assert-Equal $Draft.customer_id 'sandbox-customer-001' 'Draft customer id mismatch.'
    Assert-Equal $Draft.draft_only $true 'Draft route is not marked draft_only.'
    Assert-Equal $Draft.review_required $true 'Draft route does not require review.'
    Assert-False $Draft.applied 'Draft route unexpectedly applied a change.'
    Assert-False $Draft.production_allowed 'Draft route unexpectedly permits production.'

    Write-Host ''
    Write-Host 'PASS: Updated External Evaluation Worker is deployed and all live owned scenarios returned their required safety contract.'
    Write-Host "Qualified deployment candidate SHA: $CurrentSha"
    Write-Host 'Next gate: use Platform Admin preset controls to persist/prove bindings, then issue fresh CRM and Integration Evaluation Grants/keys and execute Workspace qualification.'
}
finally {
    Pop-Location
}
