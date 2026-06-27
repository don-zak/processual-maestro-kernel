# API Documentation

## Endpoint Reference

Routes are defined without a global prefix. Each group uses its own prefix as listed below.

| Group | Prefix | Description |
|-------|--------|-------------|
| Health | `/health` | Liveness (`/live`) and readiness (`/ready`) probes |
| Auth | `/auth` | JWT token creation, API key management |
| CGT | `/cgt` | Fate vector evaluation and existence ranking |
| Workflows | `/workflows` | Workflow CRUD and checkpointing |
| Governance | `/governance` | CGT governance reports |
| Settings | `/settings` | User preferences, LLM provider config, notifications |
| Reports | `/reports` | LLM-generated narrative reports, fate analysis |
| Telemetry | `/telemetry` | Anonymous usage data ingestion |
| Discord | `/discord` | Discord webhook test and configuration |
| CGT Governor | `/adapters`, `/govern`, `/auto-repair`, `/simulate` | Adapter comparison, auto-repair, gateway, simulations |
| Billing | `/billing` | Lemon Squeezy checkout, portal, webhooks |
| Applications | `/applications` | B2B apply/approve flow |

## OpenAPI Spec

When running in non-production mode (`is_production=false`):

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

## Authentication

- **JWT Bearer Token**: Pass in `Authorization: Bearer <token>` header
- **API Key**: Pass in `X-API-Key` header
- All authenticated endpoints return `401` if neither is provided

## Rate Limiting

- Default: 100 requests/minute (unauthenticated)
- Authenticated: 500 requests/minute
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`
