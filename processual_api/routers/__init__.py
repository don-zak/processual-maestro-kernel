"""API route handlers — all HTTP endpoints organized by domain."""

from .applications import router as applications_router
from .cgt import router as cgt_router
from .cgt_governor import router as cgt_governor_router
from .discord import router as discord_router
from .governance import router as governance_router
from .health import router as health_router
from .reports import router as reports_router
from .settings import router as settings_router
from .telemetry import router as telemetry_router
from .workflows import router as workflows_router

__all__ = [
    "health_router",
    "cgt_router",
    "workflows_router",
    "governance_router",
    "telemetry_router",
    "reports_router",
    "discord_router",
    "cgt_governor_router",
    "settings_router",
    "applications_router",
]
