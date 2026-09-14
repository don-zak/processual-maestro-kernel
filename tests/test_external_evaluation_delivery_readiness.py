from __future__ import annotations

import asyncio

import pytest
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
from processual_api.services.evaluation_authority_postgres import verify_evaluation_api_key


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
            f"sqlite+aiosqlite:///{tmp_path / 'evaluation-delivery-authority.db'}"
        )
    )


def _create_grant(*, evaluation_type: str = "standard") -> dict:
    return asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="external-eval-client",
                user_id="external-eval-user",
                issued_to="External Evaluation Team",
                purpose="Governed external product evaluation for delivery readiness",
                evaluation_type=evaluation_type,
                allowed_task_ids=["crm.customer_context"],
                allowed_endpoints=[{"method": "GET", "path": "/health/live"}],
                allowed_scopes=["read:health"],
                max_requests=100,
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
            body=grant_routes.EvaluationKeyIssue(label="External evaluation access"),
            request=_request(
                "POST",
                f"/settings/admin/evaluation-grants/{grant_id}/issue-key",
            ),
            current_user=_admin(),
        )
    )


def test_standard_and_integration_quota_policy(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)

    standard = _create_grant(evaluation_type="standard")
    integration = _create_grant(evaluation_type="integration")

    assert standard["max_requests"] == 100
    assert integration["max_requests"] == 200


def test_key_delivery_metadata_is_safe_and_whatsapp_specific(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant(evaluation_type="integration")
    issued = _issue_key(grant["grant_id"])
    raw_key = issued["api_key"]
    key_id = issued["key"]["key_id"]

    listed = asyncio.run(
        grant_routes.list_evaluation_keys(
            grant_id=grant["grant_id"],
            request=_request(
                "GET",
                f"/settings/admin/evaluation-grants/{grant['grant_id']}/keys",
            ),
            current_user=_admin(),
        )
    )
    assert listed["raw_secret_visible"] is False
    assert listed["keys"][0]["key_id"] == key_id
    assert listed["keys"][0]["evaluation_type"] == "integration"
    assert listed["keys"][0]["quota_limit"] == 200
    assert listed["keys"][0]["delivery_status"] == "not_sent"
    assert raw_key not in str(listed)

    sent = asyncio.run(
        grant_routes.mark_evaluation_key_delivered(
            grant_id=grant["grant_id"],
            key_id=key_id,
            body=grant_routes.EvaluationKeyDelivery(channel="whatsapp"),
            request=_request(
                "POST",
                f"/settings/admin/evaluation-grants/{grant['grant_id']}/keys/{key_id}/delivery",
            ),
            current_user=_admin(),
        )
    )
    assert sent["status"] == "sent"
    assert sent["key"]["delivery_status"] == "sent"
    assert sent["key"]["delivery_channel"] == "whatsapp"
    assert sent["key"]["delivered_at"]
    assert raw_key not in str(sent)


def test_individual_key_revoke_does_not_require_raw_secret(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    grant = _create_grant()
    issued = _issue_key(grant["grant_id"])
    raw_key = issued["api_key"]
    key_id = issued["key"]["key_id"]

    assert asyncio.run(verify_evaluation_api_key(raw_key)) is not None

    revoked = asyncio.run(
        grant_routes.revoke_evaluation_key(
            grant_id=grant["grant_id"],
            key_id=key_id,
            request=_request(
                "DELETE",
                f"/settings/admin/evaluation-grants/{grant['grant_id']}/keys/{key_id}",
            ),
            current_user=_admin(),
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["key"]["key_id"] == key_id
    assert revoked["key"]["status"] == "revoked"
    assert revoked["key"]["raw_secret_visible"] is False
    assert raw_key not in str(revoked)
    assert asyncio.run(verify_evaluation_api_key(raw_key)) is None

    grants = asyncio.run(
        grant_routes.list_evaluation_grants(
            request=_request("GET", "/settings/admin/evaluation-grants"),
            current_user=_admin(),
        )
    )
    matching = next(item for item in grants["grants"] if item["grant_id"] == grant["grant_id"])
    assert matching["status"] == "active"
    assert matching["active_key_count"] == 0
