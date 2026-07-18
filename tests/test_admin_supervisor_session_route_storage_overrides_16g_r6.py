import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_audit_log import read_admin_audit_events
from processual_api.auth import security
from processual_api.routers import settings as settings_routes
from processual_api.supervision_rbac import OPERATIONS_SUPERVISOR
from processual_api.supervisor_session_keys import (
    SUPERVISOR_SESSION_KEY_PREFIX,
    validate_supervisor_session_key,
)


@pytest.fixture(autouse=True)
def _patch_owner_admin_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security,
        "verify_access_token",
        lambda _token: {
            "sub": "owner@example.test",
            "client_id": "admin",
            "role": "admin",
            "session_type": "ui_admin",
            "scopes": ["admin:settings"],
            "supervision_level": "owner_supervisor",
        },
    )


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, Path]:
    fallback_data = tmp_path / "route_fallback_data"

    monkeypatch.setattr(
        settings_routes,
        "_DATA_DIR",
        fallback_data,
    )

    app = FastAPI()
    app.include_router(settings_routes.router)
    return TestClient(app), fallback_data


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer owner-admin-token"}


def _issue_payload() -> dict[str, str]:
    return {
        "level": OPERATIONS_SUPERVISOR,
        "issued_to": "ops-training@example.test",
        "session_label": "isolated-training-session",
        "reason": "Verify environment-governed storage paths.",
        "expires_at": "",
    }


def test_issue_route_honors_supervisor_session_store_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_store = tmp_path / "isolated" / "supervisor_session_keys.json"
    audit_path = tmp_path / "isolated" / "admin_audit.jsonl"

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(session_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_LOG_PATH",
        str(audit_path),
    )

    client, fallback_data = _client(tmp_path, monkeypatch)

    response = client.post(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
        json=_issue_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    raw_key = payload["raw_key"]

    assert raw_key.startswith(SUPERVISOR_SESSION_KEY_PREFIX)
    assert session_store.exists(), (
        "route ignored PMK_SUPERVISOR_SESSION_KEYS_PATH"
    )
    assert not (
        fallback_data / "supervisor_session_keys.json"
    ).exists()

    persisted_text = session_store.read_text(encoding="utf-8")
    persisted = json.loads(persisted_text)

    assert raw_key not in persisted_text
    assert "key_hash" in persisted["supervisor_session_keys"][0]

    auth_store = security._supervisor_session_key_store_path()
    assert auth_store == session_store

    validated = validate_supervisor_session_key(
        auth_store,
        raw_key,
    )

    assert (
        validated["session_key_id"]
        == payload["record"]["session_key_id"]
    )
    assert validated["level"] == OPERATIONS_SUPERVISOR
    assert "raw_key" not in validated
    assert "key_hash" not in validated

    listed = client.get(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
    )

    assert listed.status_code == 200
    listed_text = json.dumps(listed.json(), sort_keys=True)
    assert raw_key not in listed_text
    assert "raw_key" not in listed_text
    assert "key_hash" not in listed_text


def test_issue_route_honors_admin_audit_log_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_store = tmp_path / "isolated" / "supervisor_session_keys.json"
    audit_path = tmp_path / "isolated" / "admin_audit.jsonl"

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(session_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_LOG_PATH",
        str(audit_path),
    )

    client, fallback_data = _client(tmp_path, monkeypatch)

    response = client.post(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
        json=_issue_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    raw_key = payload["raw_key"]

    assert audit_path.exists(), (
        "route ignored PMK_ADMIN_AUDIT_LOG_PATH"
    )
    assert not (
        fallback_data / "admin_audit.jsonl"
    ).exists()

    audit_text = audit_path.read_text(encoding="utf-8")
    events = read_admin_audit_events(audit_path)

    assert [event["action"] for event in events] == [
        "supervisor_session_key_issued",
    ]
    assert (
        events[0]["target_id"]
        == payload["record"]["session_key_id"]
    )
    assert events[0]["result"] == "success"
    assert raw_key not in audit_text


def test_route_path_helpers_preserve_default_fallback_without_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_data = tmp_path / "default_route_data"

    monkeypatch.delenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        raising=False,
    )
    monkeypatch.delenv(
        "PMK_ADMIN_AUDIT_LOG_PATH",
        raising=False,
    )
    monkeypatch.setattr(
        settings_routes,
        "_DATA_DIR",
        fallback_data,
    )

    assert settings_routes._supervisor_session_key_store_path() == (
        fallback_data / "supervisor_session_keys.json"
    )
    assert settings_routes._admin_audit_path() == (
        fallback_data / "admin_audit.jsonl"
    )
    assert not fallback_data.exists()
