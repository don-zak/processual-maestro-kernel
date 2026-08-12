from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from processual_api.auth import security as security_mod


def test_supervisor_paths_use_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", raising=False)
    monkeypatch.delenv("PMK_ADMIN_AUDIT_LOG_PATH", raising=False)

    assert security_mod._supervisor_session_key_store_path() == Path("data/supervisor_session_keys.json")
    assert security_mod._auth_admin_audit_path() == Path("data/admin_audit.jsonl")

    monkeypatch.setenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", " /tmp/session-keys.json ")
    monkeypatch.setenv("PMK_ADMIN_AUDIT_LOG_PATH", " /tmp/admin-audit.jsonl ")

    assert security_mod._supervisor_session_key_store_path() == Path("/tmp/session-keys.json")
    assert security_mod._auth_admin_audit_path() == Path("/tmp/admin-audit.jsonl")


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        ({"supervision_level": "platform"}, "platform"),
        ({"supervisor_level": "tenant"}, "tenant"),
        ({}, "legacy_admin"),
    ],
)
def test_supervisor_actor_level_for_audit_fallbacks(user: dict, expected: str) -> None:
    assert security_mod._supervisor_actor_level_for_audit(user) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Session key expired", "expired_supervisor_session_key"),
        ("SESSION KEY REVOKED", "revoked_supervisor_session_key"),
        ("signature mismatch", "invalid_supervisor_session_key"),
    ],
)
def test_supervisor_session_key_denial_reason(message: str, expected: str) -> None:
    assert security_mod._supervisor_session_key_denial_reason(PermissionError(message)) == expected


def test_merge_supervisor_session_user_merges_scopes_and_optional_metadata() -> None:
    user = {
        "sub": "admin-1",
        "scopes": ["read", "", None, "shared"],
        "unchanged": "value",
    }
    session = {
        "session_key_id": "ssk-1",
        "level": "platform",
        "scopes": ["write", "shared", " "],
        "issued_to": "ops@example.com",
        "session_label": "incident-room",
    }

    merged = security_mod._merge_supervisor_session_user(user, session)

    assert merged is not user
    assert user["scopes"] == ["read", "", None, "shared"]
    assert merged["unchanged"] == "value"
    assert merged["supervision_level"] == "platform"
    assert merged["session_key_id"] == "ssk-1"
    assert merged["supervisor_session_key_id"] == "ssk-1"
    assert merged["supervisor_session_validated"] is True
    assert merged["supervision_scopes"] == ["write", "shared"]
    assert merged["scopes"] == ["read", "shared", "write"]
    assert merged["supervisor_session_issued_to"] == "ops@example.com"
    assert merged["supervisor_session_label"] == "incident-room"


def test_merge_supervisor_session_user_omits_blank_optional_metadata() -> None:
    merged = security_mod._merge_supervisor_session_user(
        {"scopes": []},
        {"session_key_id": None, "level": None, "scopes": None, "issued_to": " ", "session_label": ""},
    )

    assert merged["session_key_id"] == ""
    assert merged["supervision_level"] == ""
    assert merged["supervision_scopes"] == []
    assert merged["scopes"] == []
    assert "supervisor_session_issued_to" not in merged
    assert "supervisor_session_label" not in merged


def test_record_supervisor_session_key_denied_writes_expected_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    append = Mock()
    monkeypatch.setattr(security_mod, "append_admin_audit_event", append)
    monkeypatch.setattr(security_mod, "_auth_admin_audit_path", lambda: Path("audit.jsonl"))
    request = SimpleNamespace(url=SimpleNamespace(path="/auth/check"))

    security_mod._record_supervisor_session_key_denied(
        request=request,
        user={"email": "admin@example.com", "supervision_level": "platform", "session_key_id": "ssk-9"},
        reason="revoked_supervisor_session_key",
    )

    append.assert_called_once_with(
        audit_path=Path("audit.jsonl"),
        actor="admin@example.com",
        actor_level="platform",
        action="supervisor_session_key_denied",
        target_type="supervisor_session",
        target_id="ssk-9",
        source="auth",
        result="denied",
        reason="revoked_supervisor_session_key",
        request_path="/auth/check",
    )


def test_apply_supervisor_session_header_passthrough_success_and_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    user = {"sub": "admin-1", "scopes": ["read"]}
    request = SimpleNamespace(url=SimpleNamespace(path="/admin"))
    validate = Mock(return_value={"session_key_id": "ssk-1", "level": "tenant", "scopes": ["write"]})
    monkeypatch.setattr(security_mod, "validate_supervisor_session_key", validate)
    monkeypatch.setattr(security_mod, "_supervisor_session_key_store_path", lambda: Path("keys.json"))

    assert security_mod._apply_supervisor_session_header(
        request=request,
        user=user,
        raw_supervisor_session_key="  ",
    ) is user
    validate.assert_not_called()

    merged = security_mod._apply_supervisor_session_header(
        request=request,
        user=user,
        raw_supervisor_session_key=" key-value ",
    )
    validate.assert_called_once_with(Path("keys.json"), "key-value")
    assert merged["supervisor_session_validated"] is True
    assert merged["scopes"] == ["read", "write"]

    validate.side_effect = PermissionError("expired credential")
    record = Mock()
    monkeypatch.setattr(security_mod, "_record_supervisor_session_key_denied", record)

    with pytest.raises(HTTPException) as exc_info:
        security_mod._apply_supervisor_session_header(
            request=request,
            user=user,
            raw_supervisor_session_key="expired-key",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Supervisor session key denied."
    record.assert_called_once_with(
        request=request,
        user=user,
        reason="expired_supervisor_session_key",
    )
