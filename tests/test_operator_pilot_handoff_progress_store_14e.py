"""Tests for safe operator pilot handoff progress storage 14E."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from processual_api.services.operator_pilot_handoff_actions import (
    build_operator_pilot_handoff_actions_preview,
)
from processual_api.services.operator_pilot_handoff_progress_store import (
    ALLOWED_PROGRESS_STATUSES,
    build_operator_pilot_handoff_progress_payload,
    progress_store_path,
    update_operator_pilot_handoff_action_progress,
)


def _first_action_id() -> str:
    actions = build_operator_pilot_handoff_actions_preview()["actions"]
    action = actions[0]

    return str(action.get("action_id") or action.get("id") or action.get("key"))


def test_14e_initial_progress_payload_is_safe_and_read_only(
    tmp_path: Path,
) -> None:
    store = tmp_path / "progress.json"

    payload = build_operator_pilot_handoff_progress_payload(store)

    assert payload["phase_id"] == "operator-pilot-handoff-progress-14e"
    assert payload["schema_version"] == ("operator_pilot_handoff_progress_14e")
    assert payload["storage"] == "local_json_only"
    assert payload["action_count"] == 12
    assert len(payload["actions"]) == 12
    assert payload["timeline"] == []
    assert payload["timeline_event_count"] == 0
    assert payload["allowed_statuses"] == list(ALLOWED_PROGRESS_STATUSES)
    assert {action["status"] for action in payload["actions"]} == {"pending_operator_input"}

    assert payload["guardrails"] == {
        "production_allowed": False,
        "runtime_connector_approved": False,
        "customer_credentials_present": False,
        "external_http_allowed": False,
        "automatic_activation_allowed": False,
        "action_execution_allowed": False,
        "credentials_storage_allowed": False,
        "free_form_secret_fields_allowed": False,
        "local_progress_tracking_only": True,
    }

    assert not store.exists()


def test_14e_progress_update_persists_safe_local_metadata(
    tmp_path: Path,
) -> None:
    store = tmp_path / "progress.json"
    action_id = _first_action_id()

    updated = update_operator_pilot_handoff_action_progress(
        action_id,
        {
            "status": "requested",
            "supervisor_actor": "owner_admin",
            "note": "Operator input requested for readiness review.",
            "safe_reference": "PILOT-14E-001",
        },
        store,
    )

    assert store.exists()
    assert updated["updated_action"]["action_id"] == action_id
    assert updated["updated_action"]["status"] == "requested"
    assert updated["updated_action"]["supervisor_actor"] == "owner_admin"
    assert updated["timeline_event_count"] == 1

    reloaded = build_operator_pilot_handoff_progress_payload(store)
    progress = {action["action_id"]: action for action in reloaded["actions"]}[action_id]

    assert progress["status"] == "requested"
    assert progress["safe_reference"] == "PILOT-14E-001"
    assert reloaded["status_counts"]["requested"] == 1
    assert reloaded["status_counts"]["pending_operator_input"] == 11

    raw_payload = json.loads(store.read_text(encoding="utf-8"))

    assert raw_payload["guardrails"]["production_allowed"] is False
    assert raw_payload["guardrails"]["runtime_connector_approved"] is False
    assert raw_payload["timeline"][0]["action_id"] == action_id


def test_14e_progress_store_path_supports_safe_environment_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = tmp_path / "environment-progress.json"

    monkeypatch.setenv(
        "PMK_OPERATOR_PILOT_HANDOFF_PROGRESS_PATH",
        str(expected),
    )

    assert progress_store_path() == expected


@pytest.mark.parametrize(
    "status",
    [
        "approved",
        "production_approved",
        "completed",
        "runtime_enabled",
        "",
    ],
)
def test_14e_rejects_unsupported_progress_statuses(
    tmp_path: Path,
    status: str,
) -> None:
    with pytest.raises(ValueError, match="unsupported progress status"):
        update_operator_pilot_handoff_action_progress(
            _first_action_id(),
            {
                "status": status,
                "supervisor_actor": "owner_admin",
            },
            tmp_path / "progress.json",
        )


def test_14e_rejects_unknown_action_id(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError,
        match="unknown operator pilot handoff action",
    ):
        update_operator_pilot_handoff_action_progress(
            "unknown_action",
            {
                "status": "requested",
                "supervisor_actor": "owner_admin",
            },
            tmp_path / "progress.json",
        )


def test_14e_requires_supervisor_actor(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="supervisor_actor is required"):
        update_operator_pilot_handoff_action_progress(
            _first_action_id(),
            {
                "status": "requested",
                "supervisor_actor": "",
            },
            tmp_path / "progress.json",
        )


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        ("note", "password=unsafe"),
        ("note", "Bearer unsafe-value"),
        ("safe_reference", "https://outside.example/item"),
        ("safe_reference", "api_key=unsafe"),
        ("supervisor_actor", "authorization: unsafe"),
    ],
)
def test_14e_rejects_secret_or_external_reference_text(
    tmp_path: Path,
    field_name: str,
    unsafe_value: str,
) -> None:
    payload = {
        "status": "requested",
        "supervisor_actor": "owner_admin",
        field_name: unsafe_value,
    }

    with pytest.raises(
        ValueError,
        match="prohibited secret or external reference",
    ):
        update_operator_pilot_handoff_action_progress(
            _first_action_id(),
            payload,
            tmp_path / "progress.json",
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "production_allowed",
        "runtime_connector_approved",
        "credentials",
        "endpoint",
        "raw_secret",
    ],
)
def test_14e_rejects_unsupported_or_execution_fields(
    tmp_path: Path,
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="unsupported progress update fields",
    ):
        update_operator_pilot_handoff_action_progress(
            _first_action_id(),
            {
                "status": "requested",
                "supervisor_actor": "owner_admin",
                field_name: True,
            },
            tmp_path / "progress.json",
        )
