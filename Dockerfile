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

ENV REQUIRE_PRIVATE_CGT_FOR_READINESS=true

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
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

CMD ["sh", "-c", "uvicorn processual_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Prepare the complete public cgtlib surface in an intermediate stage. The
# proprietary tree may exist in this build-only stage/cache, but no layer from
# this stage is part of the final public image.
FROM base AS public-cgtlib-prep
COPY cgtlib /tmp/cgtlib
RUN rm -rf /tmp/cgtlib/private/ && rm -f /tmp/cgtlib/pyproject.toml
RUN test ! -e /tmp/cgtlib/private

# ---------- public target (no proprietary math) --------------------------------
FROM base AS public

ENV REQUIRE_PRIVATE_CGT_FOR_READINESS=false

COPY pyproject.toml README.md ./
COPY processual_kernel ./processual_kernel
COPY processual_api ./processual_api
COPY --from=public-cgtlib-prep /tmp/cgtlib ./cgtlib

# Defense in depth: fail before installation if the private CGT tree appears in
# the final public stage for any reason.
RUN test ! -e cgtlib/private

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[api,security,database,cache,observability,reports,llm]

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

CMD ["sh", "-c", "uvicorn processual_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
