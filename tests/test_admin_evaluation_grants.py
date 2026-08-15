from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.services import api_key_store
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_endpoint_allowed,
    evaluation_task_allowed,
)

EVALUATION_TASKS = [
    "crm.customer_context",
    "support.response_draft",
]
EVALUATION_ENDPOINTS = [
    {"method": "GET", "path": "/adapters/status"},
]
EVALUATION_SCOPES = ["read:adapters", "run:govern"]


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "client_id": "evaluation-owner",
        "role": "security_admin",
        "session_type": "ui_admin",
        "scopes": ["admin:api_keys:write"],
    }


def _allow_super_admin_business_logic(monkeypatch) -> None:
    async def _allow(_current_user: dict) -> None:
        return None

    monkeypatch.setattr(
        grant_routes,
        "require_active_platform_admin",
        _allow,
    )


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 18080),
            "root_path": "",
        }
    )


def _endpoint_models(
    allowed_endpoints: list[dict[str, str]] | None = None,
) -> list[grant_routes.EvaluationEndpointSelection]:
    return [
        grant_routes.EvaluationEndpointSelection(**item)
        for item in (allowed_endpoints or EVALUATION_ENDPOINTS)
    ]


def _create_grant(
    *,
    max_requests: int = 7,
    expires_in_days: int = 14,
    allowed_task_ids: list[str] | None = None,
    allowed_endpoints: list[dict[str, str]] | None = None,
    allowed_scopes: list[str] | None = None,
) -> dict:
    return asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="external-eval-client",
                user_id="external-eval-user",
                issued_to="External Evaluation Team",
                purpose=(
                    "Governed product evaluation outside subscription onboarding"
                ),
                allowed_task_ids=allowed_task_ids or EVALUATION_TASKS,
                allowed_endpoints=_endpoint_models(allowed_endpoints),
                allowed_scopes=allowed_scopes or EVALUATION_SCOPES,
                max_requests=max_requests,
                expires_in_days=expires_in_days,
            ),
            current_user=_admin(),
        )
    )


def _issue_key(grant_id: str) -> dict:
    return asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=grant_id,
            body=grant_routes.EvaluationKeyIssue(label="Evaluation key"),
            current_user=_admin(),
        )
    )


def test_evaluation_task_catalog_reuses_canonical_catalog(monkeypatch) -> None:
    _allow_super_admin_business_logic(monkeypatch)
    payload = asyncio.run(
        grant_routes.evaluation_task_catalog(current_user=_admin())
    )

    task_ids = {task["task_id"] for task in payload["tasks"]}
    assert payload["selection_authority"] == "integration_task_catalog"
    assert payload["evaluation_key_binding_supported"] is True
    assert payload["subscription_required"] is False
    assert "crm.customer_context" in task_ids
    assert "support.response_draft" in task_ids


def test_create_evaluation_grant_is_subscription_independent_and_runtime_bounded(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    result = _create_grant(max_requests=25)
    grant = result["grant"]

    assert result["status"] == "created"
    assert grant["grant_id"].startswith("eval_")
    assert grant["status"] == "active"
    assert grant["client_id"] == "external-eval-client"
    assert grant["max_requests"] == 25
    assert grant["subscription_required"] is False
    assert grant["execution_mode"] == "evaluation_runtime"
    assert grant["real_runtime_execution"] is True
    assert grant["production_allowed"] is False
    assert grant["approved_by_role"] == "platform_admin"
    assert grant["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert grant["endpoint_authority_source"] == "canonical_runtime_access_policy"
    assert grant["allowed_task_ids"] == EVALUATION_TASKS
    assert grant["task_authority_source"] == "integration_task_catalog"
    assert "crm:read" in grant["task_scope_ids"]
    assert "ticket:read" in grant["task_scope_ids"]
    assert "helpdesk:read" in grant["task_scope_ids"]

    raw = settings_router._load_raw("evaluation-owner")
    stored = raw[EVALUATION_GRANTS_STORAGE_KEY][0]
    assert stored["entitlement_source"] == "admin_evaluation_grant"
    assert stored["subscription_required"] is False
    assert stored["execution_mode"] == "evaluation_runtime"
    assert stored["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert stored["allowed_task_ids"] == EVALUATION_TASKS


def test_evaluation_grant_rejects_admin_scopes(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            grant_routes.create_evaluation_grant(
                body=grant_routes.EvaluationGrantCreate(
                    client_id="client",
                    issued_to="recipient",
                    purpose=(
                        "Controlled external evaluation for product qualification"
                    ),
                    allowed_task_ids=["crm.customer_context"],
                    allowed_endpoints=_endpoint_models(
                        [{"method": "GET", "path": "/health/live"}]
                    ),
                    allowed_scopes=["read:health", "admin:dangerous"],
                ),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 422


def test_evaluation_grant_rejects_non_grantable_control_plane_endpoint(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        _create_grant(
            allowed_endpoints=[
                {"method": "GET", "path": "/settings/admin/evaluation-grants"}
            ],
            allowed_scopes=["read:adapters"],
        )

    assert exc.value.status_code == 422
    assert "not eligible for evaluation access" in str(exc.value.detail)


def test_evaluation_grant_rejects_endpoint_scope_mismatch(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        _create_grant(
            allowed_endpoints=[{"method": "GET", "path": "/adapters/status"}],
            allowed_scopes=["read:health"],
        )

    assert exc.value.status_code == 422
    assert "scope derivation mismatch" in str(exc.value.detail)


def test_evaluation_grant_rejects_unknown_canonical_task(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        _create_grant(allowed_task_ids=["unknown.root.task"])

    assert exc.value.status_code == 422
    assert "Unknown evaluation task" in str(exc.value.detail)


def test_legacy_admin_cannot_create_evaluation_grant(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            grant_routes.create_evaluation_grant(
                body=grant_routes.EvaluationGrantCreate(
                    client_id="client",
                    issued_to="recipient",
                    purpose=(
                        "Controlled external evaluation for product qualification"
                    ),
                    allowed_task_ids=["crm.customer_context"],
                    allowed_endpoints=_endpoint_models(
                        [{"method": "GET", "path": "/health/live"}]
                    ),
                    allowed_scopes=["read:health"],
                ),
                current_user={
                    "sub": "legacy-security-admin",
                    "user_id": "legacy-security-admin",
                    "role": "security_admin",
                    "session_type": "ui_admin",
                    "scopes": ["*", "admin:api_keys:write"],
                },
            )
        )

    assert exc.value.status_code == 403
    assert "super-administrator" in str(exc.value.detail).lower()


def test_issue_key_binds_endpoints_tasks_quota_expiry_and_one_time_secret(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant(max_requests=9)["grant"]

    result = _issue_key(grant["grant_id"])

    assert result["status"] == "created"
    assert result["api_key"].startswith("pmk_")
    assert result["visible_once"] is True
    assert result["key"]["evaluation_grant_id"] == grant["grant_id"]
    assert result["key"]["execution_mode"] == "evaluation_runtime"
    assert result["key"]["real_runtime_execution"] is True
    assert result["key"]["production_allowed"] is False
    assert result["key"]["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert result["key"]["quota_limit"] == 9
    assert result["key"]["expires_at"] == grant["expires_at"]
    assert result["key"]["subscription_required"] is False
    assert result["key"]["allowed_task_ids"] == EVALUATION_TASKS
    assert result["key"]["task_authority_source"] == "integration_task_catalog"

    raw = settings_router._load_raw("evaluation-owner")
    stored = raw["api_keys"][0]
    assert stored["evaluation_grant_id"] == grant["grant_id"]
    assert stored["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert stored["endpoint_authority_source"] == "canonical_runtime_access_policy"
    assert stored["quota_limit_override"] == 9
    assert stored["entitlement_source"] == "admin_evaluation_grant"
    assert stored["allowed_task_ids"] == EVALUATION_TASKS
    assert stored["task_scope_ids"] == grant["task_scope_ids"]
    assert stored["hashed"]
    assert "api_key" not in stored


def test_valid_evaluation_key_authenticates_with_endpoint_and_task_authority(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])

    identity = api_key_store.verify_dynamic_api_key(issued["api_key"])

    assert identity is not None
    assert identity["client_id"] == "external-eval-client"
    assert identity["evaluation_grant_id"] == grant["grant_id"]
    assert identity["entitlement_source"] == "admin_evaluation_grant"
    assert identity["subscription_required"] is False
    assert identity["execution_mode"] == "evaluation_runtime"
    assert identity["real_runtime_execution"] is True
    assert identity["production_allowed"] is False
    assert identity["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert evaluation_endpoint_allowed(
        identity,
        method="GET",
        path="/adapters/status",
    ) is True
    assert evaluation_endpoint_allowed(
        identity,
        method="GET",
        path="/health/live",
    ) is False
    assert identity["allowed_task_ids"] == EVALUATION_TASKS
    assert identity["task_authority_source"] == "integration_task_catalog"
    assert evaluation_task_allowed(identity, "crm.customer_context") is True
    assert evaluation_task_allowed(identity, "billing.account_context") is False


def test_authentication_boundary_allows_selected_runtime_endpoint(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])

    identity = asyncio.run(
        security.get_current_user(
            request=_request("GET", "/adapters/status"),
            bearer=None,
            api_key=issued["api_key"],
            supervisor_session_key=None,
        )
    )

    assert identity["evaluation_grant_id"] == grant["grant_id"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/health/live"),
        ("GET", "/settings/admin/evaluation-grants"),
        ("POST", "/auth/session/refresh"),
    ],
)
def test_authentication_boundary_denies_unselected_or_control_plane_endpoint(
    monkeypatch,
    tmp_path,
    method,
    path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            security.get_current_user(
                request=_request(method, path),
                bearer=None,
                api_key=issued["api_key"],
                supervisor_session_key=None,
            )
        )

    assert exc.value.status_code == 403
    assert "does not allow this runtime endpoint" in str(exc.value.detail)


def test_tampered_key_endpoint_expansion_is_fail_closed(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])

    raw = settings_router._load_raw("evaluation-owner")
    raw["api_keys"][0]["allowed_endpoints"].append(
        {"method": "GET", "path": "/health/live"}
    )
    settings_router._save_raw("evaluation-owner", raw)

    assert api_key_store.verify_dynamic_api_key(issued["api_key"]) is None
    saved = settings_router._load_raw("evaluation-owner")
    assert (
        saved["api_keys"][0]["evaluation_grant_state"]
        == "evaluation_grant_endpoint_mismatch"
    )


def test_tampered_key_task_expansion_is_fail_closed(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant(allowed_task_ids=["crm.customer_context"])["grant"]
    issued = _issue_key(grant["grant_id"])

    raw = settings_router._load_raw("evaluation-owner")
    raw["api_keys"][0]["allowed_task_ids"].append("billing.account_context")
    settings_router._save_raw("evaluation-owner", raw)

    assert api_key_store.verify_dynamic_api_key(issued["api_key"]) is None
    saved = settings_router._load_raw("evaluation-owner")
    assert (
        saved["api_keys"][0]["evaluation_grant_state"]
        == "evaluation_grant_task_mismatch"
    )


def test_governed_evaluation_key_without_grant_is_fail_closed(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    created = asyncio.run(
        settings_router.create_api_key(
            body=settings_router.ApiKeyCreateRequest(
                category="pilot_client",
                client_id="governed-evaluation-client",
                user_id="governed-evaluation-user",
                scopes=["read:health"],
                quota_limit_override=5,
                expires_at=(
                    datetime.now(UTC) + timedelta(days=7)
                ).isoformat(),
                purpose="Governed evaluation key missing its required grant",
                issued_to="governed-evaluation-recipient",
            ),
            current_user=_admin(),
        )
    )

    raw = settings_router._load_raw("evaluation-owner")
    stored = raw["api_keys"][0]
    stored["entitlement_source"] = "admin_evaluation_grant"
    stored["subscription_required"] = False
    stored["allowed_endpoints"] = EVALUATION_ENDPOINTS
    stored["allowed_task_ids"] = ["crm.customer_context"]
    stored["task_scope_ids"] = ["crm:read"]
    stored["task_authority_source"] = "integration_task_catalog"
    settings_router._save_raw("evaluation-owner", raw)

    assert api_key_store.verify_dynamic_api_key(created["api_key"]) is None
    saved = settings_router._load_raw("evaluation-owner")
    assert (
        saved["api_keys"][0]["evaluation_grant_state"]
        == "evaluation_grant_required"
    )


def test_legacy_unmarked_pilot_key_remains_backward_compatible(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    created = asyncio.run(
        settings_router.create_api_key(
            body=settings_router.ApiKeyCreateRequest(
                category="pilot_client",
                client_id="legacy-pilot-client",
                user_id="legacy-pilot-user",
                scopes=["read:health"],
                quota_limit_override=5,
                expires_at=(
                    datetime.now(UTC) + timedelta(days=7)
                ).isoformat(),
                purpose="Historical pilot compatibility regression",
                issued_to="legacy-pilot",
            ),
            current_user=_admin(),
        )
    )

    identity = api_key_store.verify_dynamic_api_key(created["api_key"])
    assert identity is not None
    raw = settings_router._load_raw("evaluation-owner")
    assert raw["api_keys"][0]["evaluation_grant_state"] in {
        "legacy_pilot_compatible",
        "active",
    }


def test_expired_grant_stops_previously_valid_key(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])
    assert api_key_store.verify_dynamic_api_key(issued["api_key"]) is not None

    raw = settings_router._load_raw("evaluation-owner")
    raw[EVALUATION_GRANTS_STORAGE_KEY][0]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    settings_router._save_raw("evaluation-owner", raw)

    assert api_key_store.verify_dynamic_api_key(issued["api_key"]) is None


def test_revoke_grant_revokes_all_linked_keys(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    first = _issue_key(grant["grant_id"])
    second = _issue_key(grant["grant_id"])

    revoked = asyncio.run(
        grant_routes.revoke_evaluation_grant(
            grant_id=grant["grant_id"],
            current_user=_admin(),
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["revoked_key_count"] == 2
    assert api_key_store.verify_dynamic_api_key(first["api_key"]) is None
    assert api_key_store.verify_dynamic_api_key(second["api_key"]) is None

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            security.get_current_user(
                request=_request("GET", "/adapters/status"),
                bearer=None,
                api_key=first["api_key"],
                supervisor_session_key=None,
            )
        )
    assert exc.value.status_code == 401

    raw = settings_router._load_raw("evaluation-owner")
    assert all(key["status"] == "revoked" for key in raw["api_keys"])


def test_issue_key_rejects_inactive_grant(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)
    grant = _create_grant()["grant"]
    asyncio.run(
        grant_routes.revoke_evaluation_grant(
            grant_id=grant["grant_id"],
            current_user=_admin(),
        )
    )

    with pytest.raises(HTTPException) as exc:
        _issue_key(grant["grant_id"])

    assert exc.value.status_code == 409
    assert "evaluation_grant_inactive" in str(exc.value.detail)
