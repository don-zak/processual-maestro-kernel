# Security Documentation

## Overview

The Processual Maestro Kernel follows security best practices for API development. This document outlines the security measures implemented across the platform.

## Authentication

- **JWT Tokens**: Signed with HS256, configurable expiry (`JWT_EXPIRE_MINUTES`)
- **API Keys**: Random 256-bit keys (prefix `pmk_`), stored as bcrypt hashes
- **Rate Limiting**: Per-IP throttling with Redis backend (configurable limits)

## Encryption

- **Settings Encryption**: AES-256-GCM for LLM API keys stored on disk
- **CGT Governor Audit Logs**: Encrypted entries with integrity verification

## Error Handling

- All unhandled exceptions return `500 Internal server error` (no stack traces)
- Exception types are **not** disclosed to clients
- External API error bodies are **not** forwarded to clients
- Truncated error messages (200 chars max) in non-critical paths

## Middleware Pipeline

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | `RequestIDMiddleware` | Assigns unique `X-Request-ID` to every request |
| 2 | `RateLimitMiddleware` | Per-client rate limiting (when Redis available) |
| 3 | `SecurityHeadersMiddleware` | Adds security response headers |
| 4 | `MetricsMiddleware` | Prometheus request metrics |
| 5 | `AuditMiddleware` | Request/response audit logging |
| 6 | `SubscriptionMiddleware` | Billing subscription enforcement |
| 7 | `error_handler_middleware` | Global exception → sanitised 500 response |

## Production Checklist

1. Set `JWT_SECRET` to a strong random value (not `CHANGE_ME_IN_PRODUCTION`)
2. Set `ENCRYPTION_KEY` to a 32-byte hex-encoded AES-256 key
3. Disable `/docs` and `/redoc` in production (`is_production=true`)
4. Ensure `RATE_LIMIT_ENABLED=true`
5. Set `AUDIT_ENABLED=true`
6. Use HTTPS in production (reverse proxy — nginx, Caddy, etc.)
