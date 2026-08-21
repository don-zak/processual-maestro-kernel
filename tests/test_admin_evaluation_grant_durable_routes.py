from __future__ import annotations

import pytest
from fastapi import HTTPException

from processual_api.routers import settings_admin_evaluation_grants as runtime


def _admin() -> dict:
    return {
        "sub": "admin-1",
        "email": "admin@example.test",
        "role": "owner_admin",
        "scopes": ["admin:*"],
    }


def _body() -> runtime.EvaluationGrantCreate:
    return runtime.EvaluationGrantCreate(
        client_id="client-1",
        issued_to="Evaluation Customer",
        purpose="Durable route qualification proof",
        allowed_task_ids=["task.one"],
        allowed_scopes=["read:health"],
        max_requests=25,
        expires_in_days=7,
    )


def _forbid_settings_json(*_args, **_kwargs):
    raise AssertionError("durable evaluation authority must not use Settings JSON")


@pytest.mark.asyncio
async def test_create_uses_durable_authority_without_settings_json(monkeypatch) -> None:
    captured: dict = {}

    async def create_stub(**kwargs):
        captured.update(kwargs)
        return {
            "grant_id": "eval_durable",
            "status": "active",
            "subscription_required": False,
            "production_allowed": False,
        }

    monkeypatch.setattr(runtime, "durable_evaluation_authority_enabled", lambda: True)
    monkeypatch.setattr(runtime, "_task_selection", lambda _ids: (["task.one"], ["scope.one"]))
    monkeypatch.setattr(runtime, "create_durable_evaluation_grant", create_stub)
    monkeypatch.setattr(runtime.settings_module, "_load_raw", _forbid_settings_json)
    monkeypatch.setattr(runtime.settings_module, "_save_raw", _forbid_settings_json)

    result = await runtime.create_evaluation_grant(_body(), current_user=_admin())

    assert result["grant"]["grant_id"] == "eval_durable"
    assert captured["owner_user_ref"] == "admin-1"
    assert captured["client_ref"] == "client-1"
    assert captured["task_scope_ids"] == ["scope.one"]


@pytest.mark.asyncio
async def test_list_uses_durable_authority_without_settings_json(monkeypatch) -> None:
    async def list_stub(**kwargs):
        assert kwargs["owner_user_ref"] == "admin-1"
        return [{"grant_id": "eval_durable", "active_key_count": 1}]

    monkeypatch.setattr(runtime, "durable_evaluation_authority_enabled", lambda: True)
    monkeypatch.setattr(runtime, "list_durable_evaluation_grants", list_stub)
    monkeypatch.setattr(runtime.settings_module, "_load_raw", _forbid_settings_json)

    result = await runtime.list_evaluation_grants(current_user=_admin())

    assert result["grant_count"] == 1
    assert result["authority_source"] == "evaluation_grant_authority"


@pytest.mark.asyncio
async def test_issue_returns_visible_once_secret_without_settings_json(monkeypatch) -> None:
    async def issue_stub(**kwargs):
        assert kwargs["grant_ref"] == "eval_durable"
        assert kwargs["owner_user_ref"] == "admin-1"
        return (
            {
                "key_id": "evalkey_durable",
                "evaluation_grant_id": "eval_durable",
                "raw_secret_visible": False,
                "subscription_required": False,
                "production_allowed": False,
            },
            "pmk_visible_once",
        )

    monkeypatch.setattr(runtime, "durable_evaluation_authority_enabled", lambda: True)
    monkeypatch.setattr(runtime, "issue_durable_evaluation_key", issue_stub)
    monkeypatch.setattr(runtime.settings_module, "_load_raw", _forbid_settings_json)
    monkeypatch.setattr(runtime.settings_module, "_save_raw", _forbid_settings_json)

    result = await runtime.issue_evaluation_key(
        "eval_durable",
        runtime.EvaluationKeyIssue(label="Evaluation key"),
        current_user=_admin(),
    )

    assert result["api_key"] == "pmk_visible_once"
    assert result["visible_once"] is True
    assert result["key"]["raw_secret_visible"] is False


@pytest.mark.asyncio
async def test_revoke_uses_durable_authority_without_settings_json(monkeypatch) -> None:
    async def revoke_stub(**kwargs):
        assert kwargs == {
            "grant_ref": "eval_durable",
            "owner_user_ref": "admin-1",
        }
        return {
            "status": "revoked",
            "grant_id": "eval_durable",
            "revoked_key_count": 2,
        }

    monkeypatch.setattr(runtime, "durable_evaluation_authority_enabled", lambda: True)
    monkeypatch.setattr(runtime, "revoke_durable_evaluation_grant", revoke_stub)
    monkeypatch.setattr(runtime.settings_module, "_load_raw", _forbid_settings_json)
    monkeypatch.setattr(runtime.settings_module, "_save_raw", _forbid_settings_json)

    result = await runtime.revoke_evaluation_grant(
        "eval_durable",
        current_user=_admin(),
    )

    assert result["status"] == "revoked"
    assert result["revoked_key_count"] == 2


@pytest.mark.asyncio
async def test_durable_failure_does_not_fallback_to_settings_json(monkeypatch) -> None:
    async def issue_stub(**_kwargs):
        raise runtime.EvaluationGrantProvisioningError("evaluation_grant_inactive")

    monkeypatch.setattr(runtime, "durable_evaluation_authority_enabled", lambda: True)
    monkeypatch.setattr(runtime, "issue_durable_evaluation_key", issue_stub)
    monkeypatch.setattr(runtime.settings_module, "_load_raw", _forbid_settings_json)

    with pytest.raises(HTTPException) as exc:
        await runtime.issue_evaluation_key(
            "eval_durable",
            runtime.EvaluationKeyIssue(label="Evaluation key"),
            current_user=_admin(),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "evaluation_grant_inactive"
