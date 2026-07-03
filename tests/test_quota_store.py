from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from processual_api.services import quota_store


def _api_key_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": "key_1",
        "plan_id": "starter",
        "quota_policy": {
            "id": "manual_override",
            "source": "manual",
            "quotas": {"evaluation": 3},
        },
        "quota_scope": "evaluation",
        "quota_limit": 3,
        "quota_used": 0,
        "quota_rejected_count": 0,
    }
    record.update(overrides)
    return record


def _api_key_user(**overrides: Any) -> dict[str, Any]:
    user = {
        "sub": "user_1",
        "user_id": "user_1",
        "client_id": "client_1",
        "auth_method": "api_key",
        "api_key_id": "key_1",
        "api_key_prefix": "pmk_test",
        "scopes": ["run:govern"],
    }
    user.update(overrides)
    return user


def _write_settings(
    tmp_path: Path,
    key: dict[str, Any],
    *,
    subscription: dict[str, Any] | None = None,
) -> Path:
    path = tmp_path / "settings_owner.json"
    payload = {
        "subscription": subscription or {"plan_id": "starter"},
        "api_keys": [key],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _load_settings(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_non_api_key_user_passes_without_consuming_quota(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(tmp_path, _api_key_record(quota_used=0))

    user = {"sub": "jwt_user", "auth_method": "jwt"}
    result = quota_store.consume_quota(
        user,
        method="POST",
        endpoint="/cgt/govern",
    )

    assert result is user
    assert _load_settings(path)["api_keys"][0]["quota_used"] == 0


def test_non_counted_endpoint_passes_without_consuming_quota(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(tmp_path, _api_key_record(quota_used=0))

    result = quota_store.consume_quota(
        _api_key_user(),
        method="GET",
        endpoint="/adapters/status",
    )

    assert "quota" not in result
    assert _load_settings(path)["api_keys"][0]["quota_used"] == 0


def test_counted_endpoint_increments_quota_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(tmp_path, _api_key_record(quota_limit=3, quota_used=1))

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
    )

    stored_key = _load_settings(path)["api_keys"][0]

    assert stored_key["quota_used"] == 2
    assert stored_key["quota_last_used_at"]
    assert result["quota"] == {
        "scope": "evaluation",
        "plan_id": "starter",
        "limit": 3,
        "used": 2,
        "requested": 1,
        "remaining": 1,
    }


def test_counted_endpoint_normalizes_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(tmp_path, _api_key_record(quota_limit=3, quota_used=0))

    quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern/",
    )

    assert _load_settings(path)["api_keys"][0]["quota_used"] == 1


def test_exhausted_quota_raises_429_and_tracks_rejection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(
        tmp_path,
        _api_key_record(
            quota_limit=2,
            quota_used=2,
            quota_rejected_count=0,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(),
            method="POST",
            endpoint="/cgt/govern",
        )

    stored_key = _load_settings(path)["api_keys"][0]

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "quota_exceeded"
    assert exc.value.detail["quota_limit"] == 2
    assert exc.value.detail["quota_used"] == 2
    assert stored_key["quota_used"] == 2
    assert stored_key["quota_rejected_count"] == 1
    assert stored_key["quota_last_rejected_at"]


def test_unlimited_quota_minus_one_allows_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    path = _write_settings(
        tmp_path,
        _api_key_record(
            quota_limit=-1,
            quota_used=999,
            quota_policy={
                "id": "manual_override",
                "source": "manual",
                "quotas": {"evaluation": -1},
            },
        ),
    )

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
    )

    stored_key = _load_settings(path)["api_keys"][0]

    assert stored_key["quota_used"] == 1000
    assert result["quota"]["limit"] == -1
    assert result["quota"]["remaining"] is None


def test_missing_api_key_id_raises_403(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(api_key_id=None),
            method="POST",
            endpoint="/cgt/govern",
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Missing API key quota identity"


def test_missing_quota_record_raises_403(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    _write_settings(tmp_path, _api_key_record(id="other_key"))

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(api_key_id="key_1"),
            method="POST",
            endpoint="/cgt/govern",
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "API key quota record not found"


def test_manual_override_limit_is_respected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)

    def fail_if_plan_quota_is_used(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("manual override should bypass plan quota lookup")

    monkeypatch.setattr(
        quota_store,
        "quota_limit_for_plan",
        fail_if_plan_quota_is_used,
    )

    path = _write_settings(
        tmp_path,
        _api_key_record(
            quota_limit=5,
            quota_limit_override=5,
            quota_used=4,
            quota_policy={
                "id": "manual_override",
                "source": "manual",
                "quotas": {"evaluation": 5},
            },
        ),
    )

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
    )

    stored_key = _load_settings(path)["api_keys"][0]

    assert stored_key["quota_used"] == 5
    assert result["quota"]["limit"] == 5
    assert result["quota"]["remaining"] == 0


def test_plan_based_quota_refreshes_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        quota_store,
        "resolve_plan_id",
        lambda value: f"resolved-{value}",
    )
    monkeypatch.setattr(
        quota_store,
        "quota_limit_for_plan",
        lambda _plan_id, _scope, _default=50: 7,
    )
    monkeypatch.setattr(
        quota_store,
        "get_plan_policy",
        lambda plan_id: {
            "id": plan_id,
            "source": "plan_store",
            "quotas": {"evaluation": 7},
        },
    )

    path = _write_settings(
        tmp_path,
        _api_key_record(
            plan_id="pro",
            quota_policy={"id": "pro", "source": "plan_store"},
            quota_limit=1,
            quota_used=0,
        ),
    )

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern",
    )

    stored_key = _load_settings(path)["api_keys"][0]

    assert stored_key["plan_id"] == "resolved-pro"
    assert stored_key["quota_limit"] == 7
    assert stored_key["quota_policy"]["id"] == "resolved-pro"
    assert result["quota"]["limit"] == 7
    assert result["quota"]["remaining"] == 6
