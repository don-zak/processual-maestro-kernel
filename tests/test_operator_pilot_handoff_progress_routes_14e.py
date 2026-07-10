"""HTTP route tests for operator pilot handoff progress 14E."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.services.operator_pilot_handoff_actions import (
    build_operator_pilot_handoff_actions_preview,
)
from processual_api.supervision_rbac import (
    OWNER_SUPERVISOR,
    REVIEW_SUPERVISOR,
)
from processual_api.supervisor_session_keys import (
    issue_supervisor_session_key,
    revoke_supervisor_session_key,
)

PROGRESS_ROUTE = "/settings/admin/operator-pilot-handoff/progress"

UPDATE_ROUTE = "/settings/admin/operator-pilot-handoff/progress/actions/{action_id}"

ALLOWED_WRITE_SCOPES = {
    "admin:clients:status_decide",
    "admin:integration_readiness:write",
}


def _first_action_id() -> str:
    action = build_operator_pilot_handoff_actions_preview()["actions"][0]

    return str(action.get("action_id") or action.get("id") or action.get("key"))


def _configure_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    progress_store = tmp_path / "operator-pilot-progress.json"
    session_store = tmp_path / "supervisor-session-keys.json"

    monkeypatch.setenv(
        "PMK_OPERATOR_PILOT_HANDOFF_PROGRESS_PATH",
        str(progress_store),
    )

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(session_store),
    )

    return progress_store, session_store


def _owner_actor() -> dict[str, str]:
    return {
        "email": "owner@example.test",
        "supervision_level": OWNER_SUPERVISOR,
    }


def _issue_key(
    session_store: Path,
    *,
    level: str = OWNER_SUPERVISOR,
    expires_at: str = "",
) -> dict:
    return issue_supervisor_session_key(
        session_store,
        _owner_actor(),
        {
            "level": level,
            "issued_to": "operator-pilot-supervisor@example.test",
            "session_label": "14E route proof",
            "reason": "Safe operator pilot readiness progress",
            "expires_at": expires_at,
        },
    )


def _admin_headers(
    raw_key: str,
    *,
    explicit_scope: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Admin-Supervisor-Session": raw_key,
    }

    if explicit_scope:
        headers["X-Admin-Supervisor-Scope"] = explicit_scope

    return headers


def _canonical_headers(raw_key: str) -> dict[str, str]:
    return {
        "X-Supervisor-Session-Key": raw_key,
    }


def test_14e_progress_get_route_remains_safe_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, _session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    response = TestClient(app).get(PROGRESS_ROUTE)

    assert response.status_code == 200

    payload = response.json()

    assert payload["phase_id"] == "operator-pilot-handoff-progress-14e"
    assert payload["storage"] == "local_json_only"
    assert payload["action_count"] == 12
    assert payload["status_counts"]["pending_operator_input"] == 12

    assert payload["guardrails"]["production_allowed"] is False
    assert payload["guardrails"]["runtime_connector_approved"] is False
    assert payload["guardrails"]["external_http_allowed"] is False
    assert payload["guardrails"]["action_execution_allowed"] is False

    assert not progress_store.exists()


def test_14e_progress_post_requires_supervisor_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, _session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers={
            "X-Admin-Supervisor-Scope": ("admin:integration_readiness:write"),
        },
    )

    assert response.status_code == 403
    assert not progress_store.exists()

    detail = response.json()["detail"]

    assert detail["error"] == "supervisor_session_required"
    assert detail["supervisor_session_present"] is False
    assert detail["supervisor_session_validated"] is False


def test_14e_rejects_invalid_session_even_with_forged_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, _session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_admin_headers(
            "definitely-invalid-session-14e",
            explicit_scope="admin:integration_readiness:write",
        ),
    )

    assert response.status_code == 403
    assert not progress_store.exists()

    detail = response.json()["detail"]

    assert detail["error"] == "invalid_supervisor_session"
    assert detail["supervisor_session_present"] is True
    assert detail["supervisor_session_validated"] is False
    assert detail["provided_scopes"] == []

    assert "definitely-invalid-session-14e" not in json.dumps(detail)


def test_14e_ignores_forged_scope_for_valid_review_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(
        session_store,
        level=REVIEW_SUPERVISOR,
    )

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_admin_headers(
            issued["raw_key"],
            explicit_scope="admin:integration_readiness:write",
        ),
    )

    assert response.status_code == 403
    assert not progress_store.exists()

    detail = response.json()["detail"]

    assert detail["error"] == "supervisor_scope_required"
    assert detail["supervisor_session_validated"] is True
    assert detail["session_key_id"] == (issued["record"]["session_key_id"])

    assert not (set(detail["provided_scopes"]) & ALLOWED_WRITE_SCOPES)


def test_14e_accepts_scopes_derived_from_valid_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 200
    assert response.json()["updated_action"]["status"] == "requested"


def test_14e_accepts_canonical_supervisor_session_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_canonical_headers(issued["raw_key"]),
    )

    assert response.status_code == 200


def test_14e_rejects_revoked_supervisor_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    revoke_supervisor_session_key(
        session_store,
        _owner_actor(),
        issued["record"]["session_key_id"],
        reason="14E revoked session proof",
    )

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 403
    assert not progress_store.exists()
    assert response.json()["detail"]["error"] == "invalid_supervisor_session"


def test_14e_rejects_expired_supervisor_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(
        session_store,
        expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": "requested"},
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 403
    assert not progress_store.exists()
    assert response.json()["detail"]["error"] == "invalid_supervisor_session"


def test_14e_persists_safe_session_id_and_never_raw_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)
    action_id = _first_action_id()

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=action_id),
        json={
            "status": "requested",
            "supervisor_actor": "spoofed-supervisor",
            "note": "Operator documentation requested for review.",
            "safe_reference": "PILOT-14E-R2-001",
        },
        headers=_admin_headers(
            issued["raw_key"],
            explicit_scope="admin:clients:review",
        ),
    )

    assert response.status_code == 200
    assert progress_store.exists()

    payload = response.json()
    updated_action = payload["updated_action"]

    assert updated_action["action_id"] == action_id
    assert updated_action["status"] == "requested"

    assert updated_action["supervisor_actor"] == (issued["record"]["session_key_id"])

    assert updated_action["supervisor_actor"] != ("spoofed-supervisor")

    raw_progress = progress_store.read_text(encoding="utf-8")

    assert issued["raw_key"] not in raw_progress
    assert "spoofed-supervisor" not in raw_progress
    assert issued["record"]["session_key_id"] in raw_progress

    session_payload = json.loads(session_store.read_text(encoding="utf-8"))

    assert session_payload["supervisor_session_keys"][0]["last_used_at"]


@pytest.mark.parametrize(
    "status",
    [
        "approved",
        "production_approved",
        "runtime_enabled",
        "completed",
        "",
    ],
)
def test_14e_progress_post_rejects_unsafe_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={"status": status},
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 422
    assert "unsupported progress status" in response.json()["detail"]


def test_14e_progress_post_rejects_unknown_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id="unknown_action"),
        json={"status": "requested"},
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 422

    assert "unknown operator pilot handoff action" in response.json()["detail"]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("production_allowed", True),
        ("runtime_connector_approved", True),
        ("credentials", "not-allowed"),
        ("endpoint", "not-allowed"),
        ("raw_secret", "not-allowed"),
    ],
)
def test_14e_progress_post_rejects_execution_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    value: object,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={
            "status": "requested",
            field_name: value,
        },
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 422

    assert "unsupported progress update fields" in response.json()["detail"]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("note", "password=unsafe"),
        ("note", "Bearer unsafe-token"),
        ("safe_reference", "https://outside.example/reference"),
        ("safe_reference", "api_key=unsafe"),
    ],
)
def test_14e_progress_post_rejects_secret_or_external_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    value: str,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json={
            "status": "requested",
            field_name: value,
        },
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 422

    assert "prohibited secret or external reference" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        ["requested"],
        "requested",
        123,
        None,
    ],
)
def test_14e_progress_post_requires_json_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    _progress_store, session_store = _configure_paths(
        tmp_path,
        monkeypatch,
    )

    issued = _issue_key(session_store)

    response = TestClient(app).post(
        UPDATE_ROUTE.format(action_id=_first_action_id()),
        json=payload,
        headers=_admin_headers(issued["raw_key"]),
    )

    assert response.status_code == 422

    assert response.json()["detail"] == ("progress update payload must be a JSON object")


def test_14e_progress_routes_reject_unregistered_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_paths(tmp_path, monkeypatch)

    client = TestClient(app)
    action_route = UPDATE_ROUTE.format(action_id=_first_action_id())

    assert client.post(PROGRESS_ROUTE, json={}).status_code == 405
    assert client.put(PROGRESS_ROUTE, json={}).status_code == 405
    assert client.get(action_route).status_code == 405
    assert client.put(action_route, json={}).status_code == 405
    assert client.delete(action_route).status_code == 405


def test_14e_progress_validated_guard_contract_is_visible() -> None:
    source = Path("processual_api/main.py").read_text(encoding="utf-8")

    start_marker = "# PMK OPERATOR PILOT HANDOFF PROGRESS 14E START"

    end_marker = "# PMK OPERATOR PILOT HANDOFF PROGRESS 14E END"

    route_block = source[source.index(start_marker) : source.index(end_marker) + len(end_marker)]

    required = [
        "validate_supervisor_session_key",
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        '"X-Supervisor-Session-Key"',
        '"X-Admin-Supervisor-Session"',
        '"invalid_supervisor_session"',
        '"supervisor_session_validated": True',
        'safe_session.get("session_key_id")',
        "return session_key_id",
        'progress_payload["supervisor_actor"] = supervisor_actor',
    ]

    for marker in required:
        assert marker in route_block

    assert "_pmk13b_request_scopes(request)" not in route_block
    assert "return supervisor_session" not in route_block


def test_14e_progress_route_block_has_no_external_execution() -> None:
    source = Path("processual_api/main.py").read_text(encoding="utf-8")

    start_marker = "# PMK OPERATOR PILOT HANDOFF PROGRESS 14E START"

    end_marker = "# PMK OPERATOR PILOT HANDOFF PROGRESS 14E END"

    route_block = source[source.index(start_marker) : source.index(end_marker) + len(end_marker)]

    forbidden = [
        "requests.get",
        "requests.post",
        "httpx.",
        "urllib.",
        "subprocess",
        "production_allowed=True",
        "runtime_connector_approved=True",
        "automatic_activation_allowed=True",
    ]

    for marker in forbidden:
        assert marker not in route_block
