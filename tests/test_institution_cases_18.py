from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.routers import institution_cases_18 as routes
from processual_api.routers import settings as settings_router


CLIENT = {
    "sub": "client-a",
    "user_id": "client-a",
    "client_id": "tenant-a",
    "role": "client",
}


def _storage(monkeypatch):
    store = {}

    def load(_user_id):
        return store.setdefault("raw", {})

    def save(_user_id, raw):
        store["raw"] = raw

    monkeypatch.setattr(settings_router, "_load_raw", load)
    monkeypatch.setattr(settings_router, "_save_raw", save)
    return store


def test_institution_case_routes_are_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }
    assert "/settings/client/integration-cases" in paths
    assert "/settings/client/integration-cases/{case_id}/tasks/{task_id}" in paths
    assert "/settings/client/integration-cases/{case_id}/validate" in paths


def test_create_update_and_validate_camara_case(monkeypatch) -> None:
    _storage(monkeypatch)

    created = asyncio.run(
        routes.create_institution_case(
            routes.InstitutionCaseCreate(integration_track="camara"),
            CLIENT,
        )
    )
    case = created["case"]
    assert created["status"] == "created"
    assert case["case_type"] == "camara_integration_case"
    assert case["progress_percent"] == 0
    assert case["production_allowed"] is False
    assert case["runtime_connector_approved"] is False

    case_id = case["case_id"]
    references = {
        "capability_profile": "capability-profile-v1",
        "consent_reference": "consent-policy-ref-001",
        "sandbox_endpoint": "https://sandbox.example/camara",
        "conformance_evidence": "evidence-pack-ref-001",
    }
    for task_id, reference in references.items():
        updated = asyncio.run(
            routes.update_institution_case_task(
                case_id,
                task_id,
                routes.InstitutionTaskUpdate(
                    status="completed",
                    reference=reference,
                ),
                CLIENT,
            )
        )
        assert updated["status"] == "updated"

    validated = asyncio.run(routes.validate_institution_case(case_id, CLIENT))
    assert validated["status"] == "passed"
    assert validated["blockers"] == []
    assert validated["supervisor_required"] is True
    assert validated["case"]["status"] == "ready_for_review"
    assert validated["case"]["progress_percent"] == 100


def test_completed_task_requires_reference(monkeypatch) -> None:
    _storage(monkeypatch)
    created = asyncio.run(
        routes.create_institution_case(
            routes.InstitutionCaseCreate(integration_track="tmforum"),
            CLIENT,
        )
    )
    case_id = created["case"]["case_id"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.update_institution_case_task(
                case_id,
                "api_version",
                routes.InstitutionTaskUpdate(status="completed", reference=""),
                CLIENT,
            )
        )
    assert exc.value.status_code == 422


def test_raw_secret_markers_are_rejected(monkeypatch) -> None:
    _storage(monkeypatch)
    created = asyncio.run(
        routes.create_institution_case(
            routes.InstitutionCaseCreate(integration_track="operator"),
            CLIENT,
        )
    )
    case_id = created["case"]["case_id"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.update_institution_case_task(
                case_id,
                "oauth_profile",
                routes.InstitutionTaskUpdate(
                    status="in_progress",
                    reference="client_secret=do-not-store",
                ),
                CLIENT,
            )
        )
    assert exc.value.status_code == 422
    assert "Raw secrets" in str(exc.value.detail)


def test_url_task_blocks_invalid_reference(monkeypatch) -> None:
    _storage(monkeypatch)
    created = asyncio.run(
        routes.create_institution_case(
            routes.InstitutionCaseCreate(integration_track="camara"),
            CLIENT,
        )
    )
    case_id = created["case"]["case_id"]

    for task_id, reference in {
        "capability_profile": "capability-profile-v1",
        "consent_reference": "consent-ref",
        "sandbox_endpoint": "not-a-url",
        "conformance_evidence": "evidence-ref",
    }.items():
        asyncio.run(
            routes.update_institution_case_task(
                case_id,
                task_id,
                routes.InstitutionTaskUpdate(status="completed", reference=reference),
                CLIENT,
            )
        )

    result = asyncio.run(routes.validate_institution_case(case_id, CLIENT))
    assert result["status"] == "blocked"
    assert any("valid HTTP(S)" in blocker for blocker in result["blockers"])
