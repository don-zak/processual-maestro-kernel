from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from processual_api.auth.account_recovery_external_revocation import (
    AccountRecoveryExternalAuthorityRevoker,
    ExternalAuthorityRevocationUnavailableError,
)
from processual_api.supervisor_session_keys import (
    validate_supervisor_session_key,
)

NOW = datetime(
    2026,
    7,
    24,
    8,
    30,
    tzinfo=UTC,
)


def _record(
    *,
    issued_to: str,
    key_hash: str,
    revoked_at: str | None = None,
) -> dict:
    return {
        "session_key_id": "supsk_" + uuid.uuid4().hex,
        "key_hash": key_hash,
        "level": "owner_supervisor",
        "scopes": ["admin:read"],
        "issued_by": "owner@example.test",
        "issued_to": issued_to,
        "session_label": "Recovery test",
        "reason": "Test",
        "created_at": NOW.isoformat(),
        "expires_at": "",
        "revoked_at": revoked_at,
        "last_used_at": None,
    }


def _write_store(
    path: Path,
    records: list[dict],
) -> None:
    path.write_text(
        json.dumps(
            {
                "supervisor_session_keys": records,
            }
        ),
        encoding="utf-8",
    )


def test_revokes_matching_external_authorities(
    tmp_path: Path,
):
    user_id = str(uuid.uuid4())
    path = tmp_path / "supervisor.json"

    _write_store(
        path,
        [
            _record(
                issued_to=user_id,
                key_hash="invalid",
            ),
            _record(
                issued_to="person@example.test",
                key_hash="invalid",
            ),
            _record(
                issued_to="other@example.test",
                key_hash="invalid",
            ),
        ],
    )

    settings = {
        "api_keys": [
            {
                "id": "active",
                "user_id": user_id,
                "status": "enabled",
                "revoked_at": None,
            },
            {
                "id": "old",
                "user_id": user_id,
                "status": "revoked",
                "revoked_at": NOW.isoformat(),
            },
            {
                "id": "other",
                "user_id": "other-user",
                "status": "enabled",
                "revoked_at": None,
            },
        ]
    }

    saved: list[dict] = []

    revoker = AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=path,
        settings_loader=(lambda value: settings),
        settings_saver=(lambda value, raw: saved.append(raw)),
        clock=lambda: NOW,
    )

    receipt = revoker.revoke(
        user_id=user_id,
        identity_aliases=("person@example.test",),
    )

    assert receipt.supervisor_session_keys_revoked == 2
    assert receipt.api_keys_revoked == 1
    assert len(saved) == 1

    records = json.loads(path.read_text(encoding="utf-8"))["supervisor_session_keys"]

    assert records[0]["revoked_at"] == NOW.isoformat()
    assert records[1]["revoked_at"] == NOW.isoformat()
    assert records[2]["revoked_at"] is None

    assert settings["api_keys"][0]["status"] == "revoked"
    assert settings["api_keys"][0]["revoked_at"] == NOW.isoformat()
    assert settings["api_keys"][2]["revoked_at"] is None


def test_revocation_is_idempotent(
    tmp_path: Path,
):
    user_id = str(uuid.uuid4())
    path = tmp_path / "supervisor.json"

    _write_store(
        path,
        [],
    )

    settings = {
        "api_keys": [
            {
                "id": "old",
                "user_id": user_id,
                "status": "revoked",
                "revoked_at": NOW.isoformat(),
            }
        ]
    }

    saves: list[dict] = []

    revoker = AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=path,
        settings_loader=(lambda value: settings),
        settings_saver=(lambda value, raw: saves.append(raw)),
        clock=lambda: NOW,
    )

    first = revoker.revoke(
        user_id=user_id,
    )
    second = revoker.revoke(
        user_id=user_id,
    )

    assert first.supervisor_session_keys_revoked == 0
    assert first.api_keys_revoked == 0
    assert second == first
    assert saves == []


def test_invalid_api_store_fails_closed(
    tmp_path: Path,
):
    revoker = AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=(tmp_path / "supervisor.json"),
        settings_loader=(lambda value: {"api_keys": "invalid"}),
        settings_saver=(lambda value, raw: None),
        clock=lambda: NOW,
    )

    with pytest.raises(
        ExternalAuthorityRevocationUnavailableError,
        match="API key authority is invalid",
    ):
        revoker.revoke(
            user_id=str(uuid.uuid4()),
        )


def test_corrupt_supervisor_store_fails_closed(
    tmp_path: Path,
):
    path = tmp_path / "supervisor.json"

    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    revoker = AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=path,
        settings_loader=(lambda value: {}),
        settings_saver=(lambda value, raw: None),
        clock=lambda: NOW,
    )

    with pytest.raises(
        ExternalAuthorityRevocationUnavailableError,
        match=("Supervisor session key authority could not be revoked"),
    ):
        revoker.revoke(
            user_id=str(uuid.uuid4()),
        )


def test_revoked_supervisor_key_cannot_validate(
    tmp_path: Path,
):
    from processual_api.supervisor_session_keys import (
        issue_supervisor_session_key,
        revoke_supervisor_session_keys_for_identity,
    )

    path = tmp_path / "supervisor.json"

    actor = {
        "email": "owner@example.test",
        "supervision_level": ("owner_supervisor"),
    }

    issued = issue_supervisor_session_key(
        path,
        actor,
        {
            "level": "operations_supervisor",
            "issued_to": "person@example.test",
            "session_label": "Recovery target",
            "reason": "Test",
            "expires_at": "",
        },
    )

    count = revoke_supervisor_session_keys_for_identity(
        path,
        ("person@example.test",),
        revoked_by="account_recovery",
        reason="account_recovery_completed",
        revoked_at=NOW,
    )

    assert count == 1

    with pytest.raises(
        PermissionError,
        match="revoked",
    ):
        validate_supervisor_session_key(
            path,
            issued["raw_key"],
        )
