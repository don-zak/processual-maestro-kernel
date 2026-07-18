"""Regression coverage for one-time activation permission issuance in 16G-R3."""

from __future__ import annotations

import json

import pytest

from processual_api.services import integration_pilot_controls as pilot


def _configure_isolated_paths(tmp_path, monkeypatch):
    store_path = tmp_path / "integration_pilot_tasks.json"
    audit_path = tmp_path / "admin_audit_events.jsonl"
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(store_path),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(audit_path),
    )
    return store_path, audit_path


def _create_and_issue_once(tmp_path, monkeypatch):
    store_path, audit_path = _configure_isolated_paths(
        tmp_path,
        monkeypatch,
    )
    created = pilot.create_integration_task(
        {
            "client_id": "one-time-issuance-client",
            "operator_org_id": "one-time-issuance-org",
            "pilot_terms_note": "Isolated 16G-R3 regression.",
        },
        created_by="supervisor-proof",
    )
    assert created["ok"] is True

    task_id = created["task"]["task_id"]
    issued = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )
    assert issued["ok"] is True
    assert issued["raw_activation_permission_key_visible_once"] is True
    assert issued["activation_permission_key_once"].startswith("iapk_")

    return task_id, issued, store_path, audit_path


def test_activation_permission_key_second_issuance_is_side_effect_free(
    tmp_path,
    monkeypatch,
):
    task_id, first, store_path, audit_path = _create_and_issue_once(
        tmp_path,
        monkeypatch,
    )
    raw_key = first["activation_permission_key_once"]

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()
    persisted_before = json.loads(store_before)
    task_before = persisted_before["tasks"][0]

    second = pilot.issue_activation_permission_key(
        task_id,
        {
            "activation_permission_key_id": "",
            "activation_permission_key_hash": "",
            "activation_permission_issued_at": "",
            "status": "pending_supervisor_review",
            "expires_at": "2099-01-01T00:00:00Z",
        },
        issued_by="forged-supervisor",
    )

    assert second["ok"] is False
    assert second["error"] == "activation_permission_key_already_issued"
    assert "activation_permission_key_once" not in second
    assert "activation_permission_key_hash" not in second["task"]
    assert second["task"]["activation_permission_key_id"] == (
        task_before["activation_permission_key_id"]
    )
    assert second["guardrails"] == pilot.GUARDRAILS

    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before

    public_text = json.dumps(
        pilot.list_integration_tasks(),
        sort_keys=True,
    )
    assert raw_key not in public_text
    assert raw_key not in store_path.read_text(encoding="utf-8")
    assert raw_key not in audit_path.read_text(encoding="utf-8")
    assert "activation_permission_key_hash" not in public_text


def test_resume_does_not_restore_activation_permission_issuance(
    tmp_path,
    monkeypatch,
):
    task_id, first, store_path, audit_path = _create_and_issue_once(
        tmp_path,
        monkeypatch,
    )

    suspended = pilot.control_integration_task(
        task_id,
        "suspend",
        actor="supervisor-proof",
        reason="one-time issuance suspension proof",
    )
    assert suspended["ok"] is True

    blocked_while_suspended = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )
    assert blocked_while_suspended["ok"] is False
    assert blocked_while_suspended["error"] == (
        "task_not_eligible_for_activation_permission"
    )

    resumed = pilot.control_integration_task(
        task_id,
        "resume",
        actor="supervisor-proof",
        reason="one-time issuance resume proof",
    )
    assert resumed["ok"] is True

    store_before_retry = store_path.read_bytes()
    audit_before_retry = audit_path.read_bytes()

    blocked_after_resume = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )

    assert blocked_after_resume["ok"] is False
    assert blocked_after_resume["error"] == (
        "activation_permission_key_already_issued"
    )
    assert "activation_permission_key_once" not in blocked_after_resume
    assert store_path.read_bytes() == store_before_retry
    assert audit_path.read_bytes() == audit_before_retry

    persisted = json.loads(store_before_retry)
    task = persisted["tasks"][0]
    issuance_events = [
        event
        for event in task["timeline"]
        if event["action"] == "activation_permission_key_issued"
    ]
    assert len(issuance_events) == 1
    assert task["activation_permission_key_id"] == (
        first["task"]["activation_permission_key_id"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("activation_permission_key_id", "iapk_legacy_marker"),
        ("activation_permission_key_hash", "legacy-hash-marker"),
        ("activation_permission_issued_at", "2026-07-12T00:00:00Z"),
        ("status", "activation_permission_issued"),
    ),
)
def test_each_persisted_issuance_marker_independently_blocks_issuance(
    tmp_path,
    monkeypatch,
    field,
    value,
):
    store_path, audit_path = _configure_isolated_paths(
        tmp_path,
        monkeypatch,
    )
    created = pilot.create_integration_task(
        {
            "client_id": "legacy-marker-client",
            "operator_org_id": "legacy-marker-org",
        },
        created_by="supervisor-proof",
    )
    task_id = created["task"]["task_id"]

    store = json.loads(store_path.read_text(encoding="utf-8"))
    task = store["tasks"][0]
    task["activation_permission_key_id"] = ""
    task.pop("activation_permission_key_hash", None)
    task["activation_permission_issued_at"] = ""
    task["status"] = "pending_supervisor_review"
    task[field] = value
    store_path.write_text(
        json.dumps(store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    store_before = store_path.read_bytes()
    audit_before = audit_path.read_bytes()

    result = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )

    assert result["ok"] is False
    assert result["error"] == "activation_permission_key_already_issued"
    assert "activation_permission_key_once" not in result
    assert store_path.read_bytes() == store_before
    assert audit_path.read_bytes() == audit_before
