import json
from datetime import datetime


def _raw(path):
    return path.read_text(encoding="utf-8")


def test_admin_audit_event_store_writes_safe_success_event(tmp_path):
    from processual_api.admin_audit_log import (
        append_admin_audit_event,
        read_admin_audit_events,
    )

    audit_path = tmp_path / "admin_audit.jsonl"

    event = append_admin_audit_event(
        audit_path=audit_path,
        actor="ops@example.test",
        actor_level="operations_supervisor",
        session_key_id="supsk_ops_123",
        action="supervisor_response_sent",
        target_type="client_request",
        target_id="creq_alpha",
        client_id="client-alpha",
        source="admin_clients_panel",
        result="success",
        safe_note="Supervisor response sent to client timeline.",
        request_path="/settings/admin/client-requests/creq_alpha/supervisor-response",
    )

    assert event["event_id"].startswith("aud_")
    assert datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
    assert event["actor"] == "ops@example.test"
    assert event["actor_level"] == "operations_supervisor"
    assert event["session_key_id"] == "supsk_ops_123"
    assert event["action"] == "supervisor_response_sent"
    assert event["target_type"] == "client_request"
    assert event["target_id"] == "creq_alpha"
    assert event["client_id"] == "client-alpha"
    assert event["source"] == "admin_clients_panel"
    assert event["result"] == "success"
    assert event["safe_note"] == "Supervisor response sent to client timeline."
    assert read_admin_audit_events(audit_path) == [event]


def test_admin_audit_event_store_writes_denied_event(tmp_path):
    from processual_api.admin_audit_log import (
        append_admin_audit_event,
        read_admin_audit_events,
    )

    audit_path = tmp_path / "admin_audit.jsonl"

    event = append_admin_audit_event(
        audit_path=audit_path,
        actor="reviewer@example.test",
        actor_level="review_supervisor",
        session_key_id="supsk_review_123",
        action="supervisor_response_denied",
        target_type="client_request",
        target_id="creq_beta",
        client_id="client-beta",
        source="admin_clients_panel",
        result="denied",
        reason="missing_scope: admin:clients:respond",
        request_path="/settings/admin/client-requests/creq_beta/supervisor-response",
    )

    assert event["result"] == "denied"
    assert event["reason"] == "missing_scope: admin:clients:respond"
    assert read_admin_audit_events(audit_path) == [event]


def test_admin_audit_event_redacts_forbidden_secret_material(tmp_path):
    from processual_api.admin_audit_log import append_admin_audit_event

    audit_path = tmp_path / "admin_audit.jsonl"

    append_admin_audit_event(
        audit_path=audit_path,
        actor="owner@example.test",
        actor_level="owner_supervisor",
        session_key_id="supsk_owner_123",
        action="supervisor_response_draft_saved",
        target_type="client_request",
        target_id="creq_secret",
        client_id="client-secret",
        source="admin_clients_panel",
        result="success",
        safe_note=(
            "Do not leak pmk_live_RAW_API_KEY or "
            "pmk_sup_RAW_SUPERVISOR_KEY or Bearer raw.jwt.token"
        ),
        request_path="/settings/admin/client-requests/creq_secret/response-draft",
        metadata={
            "raw_api_key": "pmk_raw_SECRET",
            "provider_secret": "provider-secret-value",
            "encrypted_key": "encrypted-key-value",
            "headers": {
                "Authorization": "Bearer super-secret-token",
                "Cookie": "session=secret-cookie",
            },
            "nested": [
                "password=secret-password",
                "client_secret=secret-client",
                "jwt=eyJhbGciOiJIUzI1NiJ9.secret.payload",
            ],
        },
    )

    payload = _raw(audit_path)
    parsed = json.loads(payload)

    assert parsed["metadata"]["redacted_fields_count"] >= 3
    assert "pmk_live_RAW_API_KEY" not in payload
    assert "pmk_sup_RAW_SUPERVISOR_KEY" not in payload
    assert "pmk_raw_SECRET" not in payload
    assert "provider-secret-value" not in payload
    assert "encrypted-key-value" not in payload
    assert "super-secret-token" not in payload
    assert "secret-cookie" not in payload
    assert "secret-password" not in payload
    assert "secret-client" not in payload
    assert "eyJhbGciOiJIUzI1NiJ9.secret.payload" not in payload
    assert "provider_secret" not in payload
    assert "encrypted_key" not in payload
    assert "Authorization" not in payload
    assert "Cookie" not in payload



def _audit_route_entry() -> dict:
    return {
        "id": "creq_audit_route",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-05T10:00:00+00:00",
        "updated_at": "2026-07-05T10:00:00+00:00",
        "user_id": "client-audit",
        "client_id": "client-audit",
        "role": "client",
        "request_type": "general_support",
        "request_label": "General support",
        "requested_plan": "enterprise",
        "message": "Please audit these supervisor actions.",
        "status_history": [],
        "supervisor_response_drafts": [
            {
                "draft_id": "rdraft_audit_route",
                "body": "Thanks. We reviewed your request safely.",
                "created_at": "2026-07-05T10:05:00+00:00",
                "updated_at": "2026-07-05T10:05:00+00:00",
                "state": "draft",
                "actor": "reviewer@example.test",
            }
        ],
    }


def _write_audit_route_file(tmp_path):
    import json

    path = tmp_path / "settings_client-audit.json"
    path.write_text(
        json.dumps({"client_requests": [_audit_route_entry()]}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return path


def _patch_audit_route_files(monkeypatch, path) -> None:
    from processual_api.routers import settings as settings_routes

    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_LOG_PATH",
        str(path.parent / "admin_audit.jsonl"),
    )
    monkeypatch.setattr(settings_routes, "_DATA_DIR", path.parent)
    monkeypatch.setattr(settings_routes, "_admin_client_request_raw_files", lambda: [path])


def _audit_route_review_user() -> dict:
    from processual_api.supervision_rbac import REVIEW_SUPERVISOR

    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "reviewer@example.test",
        "supervision_level": REVIEW_SUPERVISOR,
        "session_key_id": "supsk_review_audit",
    }


def _audit_route_ops_user() -> dict:
    from processual_api.supervision_rbac import OPERATIONS_SUPERVISOR

    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "ops@example.test",
        "supervision_level": OPERATIONS_SUPERVISOR,
        "session_key_id": "supsk_ops_audit",
    }


def _audit_route_limited_admin_user() -> dict:
    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "limited@example.test",
        "supervision_level": "limited_supervisor",
        "session_key_id": "supsk_limited_audit",
    }


def test_admin_request_status_route_records_success_and_denied_audit(
    tmp_path,
    monkeypatch,
) -> None:
    import asyncio

    import pytest
    from fastapi import HTTPException

    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.routers import settings as settings_routes

    request_file = _write_audit_route_file(tmp_path)
    _patch_audit_route_files(monkeypatch, request_file)

    reviewed = asyncio.run(
        settings_routes.update_admin_client_request_status(
            "creq_audit_route",
            {"status": "reviewed", "note": "Reviewed safely."},
            current_user=_audit_route_review_user(),
        )
    )
    assert reviewed["status"] == "updated"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.update_admin_client_request_status(
                "creq_audit_route",
                {"status": "approved"},
                current_user=_audit_route_review_user(),
            )
        )
    assert exc.value.status_code == 403

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "admin_client_request_status_updated",
        "admin_client_request_status_denied",
    ]

    success = events[0]
    assert success["actor"] == "reviewer@example.test"
    assert success["actor_level"] == "review_supervisor"
    assert success["session_key_id"] == "supsk_review_audit"
    assert success["target_type"] == "client_request"
    assert success["target_id"] == "creq_audit_route"
    assert success["client_id"] == "client-audit"
    assert success["source"] == "admin_clients_panel"
    assert success["result"] == "success"
    assert success["safe_note"] == "Client request status updated to reviewed."
    assert success["request_path"].endswith("/status")

    denied = events[1]
    assert denied["actor"] == "reviewer@example.test"
    assert denied["actor_level"] == "review_supervisor"
    assert denied["target_id"] == "creq_audit_route"
    assert denied["result"] == "denied"
    assert denied["reason"] == "missing_scope: admin:clients:status_decide"


def test_admin_response_draft_route_records_saved_and_denied_audit(
    tmp_path,
    monkeypatch,
) -> None:
    import asyncio

    import pytest
    from fastapi import HTTPException

    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.routers import settings as settings_routes

    request_file = _write_audit_route_file(tmp_path)
    _patch_audit_route_files(monkeypatch, request_file)

    draft = asyncio.run(
        settings_routes.save_admin_client_request_response_draft(
            "creq_audit_route",
            {"mode": "generate"},
            current_user=_audit_route_review_user(),
        )
    )
    assert draft["status"] == "draft_saved"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.save_admin_client_request_response_draft(
                "creq_audit_route",
                {"mode": "generate"},
                current_user=_audit_route_limited_admin_user(),
            )
        )
    assert exc.value.status_code == 403

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "supervisor_response_draft_saved",
        "supervisor_response_draft_denied",
    ]

    assert events[0]["result"] == "success"
    assert events[0]["actor_level"] == "review_supervisor"
    assert events[0]["target_id"] == "creq_audit_route"
    assert events[0]["client_id"] == "client-audit"
    assert events[0]["safe_note"] == "Supervisor response draft saved."
    assert events[0]["metadata"]["mode"] == "generate"
    assert "body" not in events[0]["metadata"]

    assert events[1]["result"] == "denied"
    assert events[1]["actor"] == "limited@example.test"
    assert events[1]["reason"] == "missing_scope: admin:clients:draft"


def test_admin_supervisor_response_route_records_sent_already_sent_and_denied_audit(
    tmp_path,
    monkeypatch,
) -> None:
    import asyncio

    import pytest
    from fastapi import HTTPException

    from processual_api.admin_audit_log import read_admin_audit_events
    from processual_api.routers import settings as settings_routes

    request_file = _write_audit_route_file(tmp_path)
    _patch_audit_route_files(monkeypatch, request_file)

    sent = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_audit_route",
            {"draft_id": "rdraft_audit_route"},
            current_user=_audit_route_ops_user(),
        )
    )
    assert sent["status"] == "sent"

    already = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_audit_route",
            {"draft_id": "rdraft_audit_route"},
            current_user=_audit_route_ops_user(),
        )
    )
    assert already["status"] == "already_sent"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.send_admin_client_request_supervisor_response(
                "creq_audit_route",
                {"draft_id": "rdraft_audit_route"},
                current_user=_audit_route_review_user(),
            )
        )
    assert exc.value.status_code == 403

    events = read_admin_audit_events(tmp_path / "admin_audit.jsonl")
    assert [event["action"] for event in events] == [
        "supervisor_response_sent",
        "supervisor_response_already_sent",
        "supervisor_response_denied",
    ]

    assert events[0]["result"] == "success"
    assert events[0]["actor"] == "ops@example.test"
    assert events[0]["actor_level"] == "operations_supervisor"
    assert events[0]["target_id"] == "creq_audit_route"
    assert events[0]["client_id"] == "client-audit"
    assert events[0]["metadata"]["draft_id"] == "rdraft_audit_route"

    assert events[1]["result"] == "already_sent"
    assert events[1]["safe_note"] == "Supervisor response already sent for this draft."

    assert events[2]["result"] == "denied"
    assert events[2]["actor"] == "reviewer@example.test"
    assert events[2]["reason"] == "missing_scope: admin:clients:respond"
