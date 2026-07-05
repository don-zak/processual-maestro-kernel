import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.supervision_rbac import OPERATIONS_SUPERVISOR, OWNER_SUPERVISOR, REVIEW_SUPERVISOR
from processual_api.supervisor_session_keys import issue_supervisor_session_key


def _owner_user() -> dict:
    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "owner@example.test",
        "supervision_level": OWNER_SUPERVISOR,
    }


def _admin_token() -> str:
    return "test-admin-token"


@pytest.fixture(autouse=True)
def _patch_admin_jwt(monkeypatch):
    from processual_api.auth import security

    monkeypatch.setattr(
        security,
        "verify_access_token",
        lambda _token: {
            "sub": "admin@example.test",
            "client_id": "admin",
            "role": "admin",
            "session_type": "ui_admin",
            "scopes": ["admin:clients:read"],
        },
    )


def _test_app() -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(current_user: dict = Depends(get_current_user)):
        return current_user

    return TestClient(app)


def _issue_ops_key(path: Path, *, expires_at: str = "") -> dict:
    return issue_supervisor_session_key(
        path,
        _owner_user(),
        {
            "level": OPERATIONS_SUPERVISOR,
            "issued_to": "ops@example.test",
            "session_label": "Ops browser session",
            "reason": "Header validation regression test.",
            "expires_at": expires_at,
        },
    )


def test_supervisor_session_header_enriches_admin_jwt_and_updates_last_used(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.auth import security

    key_path = tmp_path / "supervisor_session_keys.json"
    issued = _issue_ops_key(key_path)
    raw_key = issued["raw_key"]
    session_key_id = issued["record"]["session_key_id"]

    monkeypatch.setattr(
        security,
        "_supervisor_session_key_store_path",
        lambda: key_path,
    )
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: tmp_path / "admin_audit.jsonl",
    )

    client = _test_app()
    response = client.get(
        "/whoami",
        headers={
            "Authorization": f"Bearer {_admin_token()}",
            "X-Supervisor-Session-Key": raw_key,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["role"] == "admin"
    assert payload["auth_method"] == "jwt"
    assert payload["supervision_level"] == OPERATIONS_SUPERVISOR
    assert payload["session_key_id"] == session_key_id
    assert payload["supervisor_session_key_id"] == session_key_id
    assert payload["supervisor_session_validated"] is True
    assert "admin:clients:respond" in payload["supervision_scopes"]
    assert "admin:clients:respond" in payload["scopes"]
    assert raw_key not in json.dumps(payload)

    store = json.loads(key_path.read_text(encoding="utf-8"))
    saved = store["supervisor_session_keys"][0]
    assert saved["last_used_at"]
    assert saved["last_used_at"] != issued["record"].get("last_used_at", "")


def test_invalid_supervisor_session_header_blocks_request_and_records_audit(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.auth import security

    key_path = tmp_path / "supervisor_session_keys.json"
    audit_path = tmp_path / "admin_audit.jsonl"

    monkeypatch.setattr(
        security,
        "_supervisor_session_key_store_path",
        lambda: key_path,
    )
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: audit_path,
    )

    raw_key = "pmk_sup_invalid_secret_material"
    client = _test_app()
    response = client.get(
        "/whoami",
        headers={
            "Authorization": f"Bearer {_admin_token()}",
            "X-Supervisor-Session-Key": raw_key,
        },
    )

    assert response.status_code == 403
    assert "Supervisor session key" in response.json()["detail"]

    events = read_admin_audit_events(audit_path)
    assert len(events) == 1

    event = events[0]
    assert event["action"] == "supervisor_session_key_denied"
    assert event["actor"] == "admin@example.test"
    assert event["actor_level"] == "legacy_admin"
    assert event["target_type"] == "supervisor_session"
    assert event["target_id"] == "unknown"
    assert event["source"] == "auth"
    assert event["result"] == "denied"
    assert event["reason"] == "invalid_supervisor_session_key"
    assert event["request_path"] == "/whoami"

    serialized = json.dumps(event, sort_keys=True)
    assert raw_key not in serialized
    assert "pmk_sup_invalid_secret_material" not in audit_path.read_text(
        encoding="utf-8"
    )


def test_expired_supervisor_session_header_blocks_request_and_records_audit(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.auth import security

    key_path = tmp_path / "supervisor_session_keys.json"
    audit_path = tmp_path / "admin_audit.jsonl"
    expired_at = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    raw_key = _issue_ops_key(key_path, expires_at=expired_at)["raw_key"]

    monkeypatch.setattr(
        security,
        "_supervisor_session_key_store_path",
        lambda: key_path,
    )
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: audit_path,
    )

    client = _test_app()
    response = client.get(
        "/whoami",
        headers={
            "Authorization": f"Bearer {_admin_token()}",
            "X-Supervisor-Session-Key": raw_key,
        },
    )

    assert response.status_code == 403

    events = read_admin_audit_events(audit_path)
    assert len(events) == 1
    assert events[0]["action"] == "supervisor_session_key_denied"
    assert events[0]["reason"] == "expired_supervisor_session_key"


def test_missing_supervisor_session_header_preserves_legacy_admin_jwt(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.auth import security

    audit_path = tmp_path / "admin_audit.jsonl"
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: audit_path,
    )

    client = _test_app()
    response = client.get(
        "/whoami",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "admin"
    assert payload["session_type"] == "ui_admin"
    assert "supervision_level" not in payload
    assert not audit_path.exists()



def _settings_route_app() -> TestClient:
    from processual_api.routers import settings as settings_routes

    app = FastAPI()
    app.include_router(settings_routes.router)
    return TestClient(app)


def _settings_route_entry() -> dict:
    return {
        "id": "creq_header_route",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-05T11:00:00+00:00",
        "updated_at": "2026-07-05T11:00:00+00:00",
        "user_id": "client-header",
        "client_id": "client-header",
        "role": "client",
        "request_type": "general_support",
        "request_label": "General support",
        "requested_plan": "enterprise",
        "message": "Please verify supervisor session header routing.",
        "status_history": [],
        "supervisor_response_drafts": [
            {
                "draft_id": "rdraft_header_route",
                "body": "Thanks. We reviewed your request safely.",
                "created_at": "2026-07-05T11:05:00+00:00",
                "updated_at": "2026-07-05T11:05:00+00:00",
                "state": "draft",
                "actor": "reviewer@example.test",
            }
        ],
    }


def _seed_settings_route_request(tmp_path, monkeypatch) -> None:
    from processual_api.routers import settings as settings_routes

    monkeypatch.setattr(settings_routes, "_DATA_DIR", tmp_path)
    settings_routes._save_raw(
        "client-header",
        {"client_requests": [_settings_route_entry()]},
    )


def _issue_supervisor_key(path: Path, level: str, issued_to: str) -> dict:
    return issue_supervisor_session_key(
        path,
        _owner_user(),
        {
            "level": level,
            "issued_to": issued_to,
            "session_label": f"{level} browser session",
            "reason": "Route integration regression test.",
        },
    )


def _admin_headers(raw_key: str) -> dict:
    return {
        "Authorization": f"Bearer {_admin_token()}",
        "X-Supervisor-Session-Key": raw_key,
    }


def test_review_supervisor_header_can_review_and_draft_but_cannot_decide_or_send(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.auth import security

    key_path = tmp_path / "secrets" / "supervisor_session_keys.json"
    review_key = _issue_supervisor_key(
        key_path,
        REVIEW_SUPERVISOR,
        "reviewer@example.test",
    )["raw_key"]

    monkeypatch.setattr(
        security,
        "_supervisor_session_key_store_path",
        lambda: key_path,
    )
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: tmp_path / "auth_admin_audit.jsonl",
    )
    _seed_settings_route_request(tmp_path, monkeypatch)

    client = _settings_route_app()
    headers = _admin_headers(review_key)

    reviewed = client.post(
        "/settings/admin/client-requests/creq_header_route/status",
        headers=headers,
        json={"status": "reviewed", "note": "Reviewed by header session."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["request"]["status"] == "reviewed"

    approved = client.post(
        "/settings/admin/client-requests/creq_header_route/status",
        headers=headers,
        json={"status": "approved"},
    )
    assert approved.status_code == 403

    drafted = client.post(
        "/settings/admin/client-requests/creq_header_route/response-draft",
        headers=headers,
        json={"mode": "generate"},
    )
    assert drafted.status_code == 200
    assert drafted.json()["status"] == "draft_saved"

    sent = client.post(
        "/settings/admin/client-requests/creq_header_route/supervisor-response",
        headers=headers,
        json={"draft_id": "rdraft_header_route"},
    )
    assert sent.status_code == 403

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    actions = [event["action"] for event in events]
    assert actions == [
        "admin_client_request_status_updated",
        "admin_client_request_status_denied",
        "supervisor_response_draft_saved",
        "supervisor_response_denied",
    ]
    assert {event["actor_level"] for event in events} == {"review_supervisor"}
    assert {event["session_key_id"] for event in events} != {""}


def test_operations_supervisor_header_can_decide_send_and_update_last_used(
    tmp_path,
    monkeypatch,
) -> None:
    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.auth import security

    key_path = tmp_path / "secrets" / "supervisor_session_keys.json"
    issued = _issue_supervisor_key(
        key_path,
        OPERATIONS_SUPERVISOR,
        "ops@example.test",
    )
    ops_key = issued["raw_key"]
    session_key_id = issued["record"]["session_key_id"]

    monkeypatch.setattr(
        security,
        "_supervisor_session_key_store_path",
        lambda: key_path,
    )
    monkeypatch.setattr(
        security,
        "_auth_admin_audit_path",
        lambda: tmp_path / "auth_admin_audit.jsonl",
    )
    _seed_settings_route_request(tmp_path, monkeypatch)

    client = _settings_route_app()
    headers = _admin_headers(ops_key)

    approved = client.post(
        "/settings/admin/client-requests/creq_header_route/status",
        headers=headers,
        json={"status": "approved", "note": "Approved by ops header session."},
    )
    assert approved.status_code == 200
    assert approved.json()["request"]["status"] == "approved"

    sent = client.post(
        "/settings/admin/client-requests/creq_header_route/supervisor-response",
        headers=headers,
        json={"draft_id": "rdraft_header_route"},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "admin_client_request_status_updated",
        "supervisor_response_sent",
    ]
    assert {event["actor_level"] for event in events} == {"operations_supervisor"}
    assert {event["session_key_id"] for event in events} == {session_key_id}

    store = json.loads(key_path.read_text(encoding="utf-8"))
    saved = store["supervisor_session_keys"][0]
    assert saved["last_used_at"]
