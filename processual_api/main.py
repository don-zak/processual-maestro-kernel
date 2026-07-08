from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
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
app.include_router(cgt.router)
app.include_router(workflows.router)
app.include_router(governance.router)
app.include_router(telemetry.router)
app.include_router(reports.router)
app.include_router(discord.router)
app.include_router(cgt_governor.router)
app.include_router(settings_router.router)
app.include_router(applications.router)
app.include_router(billing_router)

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


_splash_path = Path(__file__).resolve().parent / "static" / "splash.html"
_splash_html = _splash_path.read_text("utf-8") if _splash_path.exists() else "<h1>Splash page not found</h1>"

_login_path = Path(__file__).resolve().parent / "static" / "login.html"
_login_html = _login_path.read_text("utf-8") if _login_path.exists() else "<h1>Login page not found</h1>"
_admin_path = Path(__file__).resolve().parent / "static" / "admin.html"
_admin_html = _admin_path.read_text("utf-8") if _admin_path.exists() else "<h1>Admin page not found</h1>"


@app.get("/", include_in_schema=False)
async def splash_page():
    return HTMLResponse(content=_splash_html)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page():
    return HTMLResponse(content=_login_html)



@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page():
    return HTMLResponse(content=_admin_html)
@app.get("/metrics")
async def metrics_endpoint():
    try:
        from prometheus_client import generate_latest

        return Response(content=generate_latest(), media_type="text/plain")
    except Exception:
        return PlainTextResponse("# Prometheus metrics not available\n")

# INTEGRATION_READINESS_TRACKING_11P_MAIN_ROUTE_MARKER
@app.get("/settings/admin/integration-readiness-tracking")
async def admin_integration_readiness_tracking_summary_11p() -> dict[str, object]:
    """Return safe integration readiness tracking summary."""

    from processual_api.services.integration_readiness_tracking_store import (
        admin_tracking_summary_payload,
    )

    return admin_tracking_summary_payload()


@app.post("/settings/admin/integration-readiness-tracking/cases")
async def admin_create_integration_readiness_tracking_case_11p(
    payload: dict[str, object],
) -> dict[str, object]:
    """Create or replace a safe readiness tracking case."""

    from processual_api.services.integration_readiness_tracking_store import (
        create_tracking_case_from_payload,
    )

    return create_tracking_case_from_payload(dict(payload))


@app.post("/settings/admin/integration-readiness-tracking/cases/{case_id:path}/items")
async def admin_update_integration_readiness_tracking_case_item_11p(
    case_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Update a safe readiness tracking case item."""

    from processual_api.services.integration_readiness_tracking_store import (
        update_tracking_case_item_from_payload,
    )

    try:
        return update_tracking_case_item_from_payload(case_id, dict(payload))
    except KeyError:
        return {
            "error": "readiness_tracking_case_not_found",
            "case_id": case_id,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_enabled": False,
            "raw_secret_visible": False,
        }

# BEGIN INTEGRATION_READINESS_12A_CASE_MANAGEMENT_ROUTES

@app.get("/settings/admin/integration-readiness-tracking/cases")
def admin_integration_readiness_tracking_cases_12a():
    from processual_api.services.integration_readiness_tracking_store import (
        list_tracking_cases_12a,
    )

    return list_tracking_cases_12a()


@app.get("/settings/admin/integration-readiness-tracking/case-detail")
def admin_integration_readiness_tracking_case_detail_query_12a(case_id: str):
    from fastapi import HTTPException

    from processual_api.services.integration_readiness_tracking_store import (
        build_tracking_case_detail_payload_12a,
    )

    try:
        return build_tracking_case_detail_payload_12a(case_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Integration readiness case not found",
        ) from exc


@app.get("/settings/admin/integration-readiness-tracking/cases/{case_id:path}")
def admin_integration_readiness_tracking_case_detail_12a(case_id: str):
    from fastapi import HTTPException

    from processual_api.services.integration_readiness_tracking_store import (
        build_tracking_case_detail_payload_12a,
    )

    try:
        return build_tracking_case_detail_payload_12a(case_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Integration readiness case not found",
        ) from exc


@app.post("/settings/admin/integration-readiness-tracking/case-item-action")
def admin_integration_readiness_tracking_case_item_action_12a(
    payload: dict[str, object],
):
    from fastapi import HTTPException

    from processual_api.services.integration_readiness_tracking_store import (
        update_tracking_case_item_12a,
    )

    try:
        return update_tracking_case_item_12a(
            case_id=str(payload.get("case_id") or ""),
            item_key=str(payload.get("item_key") or ""),
            status=str(payload.get("status") or ""),
            safe_reference=str(payload.get("safe_reference") or ""),
            note=str(payload.get("note") or ""),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Integration readiness case not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
# END INTEGRATION_READINESS_12A_CASE_MANAGEMENT_ROUTES

# BEGIN INTEGRATION_READINESS_12A_SUMMARY_ROUTE_REBIND

def _admin_integration_readiness_tracking_summary_12a_compat():
    from processual_api.services.integration_readiness_tracking_store import (
        build_tracking_summary_12a_compat,
    )

    return build_tracking_summary_12a_compat()


app.router.routes = [
    route
    for route in app.router.routes
    if not (
        getattr(route, "path", "") == "/settings/admin/integration-readiness-tracking"
        and "GET" in (getattr(route, "methods", set()) or set())
    )
]

app.add_api_route(
    "/settings/admin/integration-readiness-tracking",
    _admin_integration_readiness_tracking_summary_12a_compat,
    methods=["GET"],
    name="admin_integration_readiness_tracking_summary_12a_compat",
)
# END INTEGRATION_READINESS_12A_SUMMARY_ROUTE_REBIND
