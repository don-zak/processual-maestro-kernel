from __future__ import annotations

import pytest
from fastapi import Request

from processual_api.routers import cgt_governor_external_guard as guard


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/cgt/govern",
            "raw_path": b"/cgt/govern",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


@pytest.mark.asyncio
async def test_external_evaluation_does_not_enter_commercial_quota_store(monkeypatch) -> None:
    def commercial_quota_must_not_be_called(scope: str):
        raise AssertionError(f"unexpected commercial quota dependency: {scope}")

    monkeypatch.setattr(guard, "require_quota", commercial_quota_must_not_be_called)
    identity = {
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
    }
    assert await guard._consume_quota(_request(), identity, item_count=100) is identity


def test_non_evaluation_identity_is_not_treated_as_external_evaluation() -> None:
    assert not guard._is_external_evaluation(
        {
            "auth_method": "api_key",
            "entitlement_source": "subscription",
            "subscription_required": True,
        }
    )
