#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
PYTHON_BIN="${PYTHON_BIN:-python}"
RESULTS_DIR="${RESULTS_DIR:-local-qualification-results}"
REDIS_PORT="${PMK_LOCAL_REDIS_PORT:-16379}"
POSTGRES_PORT="${PMK_LOCAL_POSTGRES_PORT:-15432}"
REDIS_CONTAINER="pmk-local-qualification-redis"
POSTGRES_CONTAINER="pmk-local-qualification-postgres"
REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/15"
DATABASE_URL="postgresql+asyncpg://maestro:local-benchmark-password@127.0.0.1:${POSTGRES_PORT}/maestro"

mkdir -p "$RESULTS_DIR"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

cleanup() {
  docker rm -f "$REDIS_CONTAINER" "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_redis() {
  docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$REDIS_CONTAINER" -p "${REDIS_PORT}:6379" redis:7 >/dev/null
  for _ in $(seq 1 30); do
    if docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q PONG; then
      return 0
    fi
    sleep 1
  done
  echo "Redis did not become ready" >&2
  exit 1
}

start_postgres() {
  docker rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$POSTGRES_CONTAINER" \
    -e POSTGRES_USER=maestro \
    -e POSTGRES_PASSWORD=local-benchmark-password \
    -e POSTGRES_DB=maestro \
    -p "${POSTGRES_PORT}:5432" postgres:17 >/dev/null
  for _ in $(seq 1 45); do
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U maestro -d maestro >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Postgres did not become ready" >&2
  exit 1
}

run_durable() {
  echo "== Durable real-Redis qualification =="
  start_redis
  export TEST_REDIS_URL="$REDIS_URL"
  export PYTHONPATH=.

  "$PYTHON_BIN" -m pytest -q \
    tests/test_adaptive_concurrency.py \
    tests/test_adaptive_pool_gate.py \
    tests/test_execution_domain_capacity.py \
    tests/test_durable_redis_qualification.py \
    tests/test_durable_resilience_qualification.py \
    | tee "$RESULTS_DIR/durable-tests.txt"

  "$PYTHON_BIN" benchmarks/durable_worker_scale.py \
    --redis-url "$REDIS_URL" \
    --workers 1,2,4,8 \
    --jobs 384 \
    --handler-delay-ms 20 \
    --repetitions 5 \
    --redis-telemetry \
    | tee "$RESULTS_DIR/durable-1-2-4-8.json"

  if [[ "${PMK_INCLUDE_16_WORKERS:-0}" == "1" ]]; then
    "$PYTHON_BIN" benchmarks/durable_worker_scale.py \
      --redis-url "$REDIS_URL" \
      --workers 16 \
      --jobs 384 \
      --handler-delay-ms 20 \
      --repetitions 5 \
      --redis-telemetry \
      | tee "$RESULTS_DIR/durable-16.json"
  fi
}

run_load() {
  echo "== Local HTTP/load qualification =="
  start_redis
  start_postgres

  export ENVIRONMENT=development
  export DATABASE_URL="$DATABASE_URL"
  export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
  export JWT_SECRET=local-benchmark-only-jwt-secret
  export API_KEYS=local-benchmark-only-api-key
  export POSTGRES_PASSWORD=local-benchmark-password
  export REDIS_PASSWORD=local-benchmark-password
  export GRAFANA_ADMIN_PASSWORD=local-benchmark-password
  export RATE_LIMIT_ENABLED=false

  "$PYTHON_BIN" -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000 \
    > "$RESULTS_DIR/load-server.log" 2>&1 &
  local server_pid=$!
  trap 'kill "$server_pid" >/dev/null 2>&1 || true; cleanup' RETURN

  for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8000/health/live >/dev/null; then
      break
    fi
    sleep 1
  done

  "$PYTHON_BIN" benchmarks/load_probe.py \
    --name http-live --path /health/live \
    --concurrency 1,5,10,20,40,80,120 --requests 300 \
    --output "$RESULTS_DIR/http-live.json" \
    | tee "$RESULTS_DIR/http-live.txt"

  "$PYTHON_BIN" benchmarks/load_probe.py \
    --name dependency-ready --path /health/ready \
    --concurrency 1,5,10,20,40,80,120 --requests 200 \
    --output "$RESULTS_DIR/dependency-ready.json" \
    | tee "$RESULTS_DIR/dependency-ready.txt"

  "$PYTHON_BIN" benchmarks/workload_probe.py \
    --concurrency 1,5,10,20,40 \
    --light-requests 200 --normal-requests 160 --heavy-requests 80 \
    --output "$RESULTS_DIR/workloads.json" \
    | tee "$RESULTS_DIR/workloads.txt"

  "$PYTHON_BIN" benchmarks/performance_guard.py "$RESULTS_DIR/workloads.json"
  kill "$server_pid" >/dev/null 2>&1 || true
  trap cleanup RETURN
}

run_soak() {
  echo "== Multi-process orchestration soak =="
  start_redis

  export PYTHONPATH=.
  export ENVIRONMENT=development
  export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
  export JWT_SECRET=local-benchmark-only-jwt-secret
  export API_KEYS=local-benchmark-only-api-key
  export RATE_LIMIT_ENABLED=false
  export CAPACITY_GUARD_ENABLED=false
  export EXECUTION_FANOUT_ENABLED=true
  export EXECUTION_FANOUT_GLOBAL_LIMIT=16
  export EXECUTION_FANOUT_PROVIDER_LIMIT=8
  export EXECUTION_FANOUT_WAIT_MS=250

  "$PYTHON_BIN" -m pytest -q tests/test_orchestration_api_soak.py \
    | tee "$RESULTS_DIR/orchestration-soak-tests.txt"

  "$PYTHON_BIN" benchmarks/flush_redis.py
  "$PYTHON_BIN" -m uvicorn benchmarks.orchestration_api_app:app \
    --host 127.0.0.1 --port 8030 --workers 2 --timeout-keep-alive 30 \
    > "$RESULTS_DIR/orchestration-server.log" 2>&1 &
  local server_pid=$!
  trap 'kill "$server_pid" >/dev/null 2>&1 || true; cleanup' RETURN

  for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8030/health/live >/dev/null; then
      break
    fi
    sleep 1
  done

  "$PYTHON_BIN" benchmarks/orchestration_api_soak.py \
    --base-url http://127.0.0.1:8030 \
    --workers 2 --widths 4,8,12,16 --concurrency 10,20 \
    --trials 3 --requests 120 \
    --output "$RESULTS_DIR/orchestration-soak.json" \
    | tee "$RESULTS_DIR/orchestration-soak.txt"

  curl --fail --silent http://127.0.0.1:8030/metrics > "$RESULTS_DIR/orchestration-metrics.txt"
  grep -q 'maestro_llm_orchestration_requests_total' "$RESULTS_DIR/orchestration-metrics.txt"
  grep -q 'maestro_llm_orchestration_latency_seconds' "$RESULTS_DIR/orchestration-metrics.txt"

  kill "$server_pid" >/dev/null 2>&1 || true
  trap cleanup RETURN
}

require_cmd docker
require_cmd curl
require_cmd "$PYTHON_BIN"

case "$MODE" in
  durable) run_durable ;;
  load) run_load ;;
  soak) run_soak ;;
  all)
    run_durable
    run_load
    run_soak
    ;;
  *)
    echo "Usage: $0 [durable|load|soak|all]" >&2
    exit 2
    ;;
esac

echo "Qualification evidence written to: $RESULTS_DIR"
