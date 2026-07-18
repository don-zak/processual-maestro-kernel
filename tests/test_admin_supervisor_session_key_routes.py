import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_audit_log import read_admin_audit_events
from processual_api.routers import settings as settings_routes
from processual_api.supervision_rbac import OPERATIONS_SUPERVISOR, REVIEW_SUPERVISOR
from processual_api.supervisor_session_keys import SUPERVISOR_SESSION_KEY_PREFIX


@pytest.fixture(autouse=True)
def _patch_owner_admin_jwt(monkeypatch):
    from processual_api.auth import security

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


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    key_path = tmp_path / "supervisor_session_keys.json"
    audit_path = tmp_path / "admin_audit.jsonl"

    monkeypatch.setattr(
        settings_routes,
        "_supervisor_session_key_store_path",
        lambda: key_path,
        raising=False,
    )
    monkeypatch.setattr(
        settings_routes,
        "_admin_audit_path",
        lambda: audit_path,
        raising=False,
    )

    app = FastAPI()
    app.include_router(settings_routes.router)
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer owner-admin-token"}


def _issue_payload(level: str = OPERATIONS_SUPERVISOR) -> dict:
    return {
        "level": level,
        "issued_to": "ops@example.test",
        "session_label": "ops-browser-session",
        "reason": "Owner issued a supervised browser session.",
        "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
    }


def test_owner_can_issue_supervisor_session_key_once_visible_raw(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
        json=_issue_payload(),
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["status"] == "issued"
    assert payload["raw_key"].startswith(SUPERVISOR_SESSION_KEY_PREFIX)
    assert payload["record"]["session_key_id"].startswith("supsk_")
    assert payload["record"]["level"] == OPERATIONS_SUPERVISOR
    assert payload["record"]["issued_to"] == "ops@example.test"
    assert "admin:clients:respond" in payload["record"]["scopes"]

    rendered = json.dumps(payload).lower()
    assert "key_hash" not in rendered
    assert "provider_secret" not in rendered
    assert "encrypted_key" not in rendered
    assert "authorization" not in rendered
    assert "cookie" not in rendered
    assert "jwt" not in rendered

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "supervisor_session_key_issued",
    ]
    assert events[0]["target_id"] == payload["record"]["session_key_id"]
    assert events[0]["result"] == "success"
    assert payload["raw_key"] not in repr(events)


def test_owner_can_list_supervisor_session_keys_without_secret_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    issued = client.post(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
        json=_issue_payload(REVIEW_SUPERVISOR),
    )
    assert issued.status_code == 201
    raw_key = issued.json()["raw_key"]

    response = client.get(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["supervisor_session_keys"][0]["level"] == REVIEW_SUPERVISOR
    assert payload["supervisor_session_keys"][0]["session_key_id"].startswith(
        "supsk_"
    )

    rendered = json.dumps(payload).lower()
    assert raw_key.lower() not in rendered
    assert "pmk_sup_" not in rendered
    assert "key_hash" not in rendered
    assert "raw_key" not in rendered
    assert "provider_secret" not in rendered
    assert "encrypted_key" not in rendered
    assert "authorization" not in rendered
    assert "cookie" not in rendered
    assert "jwt" not in rendered


def test_owner_can_revoke_supervisor_session_key_and_audit_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    issued = client.post(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
        json=_issue_payload(),
    )
    assert issued.status_code == 201
    session_key_id = issued.json()["record"]["session_key_id"]

    response = client.post(
        f"/settings/admin/supervisor-session-keys/{session_key_id}/revoke",
        headers=_headers(),
        json={"reason": "rotated from admin API Keys page"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "revoked"
    assert payload["record"]["session_key_id"] == session_key_id
    assert payload["record"]["revoked_at"]
    assert payload["record"]["revocation_reason"] == "rotated from admin API Keys page"

    listed = client.get(
        "/settings/admin/supervisor-session-keys",
        headers=_headers(),
    )
    assert listed.status_code == 200
    assert listed.json()["supervisor_session_keys"][0]["revoked_at"]

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "supervisor_session_key_issued",
        "supervisor_session_key_revoked",
    ]
    assert {event["target_id"] for event in events} == {session_key_id}


def test_missing_supervisor_session_key_revoke_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/settings/admin/supervisor-session-keys/supsk_missing/revoke",
        headers=_headers(),
        json={"reason": "missing"},
    )

    assert response.status_code == 404
