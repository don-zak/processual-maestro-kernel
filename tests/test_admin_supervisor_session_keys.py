from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from processual_api.supervision_rbac import (
    OPERATIONS_SUPERVISOR,
    OWNER_SUPERVISOR,
    REVIEW_SUPERVISOR,
)
from processual_api.supervisor_session_keys import (
    SUPERVISOR_SESSION_KEY_PREFIX,
    issue_supervisor_session_key,
    list_supervisor_session_keys,
    revoke_supervisor_session_key,
    validate_supervisor_session_key,
)


def _store(tmp_path: Path) -> Path:
    return tmp_path / "supervisor_session_keys.json"


def _owner() -> dict:
    return {
        "email": "owner@example.test",
        "supervision_level": OWNER_SUPERVISOR,
    }


def _ops_payload() -> dict:
    return {
        "issued_to": "ops@example.test",
        "level": OPERATIONS_SUPERVISOR,
        "session_label": "daily-client-supervision",
        "reason": "Handle pending client requests.",
        "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
    }


def test_owner_can_issue_supervisor_session_key_once_visible_raw(tmp_path: Path) -> None:
    store = _store(tmp_path)

    issued = issue_supervisor_session_key(store, _owner(), _ops_payload())

    assert issued["raw_key"].startswith(SUPERVISOR_SESSION_KEY_PREFIX)
    assert issued["record"]["session_key_id"].startswith("supsk_")
    assert issued["record"]["level"] == OPERATIONS_SUPERVISOR
    assert issued["record"]["issued_by"] == "owner@example.test"
    assert issued["record"]["issued_to"] == "ops@example.test"
    assert issued["record"]["session_label"] == "daily-client-supervision"
    assert "admin:clients:respond" in issued["record"]["scopes"]

    rendered_response = repr(issued["record"]).lower()
    assert issued["raw_key"] not in rendered_response
    assert "key_hash" not in issued["record"]

    raw = json.loads(store.read_text(encoding="utf-8"))
    persisted = raw["supervisor_session_keys"][0]
    persisted_rendered = repr(persisted)

    assert persisted["session_key_id"] == issued["record"]["session_key_id"]
    assert persisted["level"] == OPERATIONS_SUPERVISOR
    assert persisted["key_hash"]
    assert issued["raw_key"] not in persisted_rendered
    assert "pmk_sup_" not in persisted_rendered


def test_non_owner_cannot_issue_supervisor_session_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    issuer = {
        "email": "ops@example.test",
        "supervision_level": OPERATIONS_SUPERVISOR,
    }

    with pytest.raises(PermissionError):
        issue_supervisor_session_key(store, issuer, _ops_payload())

    assert not store.exists()


def test_list_supervisor_session_keys_is_safe_and_hides_secret_material(tmp_path: Path) -> None:
    store = _store(tmp_path)
    issued = issue_supervisor_session_key(store, _owner(), _ops_payload())

    listed = list_supervisor_session_keys(store, _owner())

    assert len(listed) == 1
    assert listed[0]["session_key_id"] == issued["record"]["session_key_id"]
    assert "key_hash" not in listed[0]
    assert "raw_key" not in listed[0]

    rendered = repr(listed).lower()
    assert issued["raw_key"].lower() not in rendered
    assert "provider_secret" not in rendered
    assert "encrypted_key" not in rendered
    assert "authorization" not in rendered
    assert "cookie" not in rendered
    assert "jwt" not in rendered


def test_validate_supervisor_session_key_returns_safe_session_and_updates_last_used(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    issued = issue_supervisor_session_key(store, _owner(), _ops_payload())

    validated = validate_supervisor_session_key(store, issued["raw_key"])

    assert validated["session_key_id"] == issued["record"]["session_key_id"]
    assert validated["level"] == OPERATIONS_SUPERVISOR
    assert validated["issued_to"] == "ops@example.test"
    assert "admin:clients:respond" in validated["scopes"]
    assert "key_hash" not in validated
    assert "raw_key" not in validated

    raw = json.loads(store.read_text(encoding="utf-8"))
    persisted = raw["supervisor_session_keys"][0]
    assert persisted["last_used_at"]


def test_revoke_supervisor_session_key_invalidates_validation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    issued = issue_supervisor_session_key(store, _owner(), _ops_payload())

    revoked = revoke_supervisor_session_key(
        store,
        _owner(),
        issued["record"]["session_key_id"],
        reason="rotated by owner",
    )

    assert revoked["revoked_at"]
    assert revoked["revoked_by"] == "owner@example.test"
    assert revoked["revocation_reason"] == "rotated by owner"

    with pytest.raises(PermissionError):
        validate_supervisor_session_key(store, issued["raw_key"])


def test_expired_supervisor_session_key_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = _ops_payload()
    payload["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

    issued = issue_supervisor_session_key(store, _owner(), payload)

    with pytest.raises(PermissionError):
        validate_supervisor_session_key(store, issued["raw_key"])


def test_review_supervisor_key_gets_review_only_scopes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = _ops_payload()
    payload["issued_to"] = "reviewer@example.test"
    payload["level"] = REVIEW_SUPERVISOR

    issued = issue_supervisor_session_key(store, _owner(), payload)

    scopes = set(issued["record"]["scopes"])
    assert "admin:clients:read" in scopes
    assert "admin:clients:draft" in scopes
    assert "admin:clients:status_review" in scopes
    assert "admin:clients:respond" not in scopes
    assert "admin:clients:status_decide" not in scopes
    assert "admin:supervisor_sessions:issue" not in scopes


def test_supervisor_session_store_uses_atomic_replacement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "supervisor_sessions.json"

    actor = {
        "email": "owner@example.test",
        "supervision_level": ("owner_supervisor"),
    }

    issued = issue_supervisor_session_key(
        path,
        actor,
        {
            "level": "operations_supervisor",
            "issued_to": "operator@example.test",
            "session_label": "Atomic storage",
            "reason": "Regression",
            "expires_at": "",
        },
    )

    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    assert issued["record"]["issued_to"] == "operator@example.test"
