from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException as PMK13AHTTPException
from fastapi import Request as PMK13ARequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

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

# BEGIN INTEGRATION_READINESS_12B_SUPERVISOR_SCOPE_AUDIT

_INTEGRATION_READINESS_WRITE_PATHS_12B = {
    "/settings/admin/integration-readiness-tracking/cases",
    "/settings/admin/integration-readiness-tracking/case-item-action",
}
_INTEGRATION_READINESS_WRITE_PREFIX_12B = (
    "/settings/admin/integration-readiness-tracking/cases/"
)
_INTEGRATION_READINESS_ALLOWED_SCOPES_12B = {
    "admin:clients:status_decide",
    "admin:clients:review",
    "admin:integration_readiness:review",
    "admin:integration_readiness:write",
}


def _integration_readiness_write_requires_scope_12b(path: str, method: str) -> bool:
    if method.upper() != "POST":
        return False
    if path in _INTEGRATION_READINESS_WRITE_PATHS_12B:
        return True
    return path.startswith(_INTEGRATION_READINESS_WRITE_PREFIX_12B)


def _split_supervisor_scopes_12b(value: str) -> set[str]:
    scopes = set()
    for part in str(value or "").replace(",", " ").split():
        text = part.strip()
        if text:
            scopes.add(text)
    return scopes


def _extract_readiness_audit_body_12b(raw_body: bytes) -> dict:
    if not raw_body:
        return {}
    try:
        json_module = __import__("json")
        payload = json_module.loads(raw_body.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _integration_readiness_audit_path_12b():
    os_module = __import__("os")
    pathlib_module = __import__("pathlib", fromlist=["Path"])
    env_path = os_module.getenv("PMK_ADMIN_AUDIT_EVENTS_PATH")
    if env_path:
        return pathlib_module.Path(env_path)
    return pathlib_module.Path("data") / "admin_audit_events.jsonl"


def _append_integration_readiness_audit_12b(
    request,
    payload: dict,
    status_code: int,
    *,
    supervisor_session: dict[str, object] | None = None,
) -> None:
    if status_code >= 400:
        return

    json_module = __import__("json")
    datetime_module = __import__("datetime", fromlist=["UTC", "datetime"])

    path = _integration_readiness_audit_path_12b()
    path.parent.mkdir(parents=True, exist_ok=True)

    safe_supervisor = supervisor_session or {}

    event = {
        "event": "integration_readiness_case_write",
        "event_type": "integration_readiness_case_write",
        "path": str(request.url.path),
        "method": request.method,
        "case_id": str(payload.get("case_id") or ""),
        "item_key": str(payload.get("item_key") or ""),
        "status": str(payload.get("status") or ""),
        "supervisor_session_present": bool(
            safe_supervisor.get("session_present")
        )
        if safe_supervisor
        else bool(
            request.headers.get("X-Supervisor-Session-Key")
            or request.headers.get("X-Admin-Supervisor-Session")
        ),
        "supervisor_session_validated": bool(
            safe_supervisor.get("session_validated")
        )
        if safe_supervisor
        else False,
        "session_key_id": str(safe_supervisor.get("session_key_id") or ""),
        "supervisor_scope": ",".join(
            str(scope)
            for scope in safe_supervisor.get("provided_scopes", [])
            if str(scope or "").strip()
        )
        if safe_supervisor
        else str(
            request.headers.get("X-Admin-Supervisor-Scope")
            or request.headers.get("X-Admin-Supervisor-Scopes")
            or ""
        ),
        "at": datetime_module.datetime.now(datetime_module.UTC)
        .replace(microsecond=0)
        .isoformat(),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json_module.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


@app.middleware("http")
async def integration_readiness_supervisor_scope_audit_12b(request, call_next):
    if not _integration_readiness_write_requires_scope_12b(
        str(request.url.path),
        request.method,
    ):
        return await call_next(request)

    from starlette.responses import JSONResponse

    body = await request.body()
    payload = _extract_readiness_audit_body_12b(body)

    async def receive_once_12b():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive_once_12b

    if request.headers.get("X-Supervisor-Session-Key"):
        from processual_api.services.supervisor_session_write_guard import (
            SupervisorSessionWriteGuardError,
            require_validated_supervisor_write_session,
        )

        try:
            safe_supervisor = require_validated_supervisor_write_session(
                request,
                _INTEGRATION_READINESS_ALLOWED_SCOPES_12B,
                guard_name="integration readiness writes",
            )
        except SupervisorSessionWriteGuardError as exc:
            return JSONResponse(
                {
                    "detail": exc.detail,
                    "error": exc.error,
                    "required_scopes": exc.required_scopes,
                    "supervisor_session_present": exc.session_present,
                    "supervisor_session_validated": exc.session_validated,
                    "session_key_id": exc.session_key_id,
                    "provided_scopes": exc.provided_scopes,
                    "production_allowed": False,
                    "runtime_connector_approved": False,
                    "external_http_enabled": False,
                    "raw_secret_visible": False,
                },
                status_code=403,
            )

        response = await call_next(request)
        _append_integration_readiness_audit_12b(
            request,
            payload,
            response.status_code,
            supervisor_session=safe_supervisor,
        )
        return response

    supervisor_session = str(
        request.headers.get("X-Admin-Supervisor-Session") or ""
    ).strip()
    if not supervisor_session:
        return JSONResponse(
            {
                "detail": "Supervisor session required for integration readiness writes",
                "production_allowed": False,
                "runtime_connector_approved": False,
                "external_http_enabled": False,
                "raw_secret_visible": False,
            },
            status_code=403,
        )

    explicit_scope_header = (
        request.headers.get("X-Admin-Supervisor-Scope")
        or request.headers.get("X-Admin-Supervisor-Scopes")
        or ""
    )
    explicit_scopes = _split_supervisor_scopes_12b(explicit_scope_header)
    if explicit_scopes and not (
        explicit_scopes & _INTEGRATION_READINESS_ALLOWED_SCOPES_12B
    ):
        return JSONResponse(
            {
                "detail": "Supervisor scope does not allow integration readiness writes",
                "required_scopes": sorted(_INTEGRATION_READINESS_ALLOWED_SCOPES_12B),
                "production_allowed": False,
                "runtime_connector_approved": False,
                "external_http_enabled": False,
                "raw_secret_visible": False,
            },
            status_code=403,
        )

    response = await call_next(request)
    _append_integration_readiness_audit_12b(request, payload, response.status_code)
    return response
# END INTEGRATION_READINESS_12B_SUPERVISOR_SCOPE_AUDIT

# BEGIN INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_ROUTES

@app.get("/settings/admin/integration-readiness-operator-package")
def admin_integration_readiness_operator_package_12c():
    from processual_api.services.operator_readiness_package import (
        build_operator_readiness_package_12c,
    )

    return build_operator_readiness_package_12c()


@app.get("/settings/admin/integration-readiness-operator-package/export")
def admin_integration_readiness_operator_package_export_12c():
    from starlette.responses import PlainTextResponse

    from processual_api.services.operator_readiness_package import (
        render_operator_readiness_markdown_12c,
    )

    return PlainTextResponse(
        render_operator_readiness_markdown_12c(),
        media_type="text/markdown; charset=utf-8",
    )
# END INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_ROUTES

# PMK INTEGRATION CLAIM KEYS 13A START

PMK13A_ALLOWED_SUPERVISOR_SCOPES = {
    "admin:clients:review",
    "admin:clients:status_decide",
    "admin:integration_readiness:review",
    "admin:integration_readiness:write",
}


def _pmk13a_split_scopes(value: str | None) -> set[str]:
    if not value:
        return set()
    scopes: set[str] = set()
    for chunk in str(value).replace(",", " ").split():
        text = chunk.strip()
        if text:
            scopes.add(text)
    return scopes



# BEGIN INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES

@app.get("/settings/admin/operator-pilot-handoff")
def admin_operator_pilot_handoff_package_14b():
    """Return the safe read-only operator pilot handoff package."""
    from processual_api.services.operator_pilot_handoff import (
        build_operator_pilot_handoff_package,
    )

    return build_operator_pilot_handoff_package()


@app.get("/settings/admin/operator-pilot-handoff/export")
def admin_operator_pilot_handoff_export_14b():
    """Export the safe operator pilot handoff package as Markdown."""
    from starlette.responses import PlainTextResponse

    from processual_api.services.operator_pilot_handoff import (
        build_operator_pilot_handoff_package,
        render_operator_pilot_handoff_markdown,
    )

    package = build_operator_pilot_handoff_package()
    markdown = render_operator_pilot_handoff_markdown(package)

    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="operator-pilot-handoff-14b.md"'
            )
        },
    )


# END INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES
def _pmk13a_request_scopes(request: PMK13ARequest) -> set[str]:
    scopes = set()
    scopes |= _pmk13a_split_scopes(request.headers.get("X-Admin-Supervisor-Scope"))
    scopes |= _pmk13a_split_scopes(request.headers.get("X-Admin-Supervisor-Scopes"))
    return scopes


def _pmk13a_require_supervisor_write(request: PMK13ARequest) -> None:
    session = request.headers.get("X-Admin-Supervisor-Session")
    scopes = _pmk13a_request_scopes(request)
    if session and scopes.intersection(PMK13A_ALLOWED_SUPERVISOR_SCOPES):
        return

    raise PMK13AHTTPException(
        status_code=403,
        detail={
            "error": "supervisor_scope_required",
            "required_any_scope": sorted(PMK13A_ALLOWED_SUPERVISOR_SCOPES),
            "supervisor_session_present": bool(session),
            "provided_scopes": sorted(scopes),
            **PMK13A_CLAIM_GUARDRAILS,
        },
    )


@app.post("/settings/admin/integration-claim-keys")
async def pmk13a_admin_issue_integration_claim_key(request: PMK13ARequest):
    _pmk13a_require_supervisor_write(request)
    payload = await request.json()
    issued_by = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return pmk13a_issue_integration_claim_key(payload, issued_by=issued_by)


@app.get("/settings/admin/integration-claim-keys")
async def pmk13a_admin_list_integration_claim_keys():
    return pmk13a_list_integration_claim_keys()


@app.post("/settings/admin/integration-claim-keys/{claim_key_id}/revoke")
async def pmk13a_admin_revoke_integration_claim_key(
    claim_key_id: str,
    request: PMK13ARequest,
):
    _pmk13a_require_supervisor_write(request)
    payload = await request.json()
    revoked_by = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return pmk13a_revoke_integration_claim_key(
        claim_key_id,
        revoked_by=revoked_by,
        reason=str(payload.get("reason", "")).strip(),
    )


@app.post("/settings/client/integration-claim-keys/redeem")
async def pmk13a_client_redeem_integration_claim_key(request: PMK13ARequest):
    payload = await request.json()
    return pmk13a_redeem_integration_claim_key(payload)


@app.get("/settings/client/integration-onboarding/status")
async def pmk13a_client_integration_onboarding_status(request: PMK13ARequest):
    return pmk13a_get_client_integration_onboarding_status(
        client_id=request.query_params.get("client_id"),
        user_id=request.query_params.get("user_id"),
    )


# PMK INTEGRATION CLAIM KEYS 13A END

# PMK INTEGRATION PILOT CONTROLS 13B START

PMK13B_ALLOWED_SUPERVISOR_SCOPES = {
    "admin:clients:review",
    "admin:clients:status_decide",
    "admin:integration_readiness:review",
    "admin:integration_readiness:write",
    "admin:api_keys:read",
}


def _pmk13b_split_scopes(value: str | None) -> set[str]:
    if not value:
        return set()
    scopes: set[str] = set()
    for chunk in str(value).replace(",", " ").split():
        text = chunk.strip()
        if text:
            scopes.add(text)
    return scopes


def _pmk13b_supervisor_session_store_path():
    from pathlib import Path

    return Path(__file__).resolve().parent / "data" / "supervisor_session_keys.json"


def _pmk13b_scopes_from_supervisor_session(raw_key: str | None) -> set[str]:
    if not raw_key:
        return set()

    try:
        from processual_api.supervisor_session_keys import validate_supervisor_session_key

        safe_record = validate_supervisor_session_key(
            _pmk13b_supervisor_session_store_path(),
            str(raw_key),
        )
    except (PermissionError, OSError, ValueError, TypeError):
        return set()

    raw_scopes = safe_record.get("scopes") or []
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]

    return {str(scope).strip() for scope in raw_scopes if str(scope).strip()}


def _pmk13b_request_scopes(request) -> set[str]:
    scopes = set()
    scopes |= _pmk13b_split_scopes(request.headers.get("X-Admin-Supervisor-Scope"))
    scopes |= _pmk13b_split_scopes(request.headers.get("X-Admin-Supervisor-Scopes"))
    scopes |= _pmk13b_scopes_from_supervisor_session(
        request.headers.get("X-Admin-Supervisor-Session")
    )
    return scopes


def _pmk13b_require_supervisor_write(request) -> None:
    from fastapi import HTTPException

    from processual_api.services.integration_pilot_controls import GUARDRAILS

    session = request.headers.get("X-Admin-Supervisor-Session")
    scopes = _pmk13b_request_scopes(request)
    if session and scopes.intersection(PMK13B_ALLOWED_SUPERVISOR_SCOPES):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "supervisor_scope_required",
            "required_any_scope": sorted(PMK13B_ALLOWED_SUPERVISOR_SCOPES),
            "supervisor_session_present": bool(session),
            "provided_scopes": sorted(scopes),
            **GUARDRAILS,
        },
    )


@app.get("/settings/admin/integration-tasks")
async def pmk13b_admin_list_integration_tasks():
    from processual_api.services.integration_pilot_controls import list_integration_tasks

    return list_integration_tasks()


@app.post("/settings/admin/integration-tasks")
async def pmk13b_admin_create_integration_task(request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import create_integration_task

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return create_integration_task(payload, created_by=actor)


@app.post("/settings/admin/integration-tasks/{task_id}/suspend")
async def pmk13b_admin_suspend_integration_task(task_id: str, request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import control_integration_task

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return control_integration_task(
        task_id,
        "suspend",
        actor=actor,
        reason=str(payload.get("reason", "")).strip(),
    )


@app.post("/settings/admin/integration-tasks/{task_id}/resume")
async def pmk13b_admin_resume_integration_task(task_id: str, request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import control_integration_task

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return control_integration_task(
        task_id,
        "resume",
        actor=actor,
        reason=str(payload.get("reason", "")).strip(),
    )


@app.post("/settings/admin/integration-tasks/{task_id}/revoke")
async def pmk13b_admin_revoke_integration_task(task_id: str, request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import control_integration_task

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return control_integration_task(
        task_id,
        "revoke",
        actor=actor,
        reason=str(payload.get("reason", "")).strip(),
    )


@app.post("/settings/admin/integration-tasks/{task_id}/cancel")
async def pmk13b_admin_cancel_integration_task(task_id: str, request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import control_integration_task

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return control_integration_task(
        task_id,
        "cancel",
        actor=actor,
        reason=str(payload.get("reason", "")).strip(),
    )


@app.post("/settings/admin/integration-tasks/{task_id}/activation-permission-key")
async def pmk13b_admin_issue_activation_permission_key(task_id: str, request: PMK13ARequest):
    from processual_api.services.integration_pilot_controls import (
        issue_activation_permission_key,
    )

    _pmk13b_require_supervisor_write(request)
    payload = await request.json()
    actor = request.headers.get("X-Admin-Supervisor-Session") or "supervisor"
    return issue_activation_permission_key(task_id, payload, issued_by=actor)


# PMK INTEGRATION PILOT CONTROLS 13B END

# PMK OPERATOR PILOT HANDOFF ACTIONS 14D START
@app.get("/settings/admin/operator-pilot-handoff/actions-preview")
def admin_operator_pilot_handoff_actions_preview_14d() -> dict[str, object]:
    """Return the read-only operator pilot handoff actions preview."""
    from processual_api.services.operator_pilot_handoff_actions import (  # noqa: PLC0415
        build_operator_pilot_handoff_actions_preview,
    )

    return build_operator_pilot_handoff_actions_preview()


# PMK OPERATOR PILOT HANDOFF ACTIONS 14D END

# PMK OPERATOR PILOT HANDOFF PROGRESS 14E START
PMK14E_ALLOWED_SUPERVISOR_SCOPES = {
    "admin:clients:status_decide",
    "admin:integration_readiness:write",
}


def _pmk14e_write_guardrails() -> dict[str, bool]:
    return {
        "production_allowed": False,
        "runtime_connector_approved": False,
        "customer_credentials_present": False,
        "external_http_allowed": False,
        "automatic_activation_allowed": False,
        "action_execution_allowed": False,
        "credentials_storage_allowed": False,
        "free_form_secret_fields_allowed": False,
        "local_progress_tracking_only": True,
    }


def _pmk14e_supervisor_session_store_path():
    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    configured = os.environ.get(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        "",
    ).strip()

    if configured:
        return Path(configured)

    return _pmk13b_supervisor_session_store_path()


def _pmk14e_require_supervisor_write(
    request: PMK13ARequest,
) -> str:
    from fastapi import HTTPException  # noqa: PLC0415

    from processual_api.supervisor_session_keys import (  # noqa: PLC0415
        validate_supervisor_session_key,
    )

    supervisor_session = str(
        request.headers.get("X-Supervisor-Session-Key")
        or request.headers.get("X-Admin-Supervisor-Session")
        or ""
    ).strip()

    if not supervisor_session:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "supervisor_session_required",
                "required_any_scope": sorted(
                    PMK14E_ALLOWED_SUPERVISOR_SCOPES
                ),
                "supervisor_session_present": False,
                "supervisor_session_validated": False,
                "provided_scopes": [],
                **_pmk14e_write_guardrails(),
            },
        )

    try:
        safe_session = validate_supervisor_session_key(
            _pmk14e_supervisor_session_store_path(),
            supervisor_session,
        )
    except (PermissionError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "invalid_supervisor_session",
                "required_any_scope": sorted(
                    PMK14E_ALLOWED_SUPERVISOR_SCOPES
                ),
                "supervisor_session_present": True,
                "supervisor_session_validated": False,
                "provided_scopes": [],
                **_pmk14e_write_guardrails(),
            },
        ) from exc

    raw_scopes = safe_session.get("scopes") or []

    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]

    supervisor_scopes = {
        str(scope).strip()
        for scope in raw_scopes
        if str(scope or "").strip()
    }

    session_key_id = str(
        safe_session.get("session_key_id") or ""
    ).strip()

    if (
        not session_key_id
        or not supervisor_scopes.intersection(
            PMK14E_ALLOWED_SUPERVISOR_SCOPES
        )
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "supervisor_scope_required",
                "required_any_scope": sorted(
                    PMK14E_ALLOWED_SUPERVISOR_SCOPES
                ),
                "supervisor_session_present": True,
                "supervisor_session_validated": True,
                "session_key_id": session_key_id,
                "provided_scopes": sorted(supervisor_scopes),
                **_pmk14e_write_guardrails(),
            },
        )

    # Persist only the safe identifier. Never persist the raw session key.
    return session_key_id

@app.get("/settings/admin/operator-pilot-handoff/progress")
def admin_operator_pilot_handoff_progress_14e() -> dict[str, object]:
    """Return safe local progress for operator pilot handoff actions."""
    from processual_api.services.operator_pilot_handoff_progress_store import (  # noqa: PLC0415
        build_operator_pilot_handoff_progress_payload,
    )

    return build_operator_pilot_handoff_progress_payload()


@app.post(
    "/settings/admin/operator-pilot-handoff/progress/actions/{action_id}"
)
async def admin_update_operator_pilot_handoff_progress_14e(
    action_id: str,
    request: PMK13ARequest,
) -> dict[str, object]:
    """Persist safe supervisor-reviewed handoff progress metadata."""
    from fastapi import HTTPException  # noqa: PLC0415

    from processual_api.services.operator_pilot_handoff_progress_store import (  # noqa: PLC0415
        update_operator_pilot_handoff_action_progress,
    )

    supervisor_actor = _pmk14e_require_supervisor_write(request)

    try:
        raw_payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="progress update payload must be a JSON object",
        ) from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=422,
            detail="progress update payload must be a JSON object",
        )

    progress_payload = dict(raw_payload)

    # The actor is always derived from the protected supervisor session.
    # A client-provided actor value cannot impersonate another supervisor.
    progress_payload["supervisor_actor"] = supervisor_actor

    try:
        return update_operator_pilot_handoff_action_progress(
            action_id,
            progress_payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# PMK OPERATOR PILOT HANDOFF PROGRESS 14E END
