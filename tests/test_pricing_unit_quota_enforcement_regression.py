from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import processual_api.services.quota_store as quota_store
from processual_api.auth.security import require_quota


def _request(method: str, path: str) -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    })


def _api_key_user() -> dict[str, Any]:
    return {
        "sub": "unit-quota-user",
        "user_id": "unit-quota-user",
        "client_id": "unit-quota-client",
        "role": "service",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "api_key_id": "key_unit_quota",
        "api_key_prefix": "pmk_unit",
        "scopes": ["run:govern"],
    }


def test_require_quota_passes_pricing_units_to_existing_quota_path(monkeypatch):
    captured: list[dict[str, Any]] = []

    def fake_consume_quota(
        current_user: dict[str, Any],
        *,
        method: str,
        endpoint: str,
        quota_scope: str = "evaluation",
        amount: int = 1,
    ) -> dict[str, Any]:
        captured.append({
            "current_user": current_user,
            "method": method,
            "endpoint": endpoint,
            "quota_scope": quota_scope,
            "amount": amount,
        })
        updated = dict(current_user)
        updated["quota"] = {
            "scope": quota_scope,
            "limit": 10,
            "used": amount,
            "requested": amount,
            "remaining": 10 - amount,
        }
        return updated

    monkeypatch.setattr(quota_store, "consume_quota", fake_consume_quota)

    request = _request("POST", "/cgt/govern/auto-repair")
    current_user = _api_key_user()

    dependency = require_quota("evaluation")
    result = asyncio.run(dependency(request, current_user))

    assert len(captured) == 1
    assert captured[0]["method"] == "POST"
    assert captured[0]["endpoint"] == "/cgt/govern/auto-repair"
    assert captured[0]["quota_scope"] == "evaluation"
    assert captured[0]["amount"] == 5

    assert request.state.pricing_units_charged == 5
    assert request.state.pricing_decision.endpoint_class == "governance_evaluation"
    assert result["quota"]["requested"] == 5


def test_require_quota_uses_batch_item_count_when_available(monkeypatch):
    captured: list[int] = []

    def fake_consume_quota(
        current_user: dict[str, Any],
        *,
        method: str,
        endpoint: str,
        quota_scope: str = "evaluation",
        amount: int = 1,
    ) -> dict[str, Any]:
        captured.append(amount)
        return dict(current_user)

    monkeypatch.setattr(quota_store, "consume_quota", fake_consume_quota)

    request = _request("POST", "/cgt/govern/batch")
    request.state.pricing_item_count = 7

    dependency = require_quota("evaluation")
    asyncio.run(dependency(request, _api_key_user()))

    assert captured == [7]
    assert request.state.pricing_units_charged == 7


def test_existing_quota_store_rejects_when_pricing_units_exceed_remaining(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    settings_path = tmp_path / "settings_unit_quota_user.json"
    settings_path.write_text(
        json.dumps({
            "subscription": {"plan": "business"},
            "api_keys": [
                {
                    "id": "key_unit_quota",
                    "prefix": "pmk_unit",
                    "role": "service",
                    "status": "enabled",
                    "quota_policy": {
                        "source": "manual",
                        "quotas": {"evaluation": 5},
                    },
                    "quota_scope": "evaluation",
                    "quota_limit": 5,
                    "quota_limit_override": 5,
                    "quota_used": 1,
                    "quota_rejected_count": 0,
                }
            ],
        }),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(),
            method="POST",
            endpoint="/cgt/govern",
            quota_scope="evaluation",
            amount=5,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "quota_exceeded"
    assert exc.value.detail["quota_limit"] == 5
    assert exc.value.detail["quota_used"] == 1
    assert exc.value.detail["quota_requested"] == 5
    assert exc.value.detail["quota_remaining"] == 4

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = stored["api_keys"][0]
    assert stored_key["quota_used"] == 1
    assert stored_key["quota_rejected_count"] == 1


def test_existing_quota_store_records_requested_units_on_success(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    settings_path = tmp_path / "settings_unit_quota_success_user.json"
    settings_path.write_text(
        json.dumps({
            "subscription": {"plan": "business"},
            "api_keys": [
                {
                    "id": "key_unit_quota",
                    "prefix": "pmk_unit",
                    "role": "service",
                    "status": "enabled",
                    "quota_policy": {
                        "source": "manual",
                        "quotas": {"evaluation": 10},
                    },
                    "quota_scope": "evaluation",
                    "quota_limit": 10,
                    "quota_limit_override": 10,
                    "quota_used": 1,
                    "quota_rejected_count": 0,
                }
            ],
        }),
        encoding="utf-8",
    )

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
        quota_scope="evaluation",
        amount=5,
    )

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = stored["api_keys"][0]

    assert stored_key["quota_used"] == 6
    assert result["quota"]["used"] == 6
    assert result["quota"]["requested"] == 5
    assert result["quota"]["remaining"] == 4
