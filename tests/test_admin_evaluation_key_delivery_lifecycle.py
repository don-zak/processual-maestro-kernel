from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

from processual_api.db import session as db_session
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.routers import settings_admin_evaluation_key_lifecycle as lifecycle_routes
from processual_api.services import api_key_store
from processual_api.services.evaluation_authority_models import (
    EvaluationAuthorityKey,
    EvaluationAuthorityState,
)
from processual_api.services.evaluation_authority_postgres import verify_evaluation_api_key


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "email": "admin@example.invalid",
        "session_type": "identity_user",
        "session_id": "evaluation-admin-session",
        "scopes": ["admin:api_keys:write"],
    }


def _request(method: str, path: str) -> Request:
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
def _allow_platform_admin(monkeypatch):
    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    monkeypatch.setattr(grant_routes, "require_active_platform_admin", allow)
    monkeypatch.setattr(lifecycle_routes, "require_active_platform_admin", allow)
    yield
    asyncio.run(db_session.close_db())


async def _initialize_database(database_url: str) -> None:
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
    asyncio.run(
        _initialize_database(
            f"sqlite+aiosqlite:///{tmp_path / 'evaluation-authority-lifecycle.db'}"
        )
    )


def _create_grant() -> dict:
    return asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="external-evaluator",
                user_id="external-evaluator",
                issued_to="External Evaluator",
                purpose="Governed external evaluation delivery lifecycle testing",
                allowed_task_ids=["crm.customer_context"],
                allowed_endpoints=[{"method": "GET", "path": "/health/live"}],
                allowed_scopes=["read:health"],
                max_requests=20,
                expires_in_days=14,
            ),
            request=_request("POST", "/settings/admin/evaluation-grants"),
            current_user=_admin(),
        )
    )["grant"]


def _issue_key(grant_id: str) -> dict:
    return asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=grant_id,
            body=grant_routes.EvaluationKeyIssue(label="Lifecycle test key"),
            request=_request(
                "POST",
                f"/settings/admin/evaluation-grants/{grant_id}/issue-key",
            ),
            current_user=_admin(),
        )
    )


def _list_keys(grant_id: str) -> dict:
    return asyncio.run(
        lifecycle_routes.list_evaluation_keys(
            grant_id=grant_id,
            request=_request("GET", f"/settings/admin/evaluation-grants/{grant_id}/keys"),
            current_user=_admin(),
        )
    )


def test_issued_key_is_listed_without_raw_secret(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    issued = _issue_key(grant["grant_id"])

    result = _list_keys(grant["grant_id"])

    assert result["status"] == "ready"
    assert result["raw_secret_visible"] is False
    assert result["production_allowed"] is False
    assert result["key_count"] == 1
    key = result["keys"][0]
    assert key["key_id"] == issued["key"]["key_id"]
    assert key["lifecycle_status"] == "issued"
    assert key["delivered_at"] is None
    assert key["acknowledged_at"] is None
    assert issued["api_key"] not in str(result)


def test_receipt_requires_delivery_confirmation(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    issued = _issue_key(grant["grant_id"])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            lifecycle_routes.acknowledge_evaluation_key_receipt(
                grant_id=grant["grant_id"],
                key_id=issued["key"]["key_id"],
                request=_request("POST", "/acknowledge"),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 409
    assert "delivery" in str(exc.value.detail).lower()


def test_delivery_and_receipt_are_durable_and_idempotent(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    issued = _issue_key(grant["grant_id"])
    key_id = issued["key"]["key_id"]

    first = asyncio.run(
        lifecycle_routes.confirm_evaluation_key_delivery(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request("POST", "/confirm-delivery"),
            current_user=_admin(),
        )
    )
    second = asyncio.run(
        lifecycle_routes.confirm_evaluation_key_delivery(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request("POST", "/confirm-delivery"),
            current_user=_admin(),
        )
    )
    acknowledged = asyncio.run(
        lifecycle_routes.acknowledge_evaluation_key_receipt(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request("POST", "/acknowledge"),
            current_user=_admin(),
        )
    )

    assert first["status"] == "delivery_confirmed"
    assert first["key"]["delivered_at"] == second["key"]["delivered_at"]
    assert first["key"]["delivered_by"] == "admin@example.invalid"
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["key"]["lifecycle_status"] == "acknowledged"
    assert acknowledged["key"]["acknowledged_at"]
    assert acknowledged["key"]["acknowledged_by"] == "admin@example.invalid"

    persisted = _list_keys(grant["grant_id"])["keys"][0]
    assert persisted["lifecycle_status"] == "acknowledged"
    assert persisted["delivered_at"] == first["key"]["delivered_at"]
    assert persisted["acknowledged_at"] == acknowledged["key"]["acknowledged_at"]


def test_individual_revocation_is_immediate_and_does_not_revoke_sibling_key(
    monkeypatch,
    tmp_path,
):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    first = _issue_key(grant["grant_id"])
    second = _issue_key(grant["grant_id"])

    assert asyncio.run(verify_evaluation_api_key(first["api_key"])) is not None
    assert asyncio.run(verify_evaluation_api_key(second["api_key"])) is not None

    revoked = asyncio.run(
        lifecycle_routes.revoke_evaluation_key(
            grant_id=grant["grant_id"],
            key_id=first["key"]["key_id"],
            request=_request("DELETE", "/key"),
            body=lifecycle_routes.EvaluationKeyRevoke(reason="Evaluator access withdrawn"),
            current_user=_admin(),
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["key"]["lifecycle_status"] == "revoked"
    assert revoked["key"]["revoked_by"] == "admin@example.invalid"
    assert revoked["key"]["revocation_reason"] == "Evaluator access withdrawn"
    assert asyncio.run(verify_evaluation_api_key(first["api_key"])) is None
    assert asyncio.run(verify_evaluation_api_key(second["api_key"])) is not None


def test_individual_revocation_is_idempotent(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    issued = _issue_key(grant["grant_id"])
    key_id = issued["key"]["key_id"]

    first = asyncio.run(
        lifecycle_routes.revoke_evaluation_key(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request("DELETE", "/key"),
            body=None,
            current_user=_admin(),
        )
    )
    second = asyncio.run(
        lifecycle_routes.revoke_evaluation_key(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request("DELETE", "/key"),
            body=None,
            current_user=_admin(),
        )
    )

    assert first["key"]["revoked_at"] == second["key"]["revoked_at"]
    assert first["key"]["status"] == "revoked"
    assert second["key"]["status"] == "revoked"


def test_lifecycle_controls_require_platform_admin(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()

    async def deny(current_user: dict, request: Request | None = None) -> dict:
        raise HTTPException(status_code=403, detail="platform admin required")

    monkeypatch.setattr(lifecycle_routes, "require_active_platform_admin", deny)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            lifecycle_routes.list_evaluation_keys(
                grant_id=grant["grant_id"],
                request=_request("GET", "/keys"),
                current_user={"sub": "viewer", "session_type": "identity_user"},
            )
        )

    assert exc.value.status_code == 403
