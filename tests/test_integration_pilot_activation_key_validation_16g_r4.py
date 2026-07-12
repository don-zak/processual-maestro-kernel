"""Read-only activation key validation regression for 16G-R4."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.services import integration_pilot_controls as pilot


def _setup(tmp_path, monkeypatch):
    store_path = tmp_path / "pilot_tasks.json"
    audit_path = tmp_path / "pilot_audit.jsonl"
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(store_path),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(audit_path),
    )
    return store_path, audit_path


def _create_and_issue(tmp_path, monkeypatch):
    store_path, audit_path = _setup(tmp_path, monkeypatch)
    created = pilot.create_integration_task(
        {
            "client_id": "r4-validation-client",
            "operator_org_id": "r4-validation-operator",
            "pilot_terms_note": "Isolated R4 validation.",
        },
        created_by="r4-supervisor",
    )
    assert created["ok"] is True

    task_id = created["task"]["task_id"]
    issued = pilot.issue_activation_permission_key(
        task_id,
        {
            "expires_at": (
                datetime.now(UTC) + timedelta(hours=1)
            ).replace(microsecond=0).isoformat().replace(
                "+00:00",
                "Z",
            ),
        },
        issued_by="r4-supervisor",
    )
    assert issued["ok"] is True

    return (
        task_id,
        issued["activation_permission_key_once"],
        store_path,
        audit_path,
    )


def _replace_task_fields(store_path, **changes):
    store = json.loads(store_path.read_text(encoding="utf-8"))
    store["tasks"][0].update(changes)
    store_path.write_text(
        json.dumps(
            store,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_valid_key_is_accepted_without_store_or_audit_writes(
    tmp_path,
    monkeypatch,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        raw_key,
    )

    assert result["ok"] is True
    assert result["activation_permission_key_valid"] is True
    assert result["package_version"] == (
        "integration-pilot-controls-16g-r4"
    )
    assert result["guardrails"] == pilot.GUARDRAILS
    assert result["task"]["status"] == "activation_permission_issued"
    assert "activation_permission_key_hash" not in result["task"]
    assert "activation_permission_key_once" not in result
    assert raw_key not in json.dumps(result, sort_keys=True)
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


@pytest.mark.parametrize(
    "forged_key",
    (
        "",
        "forged",
        "iapk_forged.invalid",
        "iapk_forged.",
        ".invalid",
    ),
)
def test_forged_key_is_rejected_without_side_effects(
    tmp_path,
    monkeypatch,
    forged_key,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        forged_key,
    )

    assert result["ok"] is False
    assert result["error"] == "invalid_activation_permission_key"
    assert result["activation_permission_key_valid"] is False
    assert "activation_permission_key_once" not in result
    assert "activation_permission_key_hash" not in result["task"]
    assert raw_key not in json.dumps(result, sort_keys=True)
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


@pytest.mark.parametrize(
    ("action", "expected_status"),
    (
        ("suspend", "suspended"),
        ("revoke", "revoked"),
        ("cancel", "cancelled"),
    ),
)
def test_disabled_task_rejects_the_real_key(
    tmp_path,
    monkeypatch,
    action,
    expected_status,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    controlled = pilot.control_integration_task(
        task_id,
        action,
        actor="r4-supervisor",
        reason="R4 inactive-key proof.",
    )
    assert controlled["task"]["status"] == expected_status

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        raw_key,
    )

    assert result["ok"] is False
    assert result["error"] == "activation_permission_key_inactive"
    assert result["activation_permission_key_valid"] is False
    assert raw_key not in json.dumps(result, sort_keys=True)
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


def test_resume_does_not_reactivate_the_key(
    tmp_path,
    monkeypatch,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    pilot.control_integration_task(
        task_id,
        "suspend",
        actor="r4-supervisor",
    )
    resumed = pilot.control_integration_task(
        task_id,
        "resume",
        actor="r4-supervisor",
    )
    assert resumed["task"]["status"] == "pending_supervisor_review"

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        raw_key,
    )

    assert result["ok"] is False
    assert result["error"] == "activation_permission_key_inactive"
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


def test_expired_key_is_rejected_without_mutation(
    tmp_path,
    monkeypatch,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    expired = (
        datetime.now(UTC) - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _replace_task_fields(
        store_path,
        activation_permission_expires_at=expired,
    )

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        raw_key,
    )

    assert result["ok"] is False
    assert result["error"] == "activation_permission_key_expired"
    assert result["activation_permission_key_valid"] is False
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("activation_permission_key_id", ""),
        ("activation_permission_key_hash", ""),
        ("activation_permission_expires_at", ""),
        ("activation_permission_expires_at", "not-a-timestamp"),
        ("activation_permission_expires_at", "2026-07-12T12:00:00"),
    ),
)
def test_invalid_persisted_key_metadata_is_rejected(
    tmp_path,
    monkeypatch,
    field,
    value,
):
    task_id, raw_key, store_path, audit_path = _create_and_issue(
        tmp_path,
        monkeypatch,
    )
    _replace_task_fields(store_path, **{field: value})

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.validate_activation_permission_key(
        task_id,
        raw_key,
    )

    assert result["ok"] is False
    assert result["error"] == (
        "activation_permission_key_metadata_invalid"
    )
    assert result["activation_permission_key_valid"] is False
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before


def test_unknown_task_returns_safe_default_deny(
    tmp_path,
    monkeypatch,
):
    store_path, audit_path = _setup(tmp_path, monkeypatch)

    result = pilot.validate_activation_permission_key(
        "itask_unknown",
        "iapk_unknown.invalid",
    )

    assert result["ok"] is False
    assert result["error"] == "task_not_found"
    assert result["activation_permission_key_valid"] is False
    assert result["guardrails"] == pilot.GUARDRAILS
    assert not store_path.exists()
    assert not audit_path.exists()
