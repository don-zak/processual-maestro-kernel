# Deployment Guide

## Quick Start (Local)

```bash
pip install -e .[all]
cp .env.example .env
uvicorn processual_api.main:app --reload
```

## Docker

```bash
docker compose up --build
```

Services: API (8000), PostgreSQL (5432), Redis (6379), Prometheus (9090), Grafana (3000).

## Kubernetes

```bash
kubectl apply -k ops/k8s/overlays/dev/
```

## Cloud Providers

| Provider | Service | Notes |
|---|---|---|
| Google Cloud | Cloud Run + Secret Manager + Cloud SQL | serverless, auto-scale |
| AWS | ECS/Fargate + Secrets Manager + RDS | container-native |
| Azure | Container Apps + Key Vault + PostgreSQL | managed containers |

### Secrets Required

| Variable | Source |
|---|---|
| `JWT_SECRET` | Secret Manager |
| `API_KEYS` | Secret Manager |
| `DATABASE_URL` | Cloud SQL / RDS / PostgreSQL |
| `REDIS_URL` | Memorystore / ElastiCache / Redis |
| `SENTRY_DSN` | Sentry project |
| `DISCORD_WEBHOOK_URL` | Discord channel |
| `PROCESSUAL_CRYPTO_KEY_B64` | Key generation |

## Monorepo Split

### Architecture
- **Private repo**: contains the full monorepo including `cgtlib/private/` (proprietary math). Built as `cgtlib` (standalone private package) + `processual-maestro-kernel` monolith.
- **Public repo**: contains everything **except** `cgtlib/private/`. Published as `processual-maestro-kernel`. The public `cgtlib` module will raise a clear error if `private` is missing.

### How to split

**Using the split script (PowerShell):**
```powershell
.\tools\split-public-repo.ps1 -TargetDir ..\processual-maestro-public
cd ..\processual-maestro-public
git init
git add .
git commit -m "initial public release"
git remote add origin https://github.com/YOUR_ORG/processual-maestro-kernel.git
git push -u origin main
```

**Manual split:**
```bash
# Clone private monorepo
git clone git@github.com:YOUR_ORG/processual-maestro-private.git
cd processual-maestro-private

# Create public branch
git checkout -b public-release

# Remove private modules
git rm -r cgtlib/private/
git rm cgtlib/pyproject.toml
git rm -r tools/
git mv .github/workflows/ci-public.yml .github/workflows/ci.yml
git rm .github/workflows/ci.yml  # the private one

# Commit and push to public repo
git commit -m "strip private modules for public release"
git push git@github.com:YOUR_ORG/processual-maestro-kernel.git public-release:main
```

### CI/CD distinctions

| Workflow | Private Repo | Public Repo |
|---|---|---|
| `ci.yml` | Full test suite + private module verification | — |
| `ci-public.yml` | — | Tests without private modules |
| `release.yml` | Builds both packages | Builds public package only |
| `security.yml` | Full scan | Scan without private dirs |
| `docker.yml` | Builds both `private` and `public` Docker targets | Builds `public` target |

### Docker multi-target build

```bash
# Build private image (default, includes proprietary math)
docker build --target private -t processual-maestro:latest .

# Build public image (excludes cgtlib/private/)
docker build --target public -t processual-maestro-public:latest .
```
