[CmdletBinding()]
param(
    [ValidateSet('durable', 'load', 'soak', 'all')]
    [string]$Mode = 'all',

    [switch]$Include16Workers,

    [string]$PythonBin = 'python',

    [string]$ResultsDir = 'local-qualification-results',

    [int]$RedisPort = 16379,

    [int]$PostgresPort = 15432
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RedisContainer = 'pmk-local-qualification-redis'
$PostgresContainer = 'pmk-local-qualification-postgres'
$RedisQualificationUrl = "redis://127.0.0.1:$RedisPort/15"
$RedisRuntimeUrl = "redis://127.0.0.1:$RedisPort/0"
$DatabaseUrl = "postgresql+asyncpg://maestro:local-benchmark-password@127.0.0.1:$PostgresPort/maestro"

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

function Assert-Command {
    param([Parameter(Mandatory)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $($Arguments -join ' ')"
    }
}

function Stop-QualificationContainers {
    & docker rm -f $RedisContainer $PostgresContainer *> $null
}

function Start-QualificationRedis {
    & docker rm -f $RedisContainer *> $null
    Invoke-Checked docker @('run', '-d', '--name', $RedisContainer, '-p', "${RedisPort}:6379", 'redis:7')

    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $pong = & docker exec $RedisContainer redis-cli ping 2>$null
        if ($LASTEXITCODE -eq 0 -and $pong -match 'PONG') {
            return
        }
        Start-Sleep -Seconds 1
    }

    throw 'Redis did not become ready.'
}

function Start-QualificationPostgres {
    & docker rm -f $PostgresContainer *> $null
    Invoke-Checked docker @(
        'run', '-d', '--name', $PostgresContainer,
        '-e', 'POSTGRES_USER=maestro',
        '-e', 'POSTGRES_PASSWORD=local-benchmark-password',
        '-e', 'POSTGRES_DB=maestro',
        '-p', "${PostgresPort}:5432",
        'postgres:17'
    )

    for ($attempt = 1; $attempt -le 45; $attempt++) {
        & docker exec $PostgresContainer pg_isready -U maestro -d maestro *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    }

    throw 'Postgres did not become ready.'
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$Attempts = 30
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            # Service is still starting.
        }
        Start-Sleep -Seconds 1
    }

    throw "Service did not become ready: $Url"
}

function Start-PythonServer {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$StdoutPath,
        [Parameter(Mandatory)][string]$StderrPath
    )

    return Start-Process \
        -FilePath $PythonBin \
        -ArgumentList $Arguments \
        -PassThru \
        -NoNewWindow \
        -RedirectStandardOutput $StdoutPath \
        -RedirectStandardError $StderrPath
}

function Stop-ProcessSafely {
    param($Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit()
    }
}

function Run-DurableQualification {
    Write-Host '== Durable real-Redis qualification =='
    Start-QualificationRedis

    $env:TEST_REDIS_URL = $RedisQualificationUrl
    $env:PYTHONPATH = '.'

    $testOutput = Join-Path $ResultsDir 'durable-tests.txt'
    & $PythonBin -m pytest -q \
        tests/test_adaptive_concurrency.py \
        tests/test_adaptive_pool_gate.py \
        tests/test_execution_domain_capacity.py \
        tests/test_durable_redis_qualification.py \
        tests/test_durable_resilience_qualification.py 2>&1 | Tee-Object -FilePath $testOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Durable qualification tests failed with exit code $LASTEXITCODE."
    }

    $scaleOutput = Join-Path $ResultsDir 'durable-1-2-4-8.json'
    & $PythonBin benchmarks/durable_worker_scale.py \
        --redis-url $RedisQualificationUrl \
        --workers '1,2,4,8' \
        --jobs 384 \
        --handler-delay-ms 20 \
        --repetitions 5 \
        --redis-telemetry 2>&1 | Tee-Object -FilePath $scaleOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Durable scale qualification failed with exit code $LASTEXITCODE."
    }

    if ($Include16Workers) {
        $scale16Output = Join-Path $ResultsDir 'durable-16.json'
        & $PythonBin benchmarks/durable_worker_scale.py \
            --redis-url $RedisQualificationUrl \
            --workers 16 \
            --jobs 384 \
            --handler-delay-ms 20 \
            --repetitions 5 \
            --redis-telemetry 2>&1 | Tee-Object -FilePath $scale16Output
        if ($LASTEXITCODE -ne 0) {
            throw "16-worker qualification failed with exit code $LASTEXITCODE."
        }
    }
}

function Run-LoadQualification {
    Write-Host '== Local HTTP/load qualification =='
    Start-QualificationRedis
    Start-QualificationPostgres

    $env:ENVIRONMENT = 'development'
    $env:DATABASE_URL = $DatabaseUrl
    $env:REDIS_URL = $RedisRuntimeUrl
    $env:JWT_SECRET = 'local-benchmark-only-jwt-secret'
    $env:API_KEYS = 'local-benchmark-only-api-key'
    $env:POSTGRES_PASSWORD = 'local-benchmark-password'
    $env:REDIS_PASSWORD = 'local-benchmark-password'
    $env:GRAFANA_ADMIN_PASSWORD = 'local-benchmark-password'
    $env:RATE_LIMIT_ENABLED = 'false'

    $serverOut = Join-Path $ResultsDir 'load-server.stdout.log'
    $serverErr = Join-Path $ResultsDir 'load-server.stderr.log'
    $server = $null

    try {
        $server = Start-PythonServer \
            -Arguments @('-m', 'uvicorn', 'processual_api.main:app', '--host', '127.0.0.1', '--port', '8000') \
            -StdoutPath $serverOut \
            -StderrPath $serverErr

        Wait-HttpReady -Url 'http://127.0.0.1:8000/health/live'

        & $PythonBin benchmarks/load_probe.py \
            --name http-live \
            --path /health/live \
            --concurrency '1,5,10,20,40,80,120' \
            --requests 300 \
            --output (Join-Path $ResultsDir 'http-live.json') 2>&1 |
            Tee-Object -FilePath (Join-Path $ResultsDir 'http-live.txt')
        if ($LASTEXITCODE -ne 0) { throw 'HTTP live load probe failed.' }

        & $PythonBin benchmarks/load_probe.py \
            --name dependency-ready \
            --path /health/ready \
            --concurrency '1,5,10,20,40,80,120' \
            --requests 200 \
            --output (Join-Path $ResultsDir 'dependency-ready.json') 2>&1 |
            Tee-Object -FilePath (Join-Path $ResultsDir 'dependency-ready.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency-ready load probe failed.' }

        & $PythonBin benchmarks/workload_probe.py \
            --concurrency '1,5,10,20,40' \
            --light-requests 200 \
            --normal-requests 160 \
            --heavy-requests 80 \
            --output (Join-Path $ResultsDir 'workloads.json') 2>&1 |
            Tee-Object -FilePath (Join-Path $ResultsDir 'workloads.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Workload probe failed.' }

        Invoke-Checked $PythonBin @('benchmarks/performance_guard.py', (Join-Path $ResultsDir 'workloads.json'))
    }
    finally {
        Stop-ProcessSafely $server
    }
}

function Run-SoakQualification {
    Write-Host '== Multi-process orchestration soak =='
    Start-QualificationRedis

    $env:PYTHONPATH = '.'
    $env:ENVIRONMENT = 'development'
    $env:REDIS_URL = $RedisRuntimeUrl
    $env:JWT_SECRET = 'local-benchmark-only-jwt-secret'
    $env:API_KEYS = 'local-benchmark-only-api-key'
    $env:RATE_LIMIT_ENABLED = 'false'
    $env:CAPACITY_GUARD_ENABLED = 'false'
    $env:EXECUTION_FANOUT_ENABLED = 'true'
    $env:EXECUTION_FANOUT_GLOBAL_LIMIT = '16'
    $env:EXECUTION_FANOUT_PROVIDER_LIMIT = '8'
    $env:EXECUTION_FANOUT_WAIT_MS = '250'

    $soakTestOutput = Join-Path $ResultsDir 'orchestration-soak-tests.txt'
    & $PythonBin -m pytest -q tests/test_orchestration_api_soak.py 2>&1 |
        Tee-Object -FilePath $soakTestOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Orchestration soak tests failed with exit code $LASTEXITCODE."
    }

    Invoke-Checked $PythonBin @('benchmarks/flush_redis.py')

    $serverOut = Join-Path $ResultsDir 'orchestration-server.stdout.log'
    $serverErr = Join-Path $ResultsDir 'orchestration-server.stderr.log'
    $server = $null

    try {
        $server = Start-PythonServer \
            -Arguments @(
                '-m', 'uvicorn', 'benchmarks.orchestration_api_app:app',
                '--host', '127.0.0.1', '--port', '8030',
                '--workers', '2', '--timeout-keep-alive', '30'
            ) \
            -StdoutPath $serverOut \
            -StderrPath $serverErr

        Wait-HttpReady -Url 'http://127.0.0.1:8030/health/live'

        & $PythonBin benchmarks/orchestration_api_soak.py \
            --base-url http://127.0.0.1:8030 \
            --workers 2 \
            --widths '4,8,12,16' \
            --concurrency '10,20' \
            --trials 3 \
            --requests 120 \
            --output (Join-Path $ResultsDir 'orchestration-soak.json') 2>&1 |
            Tee-Object -FilePath (Join-Path $ResultsDir 'orchestration-soak.txt')
        if ($LASTEXITCODE -ne 0) {
            throw 'Orchestration soak benchmark failed.'
        }

        $metricsPath = Join-Path $ResultsDir 'orchestration-metrics.txt'
        $metrics = (Invoke-WebRequest -Uri 'http://127.0.0.1:8030/metrics' -UseBasicParsing).Content
        Set-Content -Path $metricsPath -Value $metrics -Encoding UTF8

        if ($metrics -notmatch 'maestro_llm_orchestration_requests_total') {
            throw 'Missing maestro_llm_orchestration_requests_total metric.'
        }
        if ($metrics -notmatch 'maestro_llm_orchestration_latency_seconds') {
            throw 'Missing maestro_llm_orchestration_latency_seconds metric.'
        }
    }
    finally {
        Stop-ProcessSafely $server
    }
}

Assert-Command 'docker'
Assert-Command $PythonBin

try {
    switch ($Mode) {
        'durable' { Run-DurableQualification }
        'load' { Run-LoadQualification }
        'soak' { Run-SoakQualification }
        'all' {
            Run-DurableQualification
            Run-LoadQualification
            Run-SoakQualification
        }
    }

    Write-Host "Qualification evidence written to: $ResultsDir"
}
finally {
    Stop-QualificationContainers
}
