from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Body, Depends, FastAPI
from fastapi import HTTPException as PMK13AHTTPException
from fastapi import Request as PMK13ARequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError

from processual_api.integrations.external_connectivity_cases import (
    SupervisorReadinessDecision,
    find_prohibited_customer_fields,
)
from processual_api.schemas.external_connectivity import (
    CustomerReferencePackageSubmissionRequest,
    ExternalConnectivityCaseCreateRequest,
    ExternalConnectivityCaseResponse,
    ExternalConnectivityKeyMutationRequest,
    ExternalConnectivityKeyMutationResponse,
    ExternalConnectivityQualificationKeyIssueRequest,
    ExternalConnectivityQualificationKeyIssueResponse,
    ExternalConnectivityQualificationRedeemRequest,
    ExternalConnectivityReadinessReviewRequest,
    ExternalConnectivityReviewResultResponse,
    ExternalConnectivitySandboxApiKeyIssueRequest,
    ExternalConnectivitySandboxApiKeyIssueResponse,
    ExternalConnectivitySupervisorDecisionRequest,
    ExternalConnectivitySupervisorDecisionResultResponse,
    external_connectivity_assessment_response_from_contract,
    external_connectivity_case_response_from_contract,
    supervisor_readiness_attestation_response_from_contract,
)
from processual_api.services.external_connectivity_intake import (
    ExternalConnectivityIntakeError,
    create_external_connectivity_case,
    get_external_connectivity_case,
    list_external_connectivity_cases,
    record_external_connectivity_supervisor_decision,
    review_external_connectivity_reference_package,
    submit_external_connectivity_reference_package,
)
from processual_api.services.external_connectivity_qualification import (
    ExternalConnectivityQualificationError,
    issue_external_connectivity_qualification_key,
    issue_external_connectivity_sandbox_api_key,
    redeem_external_connectivity_qualification_key,
    revoke_external_connectivity_qualification_key,
    revoke_external_connectivity_sandbox_api_key,
    suspend_external_connectivity_sandbox_api_key,
)
from processual_api.services.integration_claim_keys import (
    GUARDRAILS as PMK13A_CLAIM_GUARDRAILS,
)
from processual_api.services.integration_claim_keys import (
    get_client_integration_onboarding_status as pmk13a_get_client_integration_onboarding_status,
)
from processual_api.services.integration_claim_keys import (
    issue_integration_claim_key as pmk13a_issue_integration_claim_key,
)
from processual_api.services.integration_claim_keys import (
    list_integration_claim_keys as pmk13a_list_integration_claim_keys,
)
from processual_api.services.integration_claim_keys import (
    redeem_integration_claim_key as pmk13a_redeem_integration_claim_key,
)
from processual_api.services.integration_claim_keys import (
    revoke_integration_claim_key as pmk13a_revoke_integration_claim_key,
)

from .admin_marketplace.router import router as admin_marketplace_router
from .auth.account_recovery_router import (
    router as account_recovery_router,
)
from .auth.delivery_operations_router import (
    router as delivery_operations_router,
)
from .auth.mfa_router import router as mfa_router
from .auth.recovery_email_router import router as recovery_email_router
from .auth.registration_router import router as registration_router
from .auth.router import router as auth_router
from .auth.security import require_scope
from .auth.session_router import router as session_router
from .billing.router import router as billing_router
from .cache.redis import close_redis, init_redis
from .cgt_governor.adapters.registry import adapter_registry
from .db.session import close_db, init_db
from .middleware.audit import AuditMiddleware
from .middleware.error_handler import error_handler_middleware
from .middleware.metrics import MetricsMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.request_id import RequestIDMiddleware
from .middleware.security_headers import SecurityHeadersMiddleware
from .middleware.subscription import SubscriptionMiddleware
from .middleware.usage_log import UsageLogMiddleware
from .routers import applications, cgt, cgt_governor, discord, governance, health, reports, telemetry, workflows
from .routers import settings as settings_router
from .routers.evaluation_runtime import router as evaluation_runtime_router
from .routers.institution_qualification_18 import (
    router as institution_qualification_18_router,
)
from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    adapter_registry.discover()
    yield
    await close_redis()
    await close_db()


app = FastAPI(
    title=settings.title,
    description=settings.description,
    version=settings.version,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(UsageLogMiddleware)
app.add_middleware(SubscriptionMiddleware)
app.middleware("http")(error_handler_middleware)

app.include_router(health.router)
app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(recovery_email_router)
app.include_router(account_recovery_router)
app.include_router(delivery_operations_router)
app.include_router(session_router)
app.include_router(mfa_router)
app.include_router(cgt.router)
app.include_router(workflows.router)
app.include_router(governance.router)
app.include_router(telemetry.router)
app.include_router(reports.router)
app.include_router(discord.router)
app.include_router(cgt_governor.router)
app.include_router(evaluation_runtime_router)
app.include_router(settings_router.router)
app.include_router(applications.router)
app.include_router(billing_router)
app.include_router(admin_marketplace_router)

# Register Stage 18 qualification routes only after the
# complete router module has been initialized.
app.include_router(institution_qualification_18_router)

# Static smoke marker: from fastapi.responses import HTMLResponse
# Serve the Maestro Console frontend (single-page app)
_static_dir = Path(__file__).resolve().parent / "static"


@app.get("/pricing", include_in_schema=False)
@app.get("/pricing.html", include_in_schema=False)
async def pricing_page() -> FileResponse:
    """Serve the public-safe pricing/subscriptions page."""
    return FileResponse(_static_dir / "pricing.html")


if _static_dir.exists():
    app.mount("/console", StaticFiles(directory=str(_static_dir), html=True), name="console")

_register_page_path = _static_dir / "register.html"
_verify_email_page_path = _static_dir / "verify-email.html"
_plans_page_path = _static_dir / "plans.html"
_offer_page_path = _static_dir / "offer.html"


@app.get("/plans", response_class=HTMLResponse, include_in_schema=False)
async def plans_page() -> HTMLResponse:
    if not _plans_page_path.exists():
        return HTMLResponse(
            "<h1>Plans page unavailable</h1>",
            status_code=503,
        )
    return HTMLResponse(_plans_page_path.read_text("utf-8"))


if __name__ == "__main__":
    raise SystemExit("Run with an ASGI server, for example: uvicorn processual_api.main:app")
