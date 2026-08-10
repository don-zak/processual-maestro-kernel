from fastapi import FastAPI

from processual_api.api_readiness import ApiReadiness
from processual_api.api_readiness_gate import (
    SYSTEM_ROUTE_POLICIES,
    audit_mounted_routes,
    enumerate_mounted_routes,
    normalize_route_method,
    normalize_route_path,
    readiness_report,
    route_inventory_digest,
    validate_mounted_route_readiness,
)


def test_route_normalization_is_deterministic() -> None:
    assert normalize_route_path("") == "/"
    assert normalize_route_path("health/") == "/health"
    assert normalize_route_path("/health/") == "/health"
    assert normalize_route_method(" get ") == "GET"


def test_enumerate_mounted_routes_ignores_head_and_options() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/health", methods=["GET", "HEAD", "OPTIONS"])
    async def health() -> dict[str, bool]:
        return {"ok": True}

    mounted = enumerate_mounted_routes(app)
    assert [(route.method, route.path) for route in mounted] == [("GET", "/health")]


def test_known_route_is_classified() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    audit = audit_mounted_routes(app)
    assert audit.is_valid is True
    assert audit.unknown_records == ()
    record = audit.records[0]
    assert record.surface_id == "health"
    assert record.readiness is ApiReadiness.PRODUCTION_READY
    assert record.production_allowed is True


def test_unknown_route_fails_closed() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/new-unclassified-api")
    async def unknown() -> dict[str, bool]:
        return {"ok": True}

    audit = audit_mounted_routes(app)
    assert audit.is_valid is False
    assert [(record.method, record.path) for record in audit.unknown_records] == [
        ("GET", "/new-unclassified-api")
    ]

    try:
        validate_mounted_route_readiness(app)
    except ValueError as exc:
        assert "unclassified mounted API routes" in str(exc)
        assert "GET /new-unclassified-api" in str(exc)
    else:
        raise AssertionError("unknown mounted route must fail closed")


def test_inventory_change_fails_even_under_known_surface_prefix() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/workflows")
    async def workflows() -> dict[str, bool]:
        return {"ok": True}

    approved_digest = route_inventory_digest(app)

    @app.post("/workflows/new-endpoint")
    async def new_workflow_endpoint() -> dict[str, bool]:
        return {"ok": True}

    try:
        validate_mounted_route_readiness(app, expected_inventory_digest=approved_digest)
    except ValueError as exc:
        assert "mounted API route inventory changed" in str(exc)
    else:
        raise AssertionError("new route under a known prefix must require inventory review")


def test_duplicate_method_and_path_is_rejected() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health_one() -> dict[str, int]:
        return {"version": 1}

    @app.get("/health")
    async def health_two() -> dict[str, int]:
        return {"version": 2}

    audit = audit_mounted_routes(app)
    assert audit.duplicate_route_keys == (("GET", "/health"),)
    assert audit.is_valid is False

    try:
        validate_mounted_route_readiness(app)
    except ValueError as exc:
        assert "duplicate mounted API route policies" in str(exc)
        assert "GET /health" in str(exc)
    else:
        raise AssertionError("duplicate mounted route must fail closed")


def test_sandbox_internal_and_disabled_routes_preserve_readiness() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/settings/enterprise-integration/cases")
    async def sandbox() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/internal/execution/runs")
    async def internal() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/billing/topups/purchase")
    async def disabled() -> dict[str, bool]:
        return {"ok": True}

    audit = audit_mounted_routes(app)
    readiness = {record.path: record.readiness for record in audit.records}
    allowed = {record.path: record.production_allowed for record in audit.records}

    assert readiness["/settings/enterprise-integration/cases"] is ApiReadiness.SANDBOX_ONLY
    assert readiness["/internal/execution/runs"] is ApiReadiness.INTERNAL_ONLY
    assert readiness["/billing/topups/purchase"] is ApiReadiness.DISABLED
    assert allowed["/settings/enterprise-integration/cases"] is False
    assert allowed["/internal/execution/runs"] is False
    assert allowed["/billing/topups/purchase"] is False


def test_explicit_system_routes_are_ignored_not_promoted() -> None:
    app = FastAPI()

    @app.get("/", include_in_schema=False)
    async def splash() -> dict[str, bool]:
        return {"ok": True}

    audit = audit_mounted_routes(app)
    ignored = {
        (record.method, record.path): record
        for record in audit.records
        if record.ignored
    }

    assert ("GET", "/") in SYSTEM_ROUTE_POLICIES
    assert ignored[("GET", "/")].production_allowed is False
    assert ignored[("GET", "/")].surface_id is None
    assert audit.unknown_records == ()


def test_report_is_machine_readable_and_fail_closed() -> None:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/unknown")
    async def unknown() -> dict[str, bool]:
        return {"ok": True}

    report = readiness_report(app)
    assert report["valid"] is False
    assert isinstance(report["inventory_digest"], str)
    assert report["duplicate_routes"] == []
    assert report["unknown_routes"] == [
        {
            "method": "GET",
            "path": "/unknown",
            "route_name": "unknown",
            "surface_id": None,
            "readiness": None,
            "production_allowed": False,
            "ignored": False,
            "reason": "unclassified",
        }
    ]
