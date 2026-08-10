from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from processual_api.services import quota_store


def test_missing_api_key_plan_authority_fails_closed(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings_customer.json"
    settings_file.write_text(
        json.dumps(
            {
                "api_keys": [
                    {
                        "id": "key-1",
                        "quota_used": 0,
                    }
                ],
                "subscription": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        quota_store.consume_quota(
            {
                "auth_method": "api_key",
                "api_key_id": "key-1",
            },
            method="POST",
            endpoint="/cgt/govern",
            amount=1,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "API key subscription plan authority is missing."


def test_unknown_api_key_plan_authority_fails_closed(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "settings_customer.json"
    settings_file.write_text(
        json.dumps(
            {
                "api_keys": [
                    {
                        "id": "key-1",
                        "plan_id": "not-a-commercial-plan",
                        "quota_used": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        quota_store.consume_quota(
            {
                "auth_method": "api_key",
                "api_key_id": "key-1",
            },
            method="POST",
            endpoint="/cgt/govern",
            amount=1,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "API key subscription plan is not recognized."
