#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
hex() { od -An -N "$1" -tx1 /dev/urandom | tr -d ' \n'; }
b64() { od -An -N "$1" -tx1 /dev/urandom | tr -d ' \n' | xxd -r -p | base64 | tr -d '\n'; }

need docker
need od
need xxd
need curl

docker version >/dev/null
docker compose version >/dev/null

if [ ! -f .env.evaluation ]; then
  JWT_SECRET=$(hex 48)
  API_KEYS="pmk_eval_$(hex 32)"
  PROCESSUAL_CRYPTO_KEY_B64=$(b64 32)
  ADMIN_PASSWORD=$(hex 24)
  POSTGRES_PASSWORD=$(hex 24)
  REDIS_PASSWORD=$(hex 24)
  GRAFANA_ADMIN_PASSWORD=$(hex 24)
  AUTH_TOKEN_PEPPER=$(hex 32)
  AUTH_RATE_LIMIT_PEPPER=$(hex 32)
  AUTH_DELIVERY_KEY=$(b64 32)
  AUTH_MFA_KEY=$(b64 32)
  PAYMENT_KEY=$(b64 32)
  cat > .env.evaluation <<EOF
ENVIRONMENT=development
APP_ENV=evaluation
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=info
API_DEBUG=false
JWT_SECRET=$JWT_SECRET
API_KEYS=$API_KEYS
PROCESSUAL_CRYPTO_KEY_B64=$PROCESSUAL_CRYPTO_KEY_B64
MAESTRO_ADMIN_EMAIL=evaluator@example.local
MAESTRO_ADMIN_PASSWORD=$ADMIN_PASSWORD
GRAFANA_ADMIN_PASSWORD=$GRAFANA_ADMIN_PASSWORD
AUTH_TOKEN_PEPPER=$AUTH_TOKEN_PEPPER
AUTH_RATE_LIMIT_PEPPER=$AUTH_RATE_LIMIT_PEPPER
AUTH_DELIVERY_KEY_RING_JSON={"v1":"$AUTH_DELIVERY_KEY"}
AUTH_DELIVERY_CURRENT_KEY_VERSION=v1
AUTH_MFA_KEY_RING_JSON={"v1":"$AUTH_MFA_KEY"}
AUTH_MFA_CURRENT_KEY_VERSION=v1
ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON={"payment-v1":"$PAYMENT_KEY"}
ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION=payment-v1
POSTGRES_USER=processual
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=processual_eval
REDIS_PASSWORD=$REDIS_PASSWORD
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
EOF
fi

if ! docker image inspect processual-maestro-evaluation:v1 >/dev/null 2>&1; then
  if [ -d images ]; then
    echo "Loading bundled Docker images..."
    found=0
    for archive in images/*.tar; do
      [ -e "$archive" ] || continue
      found=1
      docker load -i "$archive"
    done
    [ "$found" -eq 1 ] || { echo "No Docker image archives found in images/." >&2; exit 1; }
  elif [ -f ../Dockerfile ]; then
    echo "Building public evaluation image from source..."
    docker build --target public -t processual-maestro-evaluation:v1 ..
  else
    echo "Evaluation image unavailable. Use the official portable bundle with images/." >&2
    exit 1
  fi
fi

docker compose --env-file .env.evaluation -f docker-compose.evaluation.yml up -d

echo "Waiting for API health..."
i=0
while [ "$i" -lt 90 ]; do
  if curl -fsS http://localhost:8000/health/live >/dev/null 2>&1; then
    echo "READY: http://localhost:8000"
    echo "Docs:  http://localhost:8000/docs"
    exit 0
  fi
  i=$((i+1))
  sleep 2
done

docker compose --env-file .env.evaluation -f docker-compose.evaluation.yml ps
docker logs maestro-eval-api --tail 120 || true
echo "Evaluation API did not become healthy." >&2
exit 1
