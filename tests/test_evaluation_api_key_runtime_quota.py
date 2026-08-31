from __future__ import annotations

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from processual_api.services import api_key_store


API_KEY = "pmk_runtime-quota-regression-key"
USER_ID = "evaluation-user"
CLIENT_ID = "evaluation-client"
GRANT_ID = "grant-runtime-quota"
FUTURE = "2099-01-01T00:00:00+00:00"
SCOPES = ["read:health", "run:analyze"]
TASKS = ["analyze"]
ENDPOINTS = [{"method": "GET", "path": "/health/live"}]


def _pbkdf2_hash(api_key: str, *, iterations: int = 1_000) -> str:
    salt = b"evaluation-quota-test-salt"
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        api_key.encode("utf-8"),
        salt,
        iterations,
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def _governed_payload(
    *,
    grant_limit: int,
    key_limit: int,
    usage_count: int = 0,
) -> dict[str, object]:
    grant = {
        "grant_id": GRANT_ID,
        "status": "active",
        "client_id": CLIENT_ID,
        "allowed_scopes": SCOPES,
        "allowed_task_ids": TASKS,
        "allowed_endpoints": ENDPOINTS,
        "max_requests": grant_limit,
        "expires_at": FUTURE,
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "production_allowed": False,
    }
    key = {
        "id": "key-runtime-quota",
        "prefix": "pmk_runtime",
        "hashed": _pbkdf2_hash(API_KEY),
        "status": "enabled",
        "category": "pilot_client",
        "role": "client",
        "client_id": CLIENT_ID,
        "scopes": SCOPES,
        "allowed_task_ids": TASKS,
        "allowed_endpoints": ENDPOINTS,
        "quota_limit": key_limit,
        "usage_count": usage_count,
        "evaluation_grant_id": GRANT_ID,
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "expires_at": FUTURE,
    }
    return {
        "client_id": CLIENT_ID,
        "evaluation_grants_v1": [grant],
        "api_keys": [key],
    }


def _write_settings(data_dir: Path, payload: dict[str, object]) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"settings_{USER_ID}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _load_key(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["api_keys"][0]


@pytest.mark.parametrize(
    ("grant_limit", "key_limit"),
    [
        (2, 2),
        (5, 2),
        (2, 0),
        (2, -1),
    ],
)
def test_governed_evaluation_key_rejects_request_after_effective_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    grant_limit: int,
    key_limit: int,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(api_key_store, "_DATA_DIR", data_dir)
    settings_path = _write_settings(
        data_dir,
        _governed_payload(
            grant_limit=grant_limit,
            key_limit=key_limit,
        ),
    )
    effective_limit = min(
        grant_limit,
        key_limit if key_limit > 0 else grant_limit,
    )

    for _ in range(effective_limit):
        identity = api_key_store.verify_dynamic_api_key(API_KEY)
        assert identity is not None
        assert identity["evaluation_grant_id"] == GRANT_ID
        assert identity["allowed_endpoints"] == ENDPOINTS
        assert identity["execution_mode"] == "evaluation_runtime"

    assert api_key_store.verify_dynamic_api_key(API_KEY) is None

    key = _load_key(settings_path)
    assert key["usage_count"] == effective_limit
    assert key["quota_rejected_count"] == 1
    assert key["evaluation_grant_state"] == "quota_exhausted"


def test_non_governed_api_key_keeps_existing_usage_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(api_key_store, "_DATA_DIR", data_dir)
    payload = {
        "client_id": CLIENT_ID,
        "api_keys": [
            {
                "id": "ordinary-key",
                "prefix": "pmk_runtime",
                "hashed": _pbkdf2_hash(API_KEY),
                "status": "enabled",
                "category": "client_api",
                "role": "client",
                "client_id": CLIENT_ID,
                "scopes": ["read:health"],
                "quota_limit": 1,
                "usage_count": 7,
                "expires_at": FUTURE,
            }
        ],
    }
    settings_path = _write_settings(data_dir, payload)

    first = api_key_store.verify_dynamic_api_key(API_KEY)
    second = api_key_store.verify_dynamic_api_key(API_KEY)

    assert first is not None
    assert second is not None
    key = _load_key(settings_path)
    assert key["usage_count"] == 9
    assert "quota_rejected_count" not in key


def test_governed_evaluation_cap_is_atomic_under_concurrent_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(api_key_store, "_DATA_DIR", data_dir)
    settings_path = _write_settings(
        data_dir,
        _governed_payload(grant_limit=1, key_limit=1),
    )
    barrier = Barrier(2)

    def authenticate() -> dict[str, object] | None:
        barrier.wait(timeout=5)
        return api_key_store.verify_dynamic_api_key(API_KEY)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: authenticate(), range(2)))

    assert sum(result is not None for result in results) == 1
    assert sum(result is None for result in results) == 1

    key = _load_key(settings_path)
    assert key["usage_count"] == 1
    assert key["quota_rejected_count"] == 1
    assert key["evaluation_grant_state"] == "quota_exhausted"
