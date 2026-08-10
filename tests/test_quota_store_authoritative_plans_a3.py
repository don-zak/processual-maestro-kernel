from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from processual_api.services import quota_store


def _write_settings(tmp_path, *, plan_id: str) -> None:
    payload = {
        "subscription": {"plan_id": plan_id},
        "api_keys": [
            {
                "id": "key-a",
                "quota_used": 0,
            }
        ],
    }
    (tmp_path / "settings_client-a.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _api_key_user() -> dict[str, object]:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "auth_method": "api_key",
        "api_key_id": "key-a",
    }


def test_business_api_key_uses_authoritative_monthly_allowance(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    _write_settings(tmp_path, plan_id="business")

    updated = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
    )

    assert updated["quota"]["plan_id"] == "business"
    assert updated["quota"]["limit"] == 100_000
    assert updated["quota"]["used"] == 1
    persisted = json.loads(
        (tmp_path / "settings_client-a.json").read_text(encoding="utf-8")
    )
    key = persisted["api_keys"][0]
    assert key["plan_id"] == "business"
    assert key["quota_policy"]["source"] == "authoritative_fulfillment_catalog"
    assert key["quota_limit"] == 100_000


def test_unknown_api_key_plan_is_rejected_before_quota_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    _write_settings(tmp_path, plan_id="unknown-commercial-plan")

    with pytest.raises(HTTPException) as exc_info:
        quota_store.consume_quota(
            _api_key_user(),
            method="POST",
            endpoint="/cgt/govern",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "API key subscription plan is not recognized."
    persisted = json.loads(
        (tmp_path / "settings_client-a.json").read_text(encoding="utf-8")
    )
    key = persisted["api_keys"][0]
    assert key["quota_used"] == 0
    assert "quota_limit" not in key
    assert "quota_policy" not in key
