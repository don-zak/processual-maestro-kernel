from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

from processual_api.db import session as db_session
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.services import api_key_store
from processual_api.services.evaluation_authority_models import (
    EvaluationAuthorityKey,
    EvaluationAuthorityState,
)
from processual_api.services.evaluation_authority_postgres import (
    load_evaluation_authority_state,
    verify_evaluation_api_key,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_task_allowed,
)

EVALUATION_TASKS = [
    "crm.customer_context",
    "support.response_draft",
]
EVALUATION_ENDPOINTS = [
    {"method": "GET", "path": "/health/live"},
    {"method": "POST", "path": "/cgt/govern"},
]


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "client_id": "evaluation-owner",
        "role": "client",
        "session_type": "identity_user",
        "session_id": "evaluation-session",
        "scopes": ["evaluation"],
    }


def _request(method: str, path: str = "/settings/admin/evaluation-grants") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


@pytest.fixture(autouse=True)
def _allow_platform_admin_authority(monkeypatch):
    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    monkeypatch.setattr(grant_routes, "require_active_platform_admin", allow)
    yield
    asyncio.run(db_session.close_db())


async def _initialize_shared_authority_database(database_url: str) -> None:
    await db_session.close_db()
    engine = create_async_engine(database_url, poolclass=NullPool)
    db_session._engine = engine
    db_session._session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: EvaluationAuthorityState.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: EvaluationAuthorityKey.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'evaluation-authority.db'}"
    asyncio.run(_initialize_shared_authority_database(database_url))


def _shared_raw() -> dict[str, Any]:
    return asyncio.run(load_evaluation_authority_state("evaluation-owner"))


def _verify_shared(raw_key: str) -> dict[str, Any] | None:
    return asyncio.run(verify_evaluation_api_key(raw_key))


async def _shared_key_rows_async() -> list[dict[str, Any]]:
    async with db_session.session_scope() as session:
        rows = (
            await session.execute(
                select(EvaluationAuthorityKey).order_by(EvaluationAuthorityKey.created_at)
            )
        ).scalars().all()
        return [
            {
                "key_id": row.key_id,
                "grant_id": row.grant_id,
                "prefix": row.prefix,
                "hashed": row.hashed,
                "status": row.status,
                "usage_count": row.usage_count,
                "quota_rejected_count": row.quota_rejected_count,
                "payload": dict(row.payload or {}),
            }
            for row in rows
        ]


def _shared_key_rows() -> list[dict[str, Any]]:
    return asyncio.run(_shared_key_rows_async())


async def _expand_shared_key_payload_async(key_id: str, task_id: str) -> None:
    async with db_session.session_scope() as session:
        row = await session.get(EvaluationAuthorityKey, key_id)
        assert row is not None
        payload = dict(row.payload or {})
        allowed_task_ids = list(payload.get("allowed_task_ids") or [])
        allowed_task_ids.append(task_id)
        payload["allowed_task_ids"] = allowed_task_ids
        row.payload = payload


def _expand_shared_key_payload(key_id: str, task_id: str) -> None:
    asyncio.run(_expand_shared_key_payload_async(key_id, task_id))


async def _expire_shared_grant_async(grant_id: str) -> None:
    async with db_session.session_scope() as session:
        state = await session.get(EvaluationAuthorityState, "evaluation-owner")
        assert state is not None
        authority = dict(state.authority or {})
        grants = [dict(item) for item in authority.get(EVALUATION_GRANTS_STORAGE_KEY, [])]
        target = next(item for item in grants if item.get("grant_id") == grant_id)
        target["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        authority[EVALUATION_GRANTS_STORAGE_KEY] = grants
        state.authority = authority
        state.updated_at = datetime.now(UTC)


def _expire_shared_grant(grant_id: str) -> None:
    asyncio.run(_expire_shared_grant_async(grant_id))


def _create_grant(
    *,
    max_requests: int = 7,
    expires_in_days: int = 14,
    allowed_task_ids: list[str] | None = None,
    allowed_endpoints: list[dict[str, str]] | None = None,
) -> dict:
    return asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="external-eval-client",
                user_id="external-eval-user",
                issued_to="External Evaluation Team",
                purpose="Governed product evaluation outside subscription onboarding",
                allowed_task_ids=allowed_task_ids or EVALUATION_TASKS,
                allowed_endpoints=allowed_endpoints or EVALUATION_ENDPOINTS,
                allowed_scopes=["read:health", "run:govern"],
                max_requests=max_requests,
                expires_in_days=expires_in_days,
            ),
            request=_request("POST"),
            current_user=_admin(),
        )
    )


def _issue_key(grant_id: str) -> dict:
    return asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=grant_id,
            body=grant_routes.EvaluationKeyIssue(label="Evaluation key"),
            request=_request(
                "POST",
                f"/settings/admin/evaluation-grants/{grant_id}/issue-key",
            ),
            current_user=_admin(),
        )
    )


def test_evaluation_task_catalog_reuses_canonical_catalog() -> None:
    payload = asyncio.run(
        grant_routes.evaluation_task_catalog(
            request=_request("GET", "/settings/admin/evaluation-grants/task-catalog"),
            current_user=_admin(),
        )
    )

    task_ids = {task["task_id"] for task in payload["tasks"]}
    assert payload["selection_authority"] == "integration_task_catalog"
    assert payload["evaluation_key_binding_supported"] is True
    assert payload["subscription_required"] is False
    assert "crm.customer_context" in task_ids
    assert "support.response_draft" in task_ids


def test_create_evaluation_grant_is_subscription_independent_and_safe(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    result = _create_grant(max_requests=25)
    grant = result["grant"]

    assert result["status"] == "created"
    assert grant["grant_id"].startswith("eval_")
    assert grant["status"] == "active"
    assert grant["client_id"] == "external-eval-client"
    assert grant["max_requests"] == 25
    assert grant["subscription_required"] is False
    assert grant["registration_required"] is False
    assert grant["commercial_quota_required"] is False
    assert grant["production_allowed"] is False
    assert grant["approved_by_role"] == "platform_admin"
    assert grant["allowed_task_ids"] == EVALUATION_TASKS
    assert grant["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert grant["task_authority_source"] == "integration_task_catalog"
    assert grant["endpoint_authority_source"] == "canonical_runtime_access_policy"
    assert "crm:read" in grant["task_scope_ids"]
    assert "ticket:read" in grant["task_scope_ids"]
    assert "helpdesk:read" in grant["task_scope_ids"]

    stored = _shared_raw()[EVALUATION_GRANTS_STORAGE_KEY][0]
    assert stored["entitlement_source"] == "admin_evaluation_grant"
    assert stored["subscription_required"] is False
    assert stored["registration_required"] is False
    assert stored["commercial_quota_required"] is False
    assert stored["allowed_task_ids"] == EVALUATION_TASKS
    assert stored["allowed_endpoints"] == EVALUATION_ENDPOINTS


def test_evaluation_grant_rejects_admin_scopes(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            grant_routes.create_evaluation_grant(
                body=grant_routes.EvaluationGrantCreate(
                    client_id="client",
                    issued_to="recipient",
                    purpose="Controlled external evaluation for product qualification",
                    allowed_task_ids=["crm.customer_context"],
                    allowed_endpoints=[{"method": "GET", "path": "/health/live"}],
                    allowed_scopes=["read:health", "admin:dangerous"],
                ),
                request=_request("POST"),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 422


def test_evaluation_grant_rejects_unknown_canonical_task(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc:
        _create_grant(allowed_task_ids=["unknown.root.task"])

    assert exc.value.status_code == 422
    assert "Unknown evaluation task" in str(exc.value.detail)


def test_platform_authority_controls_evaluation_administration(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)

    async def deny(current_user: dict, request: Request | None = None) -> dict:
        raise HTTPException(status_code=403, detail="platform admin required")

    monkeypatch.setattr(grant_routes, "require_active_platform_admin", deny)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            grant_routes.create_evaluation_grant(
                body=grant_routes.EvaluationGrantCreate(
                    client_id="client",
                    issued_to="recipient",
                    purpose="Controlled external evaluation for product qualification",
                    allowed_task_ids=["crm.customer_context"],
                    allowed_endpoints=[{"method": "GET", "path": "/health/live"}],
                    allowed_scopes=["read:health"],
                ),
                request=_request("POST"),
                current_user={
                    "sub": "viewer",
                    "user_id": "viewer",
                    "session_type": "identity_user",
                    "session_id": "viewer-session",
                },
            )
        )

    assert exc.value.status_code == 403


def test_issue_key_binds_grant_tasks_limit_expiry_and_one_time_secret(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant(max_requests=9)["grant"]

    result = _issue_key(grant["grant_id"])

    assert result["status"] == "created"
    assert result["api_key"].startswith("pmk_")
    assert result["visible_once"] is True
    assert result["key"]["evaluation_grant_id"] == grant["grant_id"]
    assert result["key"]["evaluation_request_limit"] == 9
    assert result["key"]["expires_at"] == grant["expires_at"]
    assert result["key"]["subscription_required"] is False
    assert result["key"]["registration_required"] is False
    assert result["key"]["commercial_quota_required"] is False
    assert result["key"]["allowed_task_ids"] == EVALUATION_TASKS
    assert result["key"]["allowed_endpoints"] == EVALUATION_ENDPOINTS

    stored = _shared_key_rows()[0]
    payload = stored["payload"]
    assert stored["grant_id"] == grant["grant_id"]
    assert payload["quota_limit"] == 9
    assert payload["evaluation_request_limit"] == 9
    assert payload["entitlement_source"] == "admin_evaluation_grant"
    assert payload["allowed_task_ids"] == EVALUATION_TASKS
    assert payload["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert payload["task_scope_ids"] == grant["task_scope_ids"]
    assert "plan_id" not in payload
    assert "quota_policy" not in payload
    assert "quota_scope" not in payload
    assert stored["hashed"]
    assert result["api_key"] not in str(payload)


def test_valid_evaluation_key_authenticates_with_task_and_endpoint_authority(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])

    identity = _verify_shared(issued["api_key"])

    assert identity is not None
    assert identity["client_id"] == "external-eval-client"
    assert identity["evaluation_grant_id"] == grant["grant_id"]
    assert identity["entitlement_source"] == "admin_evaluation_grant"
    assert identity["subscription_required"] is False
    assert identity["registration_required"] is False
    assert identity["commercial_quota_required"] is False
    assert identity["allowed_task_ids"] == EVALUATION_TASKS
    assert identity["allowed_endpoints"] == EVALUATION_ENDPOINTS
    assert identity["execution_mode"] == "evaluation_runtime"
    assert identity["real_runtime_execution"] is True
    assert evaluation_task_allowed(identity, "crm.customer_context") is True
    assert evaluation_task_allowed(identity, "billing.account_context") is False


def test_tampered_key_task_expansion_cannot_expand_shared_grant_authority(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant(allowed_task_ids=["crm.customer_context"])["grant"]
    issued = _issue_key(grant["grant_id"])
    key_id = issued["key"]["key_id"]

    _expand_shared_key_payload(key_id, "billing.account_context")
    identity = _verify_shared(issued["api_key"])

    assert identity is not None
    assert identity["allowed_task_ids"] == ["crm.customer_context"]
    assert evaluation_task_allowed(identity, "billing.account_context") is False


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
                expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
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
    stored["allowed_task_ids"] = ["crm.customer_context"]
    stored["allowed_endpoints"] = [{"method": "GET", "path": "/health/live"}]
    stored["task_scope_ids"] = ["crm:read"]
    stored["task_authority_source"] = "integration_task_catalog"
    settings_router._save_raw("evaluation-owner", raw)

    assert api_key_store.verify_dynamic_api_key(created["api_key"]) is None
    saved = settings_router._load_raw("evaluation-owner")
    assert saved["api_keys"][0]["evaluation_grant_state"] == "evaluation_grant_required"


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
                expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
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
    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])
    assert _verify_shared(issued["api_key"]) is not None

    _expire_shared_grant(grant["grant_id"])

    assert _verify_shared(issued["api_key"]) is None


def test_revoke_grant_revokes_all_linked_keys(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()["grant"]
    first = _issue_key(grant["grant_id"])
    second = _issue_key(grant["grant_id"])

    revoked = asyncio.run(
        grant_routes.revoke_evaluation_grant(
            grant_id=grant["grant_id"],
            request=_request(
                "DELETE",
                f"/settings/admin/evaluation-grants/{grant['grant_id']}",
            ),
            current_user=_admin(),
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["revoked_key_count"] == 2
    assert _verify_shared(first["api_key"]) is None
    assert _verify_shared(second["api_key"]) is None
    assert all(row["status"] == "revoked" for row in _shared_key_rows())


def test_issue_key_rejects_inactive_grant(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()["grant"]
    asyncio.run(
        grant_routes.revoke_evaluation_grant(
            grant_id=grant["grant_id"],
            request=_request(
                "DELETE",
                f"/settings/admin/evaluation-grants/{grant['grant_id']}",
            ),
            current_user=_admin(),
        )
    )

    with pytest.raises(HTTPException) as exc:
        _issue_key(grant["grant_id"])

    assert exc.value.status_code == 409
    assert "evaluation_grant_inactive" in str(exc.value.detail)
