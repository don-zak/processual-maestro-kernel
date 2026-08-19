FROM python:3.14-slim AS public

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --ingroup app --no-create-home app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Public repository artifact only. This source tree must not contain private
# mathematical implementations or private provider modules.
COPY pyproject.toml README.md ./
COPY cgtlib ./cgtlib
COPY processual_kernel ./processual_kernel
COPY processual_api ./processual_api

# Legacy raw-math browser sources are retained in Git for review/history only.
# They are deliberately absent from the runtime image; HTTP compatibility
# tombstones are enforced by SecurityHeadersMiddleware at their former paths.
RUN rm -f \
    processual_api/static/js/adapters/governor.js \
    processual_api/static/js/adapters/cgt.js \
    processual_api/static/js/pages/governor.js \
    processual_api/static/js/pages/cgt.js \
    && test ! -e processual_api/static/js/adapters/governor.js \
    && test ! -e processual_api/static/js/adapters/cgt.js \
    && test ! -e processual_api/static/js/pages/governor.js \
    && test ! -e processual_api/static/js/pages/cgt.js

RUN test ! -d cgtlib/private \
    && test ! -d processual_api/private_integrations \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[api,security,database,cache,observability,reports,llm]

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

CMD ["sh", "-c", "uvicorn processual_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]