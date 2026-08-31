from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.routers import cgt_governor as cgt
from processual_api.routers import cgt_governor_external_guard as guard


def _client_for_user(user: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.include_router(cgt.router)
    app.dependency_overrides[get_current_user] = lambda: dict(user)
    return TestClient(app)


def _route_count(path: str, method: str) -> int:
    return sum(
        1
        for route in cgt.router.routes
        if getattr(route, "path", "") == path
        and method in (getattr(route, "methods", set()) or set())
    )


def test_guarded_routes_replace_legacy_registrations_once() -> None:
    for path, method in guard._REPLACED_ROUTES:
        assert _route_count(path, method) == 1


def test_analyze_requires_run_analyze_scope() -> None:
    client = _client_for_user(
        {
            "user_id": "pilot",
            "client_id": "pilot",
            "auth_method": "api_key",
            "scopes": ["run:govern"],
        }
    )

    response = client.post(
        "/cgt/analyze",
        json={"answer": "answer", "client_query": "question"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: run:analyze"


def test_batch_charges_one_pricing_item_per_answer(monkeypatch) -> None:
    observed: dict[str, Any] = {}

    async def fake_consume_quota(
        request: Request,
        current_user: dict[str, Any],
        *,
        item_count: int | None = None,
    ) -> dict[str, Any]:
        observed["item_count"] = item_count
        observed["path"] = request.url.path
        return current_user

    async def fake_batch(req, current_user):
        observed["answers"] = len(req.answers)
        observed["user"] = current_user["user_id"]
        return {"results": [], "count": len(req.answers)}

    monkeypatch.setattr(guard, "_consume_quota", fake_consume_quota)
    monkeypatch.setattr(cgt, "govern_batch", fake_batch)

    client = _client_for_user(
        {
            "user_id": "pilot",
            "client_id": "pilot",
            "auth_method": "api_key",
            "scopes": ["run:govern"],
        }
    )
    response = client.post(
        "/cgt/govern/batch",
        json={
            "answers": [
                {"answer": "a1"},
                {"answer": "a2"},
                {"answer": "a3"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert observed == {
        "item_count": 3,
        "path": "/cgt/govern/batch",
        "answers": 3,
        "user": "pilot",
    }


def test_pilot_scope_cannot_toggle_governor() -> None:
    client = _client_for_user(
        {
            "user_id": "pilot",
            "client_id": "pilot",
            "auth_method": "api_key",
            "scopes": ["run:govern"],
        }
    )

    response = client.post("/cgt/govern/toggle", json={"enabled": False})

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: admin:settings"


def test_admin_scope_can_reach_toggle_handler(monkeypatch) -> None:
    async def fake_toggle(req, current_user):
        return {
            "enabled": req.enabled,
            "actor": current_user["user_id"],
        }

    monkeypatch.setattr(cgt, "governor_toggle", fake_toggle)
    client = _client_for_user(
        {
            "user_id": "admin-user",
            "client_id": "admin-user",
            "auth_method": "api_key",
            "scopes": ["admin:settings"],
        }
    )

    response = client.post("/cgt/govern/toggle", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "actor": "admin-user",
    }


def test_compare_requires_run_compare_scope() -> None:
    client = _client_for_user(
        {
            "user_id": "pilot",
            "client_id": "pilot",
            "auth_method": "api_key",
            "scopes": ["run:govern", "run:analyze"],
        }
    )

    response = client.post(
        "/cgt/govern/compare",
        json={"client_query": "compare this"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing required scope: run:compare"
