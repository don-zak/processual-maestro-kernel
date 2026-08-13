from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import processual_api.services.enterprise_qualification_decisions_18 as decisions_module
from processual_api.services.enterprise_qualification_decisions_18 import (
    QualificationDecisionError,
    activate_enterprise_qualification,
)
from processual_api.services.enterprise_qualification_store_18 import (
    empty_qualification_store,
    load_qualification_store,
    save_qualification_store,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def _case(*, client_id: str = "client-demo") -> dict:
    return {
        "case_id": "case-demo",
        "client_id": client_id,
        "integration_track": "camara",
    }


def _grant(**overrides) -> dict:
    grant = {
        "grant_id": "grant-demo",
        "case_id": "case-demo",
        "client_id": "client-demo",
        "status": "approved",
        "environment": "sandbox",
        "approved_task_ids": ["sandbox_capability_probe"],
        "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "supervisor_session_key_id": "supervisor-session-secret-reference",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }
    grant.update(overrides)
    return grant


def _write_store(path: Path, grants: list[dict]) -> None:
    store = empty_qualification_store()
    store["grants"] = grants
    save_qualification_store(store, path)


def test_activate_qualification_persists_safe_projection_and_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "qualification.json"
    _write_store(path, [_grant()])
    monkeypatch.setattr(decisions_module, "_now", lambda: NOW)

    result = activate_enterprise_qualification(
        case=_case(),
        client_id=" client-demo ",
        store_path=path,
    )

    assert result["status"] == "activated"
    assert result["already_activated"] is False
    assert result["case_phase"] == "qualification_activated"
    assert result["credential_issued"] is False
    assert result["binding_created"] is False
    assert "supervisor_session_key_id" not in result["grant"]
    assert result["grant"]["production_allowed"] is False
    assert result["grant"]["runtime_connector_approved"] is False

    persisted = load_qualification_store(path)
    assert persisted["grants"][0]["status"] == "activated"
    assert persisted["grants"][0]["activated_at"] == NOW.isoformat()
    assert len(persisted["audit"]) == 1
    audit = persisted["audit"][0]
    assert audit["event"] == "qualification_activated"
    assert audit["task_ids"] == ["sandbox_capability_probe"]
    assert audit["production_allowed"] is False
    assert audit["external_http_allowed"] is False


def test_activate_qualification_is_idempotent_after_activation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "qualification.json"
    _write_store(
        path,
        [
            _grant(
                status="activated",
                activated_at=(NOW - timedelta(hours=1)).isoformat(),
            )
        ],
    )
    monkeypatch.setattr(decisions_module, "_now", lambda: NOW)

    result = activate_enterprise_qualification(
        case=_case(),
        client_id="client-demo",
        store_path=path,
    )

    assert result["already_activated"] is True
    persisted = load_qualification_store(path)
    assert persisted["audit"] == []
    assert persisted["grants"][0]["activated_at"] == (
        NOW - timedelta(hours=1)
    ).isoformat()


@pytest.mark.parametrize(
    ("case", "client_id", "match"),
    [
        (_case(), "", "client_id is required"),
        (_case(), "other-client", "does not belong"),
        ({"case_id": "", "client_id": "client-demo", "integration_track": "camara"}, "client-demo", "case_id is required"),
        ({"case_id": "case-demo", "client_id": "client-demo", "integration_track": "unknown"}, "client-demo", "Unsupported integration track"),
    ],
)
def test_activate_qualification_rejects_invalid_identity(
    tmp_path: Path,
    case: dict,
    client_id: str,
    match: str,
) -> None:
    with pytest.raises(QualificationDecisionError, match=match):
        activate_enterprise_qualification(
            case=case,
            client_id=client_id,
            store_path=tmp_path / "qualification.json",
        )


def test_activate_qualification_rejects_missing_or_duplicate_active_grants(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    _write_store(missing, [])
    with pytest.raises(QualificationDecisionError, match="not found"):
        activate_enterprise_qualification(
            case=_case(),
            client_id="client-demo",
            store_path=missing,
        )

    duplicate = tmp_path / "duplicate.json"
    _write_store(duplicate, [_grant(), _grant(grant_id="grant-two")])
    with pytest.raises(QualificationDecisionError, match="Multiple active"):
        activate_enterprise_qualification(
            case=_case(),
            client_id="client-demo",
            store_path=duplicate,
        )


def test_activate_qualification_rejects_invalid_and_expired_expiry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(decisions_module, "_now", lambda: NOW)

    invalid = tmp_path / "invalid.json"
    _write_store(invalid, [_grant(expires_at="not-a-date")])
    with pytest.raises(QualificationDecisionError, match="expiry is invalid"):
        activate_enterprise_qualification(
            case=_case(),
            client_id="client-demo",
            store_path=invalid,
        )

    expired = tmp_path / "expired.json"
    _write_store(expired, [_grant(expires_at=(NOW - timedelta(seconds=1)).isoformat())])
    with pytest.raises(QualificationDecisionError, match="has expired"):
        activate_enterprise_qualification(
            case=_case(),
            client_id="client-demo",
            store_path=expired,
        )
    assert load_qualification_store(expired)["grants"][0]["status"] == "expired"


def test_activate_qualification_accepts_naive_future_expiry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "naive.json"
    _write_store(path, [_grant(expires_at="2026-08-14T12:00:00")])
    monkeypatch.setattr(decisions_module, "_now", lambda: NOW)

    result = activate_enterprise_qualification(
        case=_case(),
        client_id="client-demo",
        store_path=path,
    )

    assert result["status"] == "activated"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"environment": "production"}, "safety boundaries"),
        ({"production_allowed": True}, "safety boundaries"),
        ({"runtime_connector_approved": True}, "safety boundaries"),
        ({"write_allowed": True}, "safety boundaries"),
        ({"restricted_allowed": True}, "safety boundaries"),
        ({"external_http_allowed": True}, "safety boundaries"),
        ({"raw_secret_visible": True}, "safety boundaries"),
        ({"approved_task_ids": []}, "no approved tasks"),
        ({"approved_task_ids": ["", "   "]}, "no approved tasks"),
    ],
)
def test_activate_qualification_enforces_sandbox_boundaries(
    tmp_path: Path,
    monkeypatch,
    overrides: dict,
    match: str,
) -> None:
    path = tmp_path / "unsafe.json"
    _write_store(path, [_grant(**overrides)])
    monkeypatch.setattr(decisions_module, "_now", lambda: NOW)

    with pytest.raises(QualificationDecisionError, match=match):
        activate_enterprise_qualification(
            case=_case(),
            client_id="client-demo",
            store_path=path,
        )
