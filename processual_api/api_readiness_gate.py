from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI
from fastapi.routing import APIRoute

from processual_api.api_readiness import ApiReadiness, ApiSurfacePolicy, readiness_for_path


@dataclass(frozen=True, slots=True)
class MountedRoute:
    method: str
    path: str
    name: str
    include_in_schema: bool

    @property
    def key(self) -> tuple[str, str]:
        return self.method, self.path


@dataclass(frozen=True, slots=True)
class RouteReadinessRecord:
    method: str
    path: str
    route_name: str
    surface_id: str | None
    readiness: ApiReadiness | None
    production_allowed: bool
    ignored: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["readiness"] = self.readiness.value if self.readiness is not None else None
        return payload


@dataclass(frozen=True, slots=True)
class ApiReadinessAudit:
    records: tuple[RouteReadinessRecord, ...]
    duplicate_route_keys: tuple[tuple[str, str], ...]
    inventory_digest: str

    @property
    def unknown_records(self) -> tuple[RouteReadinessRecord, ...]:
        return tuple(record for record in self.records if not record.ignored and record.surface_id is None)

    @property
    def is_valid(self) -> bool:
        return not self.unknown_records and not self.duplicate_route_keys

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.is_valid,
            "inventory_digest": self.inventory_digest,
            "unknown_routes": [record.to_dict() for record in self.unknown_records],
            "duplicate_routes": [
                {"method": method, "path": path} for method, path in self.duplicate_route_keys
            ],
            "routes": [record.to_dict() for record in self.records],
        }


_SYSTEM_ROUTE_POLICIES = {
    ("GET", "/"): "public_html",
    ("GET", "/admin"): "public_html",
    ("GET", "/docs"): "fastapi_docs",
    ("GET", "/docs/oauth2-redirect"): "fastapi_docs",
    ("GET", "/login"): "public_html",
    ("GET", "/openapi.json"): "fastapi_openapi",
    ("GET", "/offer/{plan_id}"): "public_html",
    ("GET", "/plans"): "public_html",
    ("GET", "/pricing"): "public_html",
    ("GET", "/pricing.html"): "public_html",
    ("GET", "/redoc"): "fastapi_docs",
    ("GET", "/register"): "public_html",
    ("GET", "/verify-email"): "public_html",
}
SYSTEM_ROUTE_POLICIES: Final = MappingProxyType(_SYSTEM_ROUTE_POLICIES)
_EXCLUDED_METHODS: Final = frozenset({"HEAD", "OPTIONS"})


def normalize_route_path(path: str) -> str:
    value = str(path or "").strip() or "/"
    if not value.startswith("/"):
        value = "/" + value
    if value != "/":
        value = value.rstrip("/")
    return value


def normalize_route_method(method: str) -> str:
    return str(method or "").strip().upper()


def enumerate_mounted_routes(app: FastAPI) -> tuple[MountedRoute, ...]:
    mounted: list[MountedRoute] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = normalize_route_path(route.path)
        for raw_method in sorted(route.methods or set()):
            method = normalize_route_method(raw_method)
            if not method or method in _EXCLUDED_METHODS:
                continue
            mounted.append(MountedRoute(method, path, str(route.name or ""), bool(route.include_in_schema)))
    return tuple(sorted(mounted, key=lambda item: (item.path, item.method, item.name)))


def route_inventory_digest(app: FastAPI) -> str:
    material = "\n".join(f"{route.method} {route.path}" for route in enumerate_mounted_routes(app))
    return sha256(material.encode("utf-8")).hexdigest()


def _system_route_reason(route: MountedRoute) -> str | None:
    explicit = SYSTEM_ROUTE_POLICIES.get(route.key)
    if explicit is not None:
        return explicit
    if route.path == "/console" or route.path.startswith("/console/"):
        return "static_console"
    return None


def _record_for_policy(route: MountedRoute, policy: ApiSurfacePolicy) -> RouteReadinessRecord:
    return RouteReadinessRecord(route.method, route.path, route.name, policy.surface_id, policy.readiness, policy.production_allowed, False, "classified")


def audit_mounted_routes(app: FastAPI) -> ApiReadinessAudit:
    routes = enumerate_mounted_routes(app)
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    records: list[RouteReadinessRecord] = []
    for route in routes:
        if route.key in seen:
            duplicates.add(route.key)
        seen.add(route.key)
        system_reason = _system_route_reason(route)
        if system_reason is not None:
            records.append(RouteReadinessRecord(route.method, route.path, route.name, None, None, False, True, system_reason))
            continue
        policy = readiness_for_path(route.path)
        if policy is None:
            records.append(RouteReadinessRecord(route.method, route.path, route.name, None, None, False, False, "unclassified"))
            continue
        records.append(_record_for_policy(route, policy))
    return ApiReadinessAudit(tuple(records), tuple(sorted(duplicates)), route_inventory_digest(app))


def readiness_report(app: FastAPI) -> dict[str, object]:
    return audit_mounted_routes(app).to_dict()


def validate_mounted_route_readiness(app: FastAPI, *, expected_inventory_digest: str | None = None) -> None:
    audit = audit_mounted_routes(app)
    if audit.duplicate_route_keys:
        rendered = ", ".join(f"{method} {path}" for method, path in audit.duplicate_route_keys)
        raise ValueError(f"duplicate mounted API route policies: {rendered}")
    if audit.unknown_records:
        rendered = ", ".join(f"{record.method} {record.path}" for record in audit.unknown_records)
        raise ValueError(f"unclassified mounted API routes: {rendered}")
    if expected_inventory_digest is not None and audit.inventory_digest != expected_inventory_digest:
        raise ValueError(
            "mounted API route inventory changed: "
            f"expected={expected_inventory_digest} actual={audit.inventory_digest}"
        )


def classified_records(records: Iterable[RouteReadinessRecord]) -> tuple[RouteReadinessRecord, ...]:
    return tuple(record for record in records if not record.ignored and record.surface_id is not None)


__all__ = [
    "ApiReadinessAudit", "MountedRoute", "RouteReadinessRecord", "SYSTEM_ROUTE_POLICIES",
    "audit_mounted_routes", "classified_records", "enumerate_mounted_routes", "normalize_route_method",
    "normalize_route_path", "readiness_report", "route_inventory_digest", "validate_mounted_route_readiness",
]
