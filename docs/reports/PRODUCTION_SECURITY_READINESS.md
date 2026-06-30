# Production Security Readiness

## Processual Maestro Kernel v2.0.0

## DOCS-PROD-01

---

## 1. Purpose

This document defines the production security readiness requirements for deploying **Processual Maestro Kernel v2.0.0**.

It focuses on the security checks that must be completed before any public, customer-facing, cloud, Google Cloud, Docker, or partner deployment.

This document does not replace runtime tests. It explains the required production configuration and the expected operational checks before deployment.

---

## 2. Current Security Posture

The project already includes production-safety logic in `processual_api/settings.py`.

The settings layer:

* Reads runtime configuration from environment variables.
* Detects whether the application is running in production through `ENVIRONMENT=production`.
* Forces `debug=False` in production.
* Rejects weak or missing secrets in production.
* Warns about weak or missing secrets in development.
* Rejects wildcard CORS origins in production.
* Keeps local defaults acceptable only for local development and pytest.

The current local pytest warnings are expected in development because local defaults are intentionally weak and must not be used in production.

---

## 3. Production Mode

Production deployment must explicitly set:

```text
ENVIRONMENT=production
```

When this value is set, weak local defaults become blocking startup errors instead of warnings.

Expected behavior:

```text
development/test mode:
weak or missing values => warnings

production mode:
weak or missing values => RuntimeError / startup rejection
```

This is correct and should be preserved.

---

## 4. Required Production Secrets

The following variables must be set to strong, unique, non-default values before production deployment:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
PROCESSUAL_CRYPTO_KEY_B64
```

Additional service-specific secrets may also be required depending on enabled integrations:

```text
LEMONSQUEEZY_API_KEY
LEMONSQUEEZY_STORE_ID
LEMONSQUEEZY_WEBHOOK_SECRET
DISCORD_WEBHOOK_URL
DISCORD_ADMIN_WEBHOOK_URL
SENTRY_DSN
OPENAI_API_KEY
OPENROUTER_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
DEEPSEEK_API_KEY
OPENCODE_API_KEY
GENERIC_OPENAI_API_KEY
```

Provider API keys are customer-owned. Processual Maestro must not ship real provider keys, and the program must not provide OpenAI, Gemini, Anthropic, DeepSeek, OpenRouter, OpenCode, Ollama, vLLM, LM Studio, or generic OpenAI-compatible credentials on behalf of customers.

---

## 5. Weak Values That Must Never Be Used in Production

The settings layer already treats common weak values as unsafe.

The following types of values must never appear in production:

```text
empty string
change_me
CHANGE_ME_IN_PRODUCTION
admin
password
processual
test
dev
changeme
default
secret
123456
```

Any value that is short, guessable, shared, reused, copied from documentation, or committed to Git must also be considered unsafe.

---

## 6. JWT_SECRET Requirements

`JWT_SECRET` is used to sign and verify authentication tokens.

Production requirement:

```text
JWT_SECRET must be a strong random secret.
JWT_SECRET must be unique per deployment.
JWT_SECRET must not be committed.
JWT_SECRET must not equal CHANGE_ME_IN_PRODUCTION.
JWT_SECRET must not be shared between unrelated environments.
```

Recommended generation on PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Minimum recommendation:

```text
At least 32 random bytes of entropy.
Prefer token_urlsafe(64) or stronger.
```

Operational warning:

Changing `JWT_SECRET` invalidates existing JWT sessions. Rotate it only during planned maintenance unless responding to a security incident.

---

## 7. API_KEYS Requirements

`API_KEYS` is the development/static fallback key list.

Production direction:

* Prefer dynamic `pmk_` API keys generated through the settings/API key system.
* Do not rely on simple static API keys for production customer access.
* If `API_KEYS` is kept for bootstrap or emergency access, use strong random values.
* Never use `dev-public-test-key` or any documentation sample in production.
* Do not store real API keys in Git.

Recommended generation:

```powershell
python -c "import secrets; print('pmk_bootstrap_' + secrets.token_urlsafe(48))"
```

---

## 8. DATABASE_URL Requirements

`DATABASE_URL` must point to a production PostgreSQL instance.

Required properties:

```text
unique strong database username
unique strong password
non-default database name
TLS/SSL enabled where supported
restricted network access
least-privilege database account
backup and restore policy defined
```

Example shape only:

```text
postgresql+asyncpg://pmk_user:<strong-password>@db-host:5432/processual_maestro
```

Do not commit the real URL.

---

## 9. REDIS_URL Requirements

`REDIS_URL` must point to a production Redis instance.

Required properties:

```text
strong Redis password
private network access
TLS where supported
no anonymous public access
rate-limit and cache behavior verified
```

Example shape only:

```text
redis://:<strong-password>@redis-host:6379/0
```

Do not commit the real URL.

---

## 10. POSTGRES_PASSWORD and REDIS_PASSWORD

`POSTGRES_PASSWORD` and `REDIS_PASSWORD` must match the credentials used by the database and Redis services.

They must be:

```text
strong
unique
not reused elsewhere
not documentation values
not default Docker values
not committed to Git
```

Recommended generation:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 11. GRAFANA_ADMIN_PASSWORD

`GRAFANA_ADMIN_PASSWORD` must be changed before exposing Grafana.

Production requirements:

```text
do not use admin/admin
do not use password
do not expose Grafana publicly without authentication
restrict dashboard access
rotate the password if shared during setup
```

Recommended generation:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 12. PROCESSUAL_CRYPTO_KEY_B64

`PROCESSUAL_CRYPTO_KEY_B64` is required for encryption of stored sensitive provider/API-key material.

Production requirements:

```text
must be generated once per deployment
must be stored securely
must not be committed
must not be lost without backup strategy
must be rotated only with a migration/decryption plan
```

Recommended generation for a 32-byte AES key:

```powershell
python -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Operational warning:

If encrypted settings or provider keys already exist, losing or changing this key may make existing encrypted values undecryptable.

---

## 13. CORS Requirements

Production must set explicit CORS origins.

Allowed:

```text
CORS_ORIGINS=https://console.example.com,https://admin.example.com
```

Forbidden in production:

```text
CORS_ORIGINS=*
```

The settings layer is expected to reject wildcard CORS in production.

---

## 14. Debug, Docs, and Redoc

Production deployment must ensure:

```text
API_DEBUG=false
debug=False
no public stack traces
OpenAPI docs/redoc exposure reviewed
```

If documentation endpoints are enabled for a private admin deployment, access must be controlled at the network or gateway level.

For public deployments, disable or restrict interactive docs unless there is a deliberate reason to expose them.

---

## 15. Provider Key Ownership Model

Processual Maestro does not provide external AI-provider access on behalf of customers.

The customer or deploying organization is responsible for:

```text
OpenAI API key
OpenRouter API key
Gemini API key
Anthropic API key
DeepSeek API key
OpenCode endpoint/key
Ollama local endpoint
LM Studio endpoint
vLLM endpoint
Generic OpenAI-compatible endpoint
```

Processual Maestro provides:

```text
configuration layer
readiness testing
governance
quota management
adapter routing
audit/reporting support
```

It does not absorb provider usage cost and does not guarantee third-party provider availability.

---

## 16. Payment and Billing Secrets

If Lemon Squeezy billing is enabled, configure:

```text
LEMONSQUEEZY_API_KEY
LEMONSQUEEZY_STORE_ID
LEMONSQUEEZY_WEBHOOK_SECRET
LS_VARIANT_STARTER
LS_VARIANT_STARTER_YEARLY
LS_VARIANT_PROFESSIONAL
LS_VARIANT_PROFESSIONAL_YEARLY
LS_VARIANT_ENTERPRISE
LS_VARIANT_ENTERPRISE_YEARLY
LEMONSQUEEZY_CHECKOUT_SUCCESS_URL
LEMONSQUEEZY_CHECKOUT_CANCEL_URL
```

Production requirements:

```text
webhook secret must be set
checkout success/cancel URLs must use production domains
variant IDs must match the actual payment provider configuration
test-mode billing values must not be mixed with production values
```

---

## 17. Observability and Discord Webhooks

Optional integrations:

```text
SENTRY_DSN
SENTRY_ENVIRONMENT
SENTRY_TRACES_SAMPLE_RATE
DISCORD_WEBHOOK_URL
DISCORD_ADMIN_WEBHOOK_URL
DISCORD_RATE_LIMIT_SECONDS
```

Production requirements:

```text
do not post secrets to Discord
do not send customer private content unnecessarily
use separate webhooks for development and production
limit alert noise
confirm incident escalation ownership
```

---

## 18. Git and Secret Hygiene

Before deployment or release, verify:

```powershell
git status --short
git check-ignore .env
git check-ignore .env.production
git check-ignore .env.local
```

Expected:

```text
.env files are ignored
.env.example is tracked
.env.production.example is tracked if it contains placeholders only
real .env files are not tracked
```

Never commit:

```text
real API keys
real JWT_SECRET
real DATABASE_URL
real REDIS_URL
real provider credentials
real payment provider secrets
real webhook secrets
real customer data
```

---

## 19. Docker and Deployment Checklist

Before Docker/Google Cloud deployment:

```text
Dockerfile reviewed
docker-compose.yml reviewed
.env loaded from secure deployment secret store
health endpoints verified
readiness endpoints verified
database reachable
Redis reachable
static console served correctly
logs written to stdout or configured logging backend
persistent data paths reviewed
backup/restore path defined
```

For Google Cloud or similar managed platforms:

```text
use Secret Manager or equivalent
do not bake secrets into images
restrict service account permissions
use HTTPS
set explicit CORS origins
restrict database and Redis network access
enable logs and alerts
define rollback plan
```

---

## 20. Required Manual Validation Before Production

Run local regression first:

```powershell
python -m pytest -q
python -m compileall .\tests .\processual_api .\processual_kernel .\cgtlib
git diff --check
```

Then verify production-style configuration in a safe staging environment:

```text
ENVIRONMENT=production
strong JWT_SECRET
strong API_KEYS or dynamic API key bootstrap
strong DATABASE_URL
strong REDIS_URL
strong POSTGRES_PASSWORD
strong REDIS_PASSWORD
strong GRAFANA_ADMIN_PASSWORD
explicit CORS_ORIGINS
PROCESSUAL_CRYPTO_KEY_B64 set
```

Expected production behavior:

```text
startup succeeds only when required secrets are strong
startup fails if weak secrets are used
startup fails if CORS_ORIGINS contains *
health endpoints respond
readiness endpoints respond
console loads
admin authentication works
dynamic API keys work
provider readiness can be tested with customer-owned keys
```

---

## 21. Current Local Warning Baseline

The current local pytest baseline may still show warnings for weak development defaults:

```text
JWT_SECRET
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

This is acceptable for local tests only.

These warnings are not acceptable for production. In production mode, weak values must become startup blockers.

---

## 22. Release Gate

Do not deploy publicly until all of the following are true:

```text
pytest baseline passes
compileall passes
git diff --check is clean
git status is clean
.env is not tracked
production secrets are strong
CORS origins are explicit
database and Redis are production-grade
provider keys are customer-owned and not committed
PROCESSUAL_CRYPTO_KEY_B64 is set and backed up securely
billing secrets are set if billing is enabled
support/refund/customer responsibility docs are ready
deployment rollback plan exists
```

---

## PROD-ENV-01 — Production Environment Template Review

The production environment template is guarded by:

`tests/test_production_env_template_regression.py`

The template must continue to include:

- Explicit production mode through `ENVIRONMENT=production`.
- Explicit application mode through `APP_ENV=production`.
- Production debug shutdown through `API_DEBUG=false`.
- Required core security values: `JWT_SECRET`, `API_KEYS`, `PROCESSUAL_CRYPTO_KEY_B64`, and `CORS_ORIGINS`.
- Required PostgreSQL values: `DATABASE_URL`, `POSTGRES_PASSWORD`, `POSTGRES_USER`, and `POSTGRES_DB`.
- Required Redis values: `REDIS_URL` and `REDIS_PASSWORD`.
- Required Grafana value: `GRAFANA_ADMIN_PASSWORD`.
- Sentry observability keys.
- Discord webhook keys.
- Lemon Squeezy billing keys.
- OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, OpenCode, and generic OpenAI-compatible provider keys and endpoints, including `GENERIC_OPENAI_API_KEY`, `GENERIC_OPENAI_API_URL`, and `GENERIC_OPENAI_DEFAULT_MODEL`.
- CGT Governor runtime keys.
- API key quota keys.

The template must also preserve the customer-owned provider key model. Processual Maestro must not ship real provider keys or absorb third-party provider usage costs on behalf of customers.

The environment template is not a real `.env` file. It must contain placeholders only and must never include real credentials.




## 23. Conclusion

Processual Maestro already has important production-safety hooks in its settings layer. The next step is disciplined operational configuration.

Production readiness is not achieved by passing pytest alone. It requires strong secrets, explicit origins, safe provider-key ownership, secure deployment storage, controlled observability, billing-secret verification, and a documented support/rollback process.

This document should be reviewed before any public deployment, Google Cloud deployment, partner pilot, or customer-facing release.


---

## PROD-RELEASE-01 — Final Release Gate Checkpoint

This checkpoint records the current production release gate after completing the production security, smoke, and Docker hardening sequence.

Verified local release gate:

```text
pytest: 168 passed, 6 warnings
compileall: PASS
git diff --check: clean
git status --short: clean


PROD-SEC-02 — Production startup hardening regression
PROD-SEC-03 — Auth fallback production boundary
PROD-SEC-04 — Secret encryption readiness regression
PROD-SMOKE-01 — Minimal FastAPI app smoke coverage
PROD-DOCKER-01 — Docker compose production regression
PROD-RELEASE-01 — Final release checklist regression


README.md
DEPLOYMENT_EXTERNAL.md
SECURITY.md
.env.production.example
Dockerfile
docker-compose.yml
docs/reports/PRODUCTION_SECURITY_READINESS.md
docs/reports/API_KEYS_ADAPTERS_REGRESSION_REPORT.md
tests/test_production_startup_hardening_regression.py
tests/test_auth_fallback_production_boundary.py
tests/test_secret_encryption_readiness_regression.py
tests/test_fastapi_integration_smoke.py
tests/test_docker_compose_production_regression.py

tests/test_final_release_checklist_regression.py
