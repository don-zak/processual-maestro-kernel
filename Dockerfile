# =============================================================================
# Multi-stage Dockerfile — two build targets:
#   docker build --target private  .   (default, includes cgtlib/private/)
#   docker build --target public   .   (excludes cgtlib/private/)
# =============================================================================

FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --ingroup app --no-create-home app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------- private target (full monorepo, includes proprietary math) ----------
FROM base AS private

COPY pyproject.toml README.md ./
COPY cgtlib ./cgtlib
COPY processual_kernel ./processual_kernel
COPY processual_api ./processual_api

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[api,security,database,cache,observability,reports,llm]

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "processual_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- public target (no proprietary math) --------------------------------
FROM base AS public

COPY pyproject.toml README.md ./
COPY processual_kernel ./processual_kernel
COPY processual_api ./processual_api
# Copy cgtlib/ but exclude cgtlib/private/ — stubs provide graceful fallback
COPY cgtlib/__init__.py cgtlib/_fallback.py cgtlib/metadata.py cgtlib/types.py cgtlib/validation.py ./cgtlib/
COPY cgtlib/serialization.py cgtlib/api.py ./cgtlib/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[api,security,database,cache,observability,reports,llm]

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "processual_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
