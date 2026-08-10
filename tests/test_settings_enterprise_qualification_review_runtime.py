from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.integrations.enterprise_qualification_drafts import (
    save_qualification_draft,
    submit_qualification_draft,
)
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_enterprise_integration_runtime as runtime
from processual_api.routers.settings_enterprise_integration_runtime import (
    EnterpriseQualificationRevisionRequest,
    get_admin_enterprise_qualification_draft,
    request_admin_enterprise_qualification_revision,
)
from processual_api.supervision_rbac import (
    QUALIFICATION_READ_SCOPE,
    QUALIFICATION_REVIEW_SCOPE,
)


def _scope_id() -> str:
    profile = get_credential_profile("enterprise_core_api_reference")
    for contract_id in profile.adapter_contract_ids:
        contract = get_adapter_contract(contract_id)
        if contract.required_scopes:
            return contract.required_scopes[0]
    raise AssertionError("profile has no required scope")


def _pending_raw() -> dict:
    raw: dict = {"subscription": {"plan_id": "enterprise_core"}}
    save_qualification_draft(
        raw,
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[],
    )
    submit_qualification_draft(raw)
    return raw


def _supervisor(*scopes: str) -> dict:
    return {
        "sub": "supervisor-a",
        "email": "supervisor@example.test",
        "role": "admin",
        "supervision_scopes": list(scopes),
    }


def test_supervisor_qualification_routes_are_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert (
        "/settings/admin/enterprise-integration/qualification-drafts/{user_id}"
        in paths
    )
    assert (
        "/settings/admin/enterprise-integration/qualification-drafts/"
        "{user_id}/request-revision"
        in paths
    )


def test_admin_read_requires_qualification_read_scope(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: _pending_raw())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_admin_enterprise_qualification_draft(
                "client-a",
                _supervisor(),
            )
        )

    assert exc_info.value.status_code == 403


def test_admin_read_returns_safe_pending_draft(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: _pending_raw())

    payload = asyncio.run(
        get_admin_enterprise_qualification_draft(
            "client-a",
            _supervisor(QUALIFICATION_READ_SCOPE),
        )
    )

    assert payload["qualification_draft"]["draft_status"] == "pending_review"
    assert payload["qualification_draft"]["security_controls_approved"] == 0
    assert payload["qualification_review"] is None
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False


def test_admin_read_rejects_unsafe_target_identifier(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: _pending_raw())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_admin_enterprise_qualification_draft(
                "../client-a",
                _supervisor(QUALIFICATION_READ_SCOPE),
            )
        )

    assert exc_info.value.status_code == 400


def test_revision_requires_token_scope_before_supervisor_session(monkeypatch) -> None:
    session_calls = 0

    def fake_session(request, required_scope):
        nonlocal session_calls
        session_calls += 1
        return {"session_validated": True}

    monkeypatch.setattr(runtime, "_require_supervisor_write_session", fake_session)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            request_admin_enterprise_qualification_revision(
                "client-a",
                EnterpriseQualificationRevisionRequest(
                    reason_code="scope_needs_clarification"
                ),
                object(),
                _supervisor(QUALIFICATION_READ_SCOPE),
            )
        )

    assert exc_info.value.status_code == 403
    assert session_calls == 0


def test_revision_requires_validated_supervisor_write_session(monkeypatch) -> None:
    def deny_session(request, required_scope):
        raise HTTPException(status_code=403, detail="session required")

    monkeypatch.setattr(runtime, "_require_supervisor_write_session", deny_session)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            request_admin_enterprise_qualification_revision(
                "client-a",
                EnterpriseQualificationRevisionRequest(
                    reason_code="scope_needs_clarification"
                ),
                object(),
                _supervisor(QUALIFICATION_REVIEW_SCOPE),
            )
        )

    assert exc_info.value.status_code == 403


def test_revision_returns_draft_without_approving_runtime(monkeypatch) -> None:
    raw = _pending_raw()
    saves: list[dict] = []
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(
        settings_router,
        "_save_raw",
        lambda user_id, data: saves.append(dict(data)),
    )
    monkeypatch.setattr(
        runtime,
        "_require_supervisor_write_session",
        lambda request, required_scope: {
            "session_validated": True,
            "session_key_id": "safe-session-id",
        },
    )

    payload = asyncio.run(
        request_admin_enterprise_qualification_revision(
            "client-a",
            EnterpriseQualificationRevisionRequest(
                reason_code="security_evidence_required"
            ),
            object(),
            _supervisor(QUALIFICATION_REVIEW_SCOPE),
        )
    )

    assert len(saves) == 1
    assert payload["status"] == "revision_requested"
    assert payload["qualification_draft"]["draft_status"] == "draft"
    assert payload["qualification_review"]["reason_code"] == (
        "security_evidence_required"
    )
    assert "reviewer_id" not in payload["qualification_review"]
    assert payload["supervisor_session_validated"] is True
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False
