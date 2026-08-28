[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function New-HexSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return -join ($buffer | ForEach-Object { $_.ToString('x2') })
}

function New-Base64Secret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer)
}

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install Docker Desktop (with Docker Compose) and retry."
    }
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host " Processual Maestro - Portable Evaluation Runtime" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""

Write-Step "Checking Docker"
Assert-Command docker
docker version --format '{{.Server.Version}}' | Out-Null
docker compose version | Out-Null

$EnvFile = Join-Path $Root '.env.evaluation'
if (-not (Test-Path $EnvFile)) {
    Write-Step "Creating isolated evaluation secrets"
    $jwt = New-HexSecret 48
    $apiKey = "pmk_eval_$(New-HexSecret 32)"
    $crypto = New-Base64Secret 32
    $admin = New-HexSecret 24
    $pg = New-HexSecret 24
    $redis = New-HexSecret 24
    $grafana = New-HexSecret 24
    $tokenPepper = New-HexSecret 32
    $ratePepper = New-HexSecret 32
    $deliveryKey = New-Base64Secret 32
    $mfaKey = New-Base64Secret 32
    $paymentKey = New-Base64Secret 32

    @"
ENVIRONMENT=development
APP_ENV=evaluation
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=info
API_DEBUG=false
JWT_SECRET=$jwt
API_KEYS=$apiKey
PROCESSUAL_CRYPTO_KEY_B64=$crypto
MAESTRO_ADMIN_EMAIL=evaluator@example.local
MAESTRO_ADMIN_PASSWORD=$admin
GRAFANA_ADMIN_PASSWORD=$grafana
AUTH_TOKEN_PEPPER=$tokenPepper
AUTH_RATE_LIMIT_PEPPER=$ratePepper
AUTH_DELIVERY_KEY_RING_JSON={"v1":"$deliveryKey"}
AUTH_DELIVERY_CURRENT_KEY_VERSION=v1
AUTH_MFA_KEY_RING_JSON={"v1":"$mfaKey"}
AUTH_MFA_CURRENT_KEY_VERSION=v1
ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON={"payment-v1":"$paymentKey"}
ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION=payment-v1
POSTGRES_USER=processual
POSTGRES_PASSWORD=$pg
POSTGRES_DB=processual_eval
REDIS_PASSWORD=$redis
MAESTRO_EVAL_PORT=8000
MAESTRO_EVAL_IMAGE_TAG=v1
RATE_LIMIT_ENABLED=true
AUDIT_ENABLED=true
CAPACITY_GUARD_ENABLED=true
CAPACITY_GLOBAL_LIMIT_OCU=20
CAPACITY_ACTOR_LIMIT_OCU=8
MAESTRO_TOP_UP_PURCHASE_ENABLED=false
MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED=false
MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED=false
LEMONSQUEEZY_API_KEY=
LEMONSQUEEZY_STORE_ID=
LEMONSQUEEZY_WEBHOOK_SECRET=
LLM_DEFAULT_PROVIDER=opencode
OPENCODE_API_URL=http://127.0.0.1:9/v1
OPENCODE_API_KEY=evaluation-disabled
"@ | Set-Content -Encoding utf8NoBOM $EnvFile
}

$imageReady = $null -ne (docker image inspect 'processual-maestro-evaluation:v1' 2>$null)
$offlineImages = Join-Path $Root 'images'
$sourceDockerfile = Join-Path (Split-Path -Parent $Root) 'Dockerfile'

if ($Rebuild) {
    if (-not (Test-Path $sourceDockerfile)) {
        throw '-Rebuild requires the source repository. Standalone bundles use the prebuilt image archives.'
    }
    Write-Step "Rebuilding the public evaluation image from source"
    docker build --target public -t processual-maestro-evaluation:v1 ..
    $imageReady = $true
}

if (-not $imageReady) {
    if (Test-Path $offlineImages) {
        Write-Step "Loading bundled Docker images"
        & (Join-Path $Root 'LOAD-OFFLINE-IMAGES.ps1')
        $imageReady = $null -ne (docker image inspect 'processual-maestro-evaluation:v1' 2>$null)
    } elseif (Test-Path $sourceDockerfile) {
        Write-Step "Building the public evaluation image from source"
        docker build --target public -t processual-maestro-evaluation:v1 ..
        $imageReady = $true
    }
}

if (-not $imageReady) {
    throw 'Evaluation image is unavailable. Use the official portable bundle with images/ or run from the source repository.'
}

Write-Step "Starting PostgreSQL, Redis and Processual Maestro"
docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml up -d

Write-Step "Waiting for API health"
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/health/live' -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    docker compose --env-file $EnvFile -f .\docker-compose.evaluation.yml ps
    docker logs maestro-eval-api --tail 120
    throw 'Evaluation API did not become healthy.'
}

Write-Host ""
Write-Host "READY - Processual Maestro Evaluation Runtime" -ForegroundColor Green
Write-Host "API:      http://localhost:8000" -ForegroundColor Green
Write-Host "Health:   http://localhost:8000/health/live" -ForegroundColor Green
Write-Host "Docs:     http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "External billing, Tunisia top-up and external LLM execution are disabled in this evaluation bundle." -ForegroundColor Yellow

if (-not $NoBrowser) {
    Start-Process 'http://localhost:8000/docs'
}
