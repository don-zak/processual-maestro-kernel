import json
import warnings

import pytest

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient  # noqa: E402

import processual_api.middleware.rate_limit as rate_module  # noqa: E402
import processual_api.routers.cgt_governor as cgt_router  # noqa: E402
from processual_api.auth.security import _pbkdf2_hash_api_key  # noqa: E402
from processual_api.main import app  # noqa: E402
from processual_api.services import api_key_store, quota_store  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    async def no_redis():
        return None

    monkeypatch.setattr(rate_module, "get_redis", no_redis)

    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()

def _route_path(route):
    return getattr(route, "path", "").rstrip("/")


def _route_methods(route):
    return set(getattr(route, "methods", set()) or set())


def _route_dependencies(route):
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return []
    return [
        dependency.call
        for dependency in dependant.dependencies
        if dependency.call is not None
    ]


def _override_route_dependencies(path: str, method: str, value: dict):
    method = method.upper()
    normalized_target = path.rstrip("/")
    overridden = []
    available = []

    route_sets = [
        ("app", app.routes),
        ("cgt_governor.router", cgt_router.router.routes),
    ]

    for source_name, routes in route_sets:
        for route in routes:
            route_path = _route_path(route)
            route_methods = _route_methods(route)

            if route_path or route_methods:
                available.append(
                    f"{source_name}: {','.join(sorted(route_methods))} {route_path}"
                )

            if method in route_methods and (
                route_path == normalized_target
                or route_path.endswith(normalized_target)
            ):
                dependencies = _route_dependencies(route)

                for dependency_call in dependencies:
                    app.dependency_overrides[dependency_call] = (
                        lambda value=value: value
                    )
                    overridden.append(dependency_call)

                if not overridden:
                    raise AssertionError(
                        f"No direct dependencies found for {method} {path}"
                    )

                return overridden

    raise AssertionError(
        f"Route not found: {method} {path}. Available routes: {available}"
    )





def test_full_app_health_endpoints_and_global_headers(client):
    response = client.get("/health/live", headers={"X-Request-ID": "smoke-10a"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "smoke-10a"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-xss-protection"] == "1; mode=block"
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )

    ready = client.get("/health/ready")
    assert ready.status_code in {200, 503}
    assert ready.headers.get("x-content-type-options") == "nosniff"


def test_full_app_public_pages_and_metrics_are_reachable(client):
    root = client.get("/")
    login = client.get("/login")
    metrics = client.get("/metrics")

    assert root.status_code == 200
    assert login.status_code == 200
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers.get("content-type", "")


def test_full_app_protected_routes_reject_anonymous_requests(client):
    adapters = client.get("/adapters/status")
    create_key = client.post("/settings/api-keys", json={"name": "Smoke key"})

    assert adapters.status_code in {401, 403}
    assert create_key.status_code in {401, 403}


def test_full_app_adapter_status_works_with_overridden_read_dependency(client):
    _override_route_dependencies(
        "/adapters/status",
        "GET",
        {
            "sub": "integration-user",
            "user_id": "integration-user",
            "scopes": ["read:adapters"],
            "role": "client",
        },
    )

    response = client.get("/adapters/status")

    assert response.status_code == 200
    payload = response.json()
    assert "providers" in payload
    assert isinstance(payload["providers"], list)


def test_full_app_cgt_govern_controlled_smoke_with_overridden_quota(
    client,
    monkeypatch,
):
    def fake_resolve_scores(req):
        assert req.answer == "Smoke governed answer."
        return {"compatibility": 0.88}

    def fake_evaluate_and_record(
        answer,
        language,
        scores,
        context=None,
        reason="govern",
    ):
        assert answer == "Smoke governed answer."
        assert language == "en"
        assert scores == {"compatibility": 0.88}
        assert reason == "govern"

        response_data = {
            "rank": "stable",
            "reward": 0.88,
            "policy": "accept",
            "policy_label": "Accept",
            "fate_vector": {"stability": 0.88},
        }
        return {
            "response_data": response_data,
            "signature": "sig-smoke-10a",
            "governance_action": "keep",
            "action_label": "Keep - Accept Response",
            "entry": {"eval_id": "eval_smoke_10a"},
        }

    monkeypatch.setattr(cgt_router, "_resolve_scores", fake_resolve_scores)
    monkeypatch.setattr(cgt_router, "_evaluate_and_record", fake_evaluate_and_record)

    _override_route_dependencies(
        "/cgt/govern",
        "POST",
        {
            "sub": "integration-user",
            "user_id": "integration-user",
            "scopes": ["evaluation"],
            "role": "client",
            "auth_method": "api_key",
            "api_key_id": "key_smoke_10a",
        },
    )

    response = client.post(
        "/cgt/govern",
        json={
            "answer": "Smoke governed answer.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["rank"] == "stable"
    assert payload["reward"] == 0.88
    assert payload["signature"] == "sig-smoke-10a"
    assert payload["governance_action"] == "keep"
    assert payload["action_label"] == "Keep - Accept Response"
    assert payload["eval_id"] == "eval_smoke_10a"
    assert payload["analysis_mode"] == "fallback"



def test_full_app_cgt_govern_rejects_exhausted_dynamic_api_key(
    client,
    monkeypatch,
    tmp_path,
):
    import processual_api.services.usage_log_store as usage_log_store

    raw_key = "pmk_exhausted_quota_endpoint_test_key"
    usage_log_path = tmp_path / "usage_logs.jsonl"

    settings_path = tmp_path / "settings_quota_endpoint_user.json"
    settings_path.write_text(
        json.dumps(
            {
                "subscription": {"plan_id": "starter"},
                "api_keys": [
                    {
                        "id": "key_exhausted_10b",
                        "user_id": "quota-endpoint-user",
                        "client_id": "quota-endpoint-client",
                        "prefix": "pmk_exhausted...",
                        "hashed": _pbkdf2_hash_api_key(raw_key),
                        "scopes": ["run:govern"],
                        "profile": "client",
                        "plan_id": "starter",
                        "quota_policy": {
                            "id": "manual_override",
                            "source": "manual",
                            "quotas": {"evaluation": 1},
                        },
                        "quota_scope": "evaluation",
                        "quota_limit": 1,
                        "quota_used": 1,
                        "quota_rejected_count": 0,
                        "status": "enabled",
                        "created_at": "2026-06-30T00:00:00+00:00",
                        "last_used_at": None,
                        "usage_count": 0,
                        "expires_at": None,
                        "revoked_at": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)


    def fail_if_governor_executes(*_args, **_kwargs):
        raise AssertionError("quota must reject before governor execution")

    monkeypatch.setattr(cgt_router, "_resolve_scores", fail_if_governor_executes)

    response = client.post(
        "/cgt/govern",
        headers={
            "X-API-Key": raw_key,
            "X-Request-ID": "usage-quota-exhausted-03",
        },

        json={
            "answer": "This request should be rejected before evaluation.",
            "language": "en",
        },
    )

    assert response.status_code == 429

    payload = response.json()
    assert payload["detail"]["error"] == "quota_exceeded"
    assert payload["detail"]["quota_scope"] == "evaluation"
    assert payload["detail"]["quota_limit"] == 1
    assert payload["detail"]["quota_used"] == 1

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = stored["api_keys"][0]

    assert stored_key["quota_used"] == 1
    assert stored_key["quota_rejected_count"] == 1
    assert stored_key["quota_last_rejected_at"]
    assert stored_key["usage_count"] == 1
    assert stored_key["last_used_at"]

    usage_records = [
        json.loads(line)
        for line in usage_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(usage_records) == 1

    usage_record = usage_records[0]

    assert usage_record["request_id"] == "usage-quota-exhausted-03"
    assert usage_record["client_id"] == "quota-endpoint-client"
    assert usage_record["user_id"] == "quota_endpoint_user"
    assert usage_record["api_key_id"] == "key_exhausted_10b"
    assert usage_record["api_key_prefix"] == "pmk_exhausted..."
    assert usage_record["auth_method"] == "api_key"
    assert usage_record["session_type"] == "api_key"
    assert usage_record["method"] == "POST"
    assert usage_record["endpoint"] == "/cgt/govern"
    assert usage_record["status_code"] == 429
    assert isinstance(usage_record["latency_ms"], float)
    assert raw_key not in json.dumps(usage_record)


def test_full_app_console_static_mount_is_reachable(client):
    response = client.get("/console/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_full_app_docs_are_available_in_non_production_smoke(client):
    docs = client.get("/docs")
    redoc = client.get("/redoc")

    assert docs.status_code == 200
    assert redoc.status_code == 200
    assert "text/html" in docs.headers.get("content-type", "")
    assert "text/html" in redoc.headers.get("content-type", "")


def test_main_keeps_docs_disabled_in_production_boundary():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "processual_api" / "main.py").read_text(encoding="utf-8")

    required_markers = [
        'docs_url="/docs" if not settings.is_production else None',
        'redoc_url="/redoc" if not settings.is_production else None',
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing production docs boundary markers: {missing}"
