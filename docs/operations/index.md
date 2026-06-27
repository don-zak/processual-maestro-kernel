# Operations Guide

## Deployment

### Prerequisites

- Python 3.14+
- Redis 7+ (optional — rate limiting only)
- PostgreSQL 16+ (optional — for multi-tenant deployments)

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | Yes | — | Secret key for JWT signing |
| `ENCRYPTION_KEY` | Yes | — | AES-256-GCM key for settings encryption |
| `REDIS_URL` | No | — | Redis connection string |
| `DATABASE_URL` | No | — | PostgreSQL connection string |
| `RATE_LIMIT_ENABLED` | No | `true` | Enable rate limiting middleware |
| `RATE_LIMIT_DEFAULT` | No | `100/minute` | Unauthenticated rate limit |
| `RATE_LIMIT_AUTHENTICATED` | No | `500/minute` | Authenticated rate limit |
| `DISCORD_RATE_LIMIT_SECONDS` | No | `2` | Cooldown between Discord webhook sends |

### Docker

```bash
docker-compose up -d
```

### Manual

```bash
pip install -e .
uvicorn processual_api.main:app --host 0.0.0.0 --port 8000
```

## Monitoring

- **Prometheus metrics**: Available at `/metrics` via `MetricsMiddleware`
- **Health probes**: `/health/live` (simple alive check), `/health/ready` (dependency check)
- **Audit logging**: All requests logged via `AuditMiddleware` when `AUDIT_ENABLED=true`

## Maintenance

- Data files stored in `processual_api/data/` as JSON
- Backup strategy: periodic snapshot of `data/` directory
- Log rotation: configure via external log shipper
