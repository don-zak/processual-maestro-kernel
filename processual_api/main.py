from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
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

# Serve the Maestro Console frontend (single-page app)
_static_dir = Path(__file__).resolve().parent / "static"
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
