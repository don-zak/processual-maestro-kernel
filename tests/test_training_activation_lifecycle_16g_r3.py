"""Isolated activation lifecycle coverage for External Connectivity 16G-R3."""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from processual_api.integrations.training_activation_lifecycle import (
    TrainingActivationExercise,
    TrainingActivationIsolation,
    run_training_activation_lifecycle,
)
from processual_api.integrations.training_connection_request import (
    build_training_customer_input_package,
)
from processual_api.integrations.training_customer_input_review import (
    TrainingCustomerInputReviewStatus,
    TrainingCustomerInputSubmission,
    review_training_customer_input_submission,
)

REQUEST_ID = "telecom_ticketing_training_connection_request"


def _values() -> dict[str, str]:
    package = build_training_customer_input_package(REQUEST_ID)
    values = {
        item.item_id: f"training_{item.item_id.replace('.', '_')}_ref"
        for item in package.items
    }
    values["provider.selected_secret_provider"] = "gcp_secret_manager"
    values["outbound.tls_minimum_version_selection"] = "tls_1_2"
    return values


def _review(values: dict[str, str] | None = None):
    submission = TrainingCustomerInputSubmission(
        submission_id="training_activation_submission",
        request_id=REQUEST_ID,
        values=values if values is not None else _values(),
    )
    return review_training_customer_input_submission(submission)


def test_models_are_frozen_slotted_dataclasses(tmp_path) -> None:
    isolation = TrainingActivationIsolation(
        store_path=tmp_path / "tasks.json",
        audit_path=tmp_path / "audit.jsonl",
    )

    assert isolation.training_mode is True
    assert isolation.__slots__

    with pytest.raises(FrozenInstanceError):
        isolation.training_mode = False  # type: ignore[misc]

    assert TrainingActivationExercise.__slots__


def test_lifecycle_requires_a_complete_supervisor_ready_r2_review(
    tmp_path,
) -> None:
    values = _values()
    values.pop("outbound.kill_switch_reference")
    review = _review(values)

    assert review.status is (
        TrainingCustomerInputReviewStatus.NEEDS_CLARIFICATION
    )

    isolation = TrainingActivationIsolation(
        store_path=tmp_path / "tasks.json",
        audit_path=tmp_path / "audit.jsonl",
    )

    with pytest.raises(
        ValueError,
        match="accepted R2 supervisor-ready review is required",
    ):
        run_training_activation_lifecycle(review, isolation)

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_isolation_rejects_shared_paths_and_existing_files(tmp_path) -> None:
    shared = tmp_path / "shared.json"

    with pytest.raises(
        ValueError,
        match="store and audit paths must differ",
    ):
        TrainingActivationIsolation(
            store_path=shared,
            audit_path=shared,
        )

    existing_store = tmp_path / "existing_tasks.json"
    existing_store.write_text("{}", encoding="utf-8")

    isolation = TrainingActivationIsolation(
        store_path=existing_store,
        audit_path=tmp_path / "new_audit.jsonl",
    )

    with pytest.raises(
        ValueError,
        match="isolated training store must not already exist",
    ):
        run_training_activation_lifecycle(_review(), isolation)


def test_complete_training_activation_lifecycle_is_isolated_and_revoked(
    tmp_path,
    monkeypatch,
) -> None:
    original_store = tmp_path / "original_store_reference.json"
    original_audit = tmp_path / "original_audit_reference.jsonl"

    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(original_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(original_audit),
    )

    store_path = tmp_path / "training_tasks.json"
    audit_path = tmp_path / "training_audit.jsonl"
    isolation = TrainingActivationIsolation(
        store_path=store_path,
        audit_path=audit_path,
    )

    result = run_training_activation_lifecycle(
        _review(),
        isolation,
        actor="training-supervisor-proof",
    )

    assert result.initial_status == "pending_supervisor_review"
    assert result.key_prefix.startswith("iapk_")
    assert result.raw_key_visible_once is True
    assert result.second_issuance_rejected is True
    assert result.raw_key_absent_from_list is True
    assert result.raw_key_absent_from_store is True
    assert result.raw_key_absent_from_audit is True
    assert result.key_hash_absent_from_public_list is True
    assert result.suspended_status == "suspended"
    assert result.resumed_status == "pending_supervisor_review"
    assert result.final_status == "revoked"
    assert result.final_key_revoked is True
    assert result.sandbox_grant_disabled is True
    assert result.runtime_connector_grant_disabled is True
    assert result.external_http_enabled is False
    assert result.runtime_enabled is False
    assert result.production_allowed is False

    assert (
        __import__("os").environ["PMK_INTEGRATION_PILOT_TASKS_STORE"]
        == str(original_store)
    )
    assert (
        __import__("os").environ["PMK_ADMIN_AUDIT_EVENTS_PATH"]
        == str(original_audit)
    )
    assert not original_store.exists()
    assert not original_audit.exists()

    persisted = json.loads(store_path.read_text(encoding="utf-8"))
    task = persisted["tasks"][0]

    issuance_events = [
        event
        for event in task["timeline"]
        if event["action"] == "activation_permission_key_issued"
    ]
    assert len(issuance_events) == 1
    assert task["status"] == "revoked"
    assert task["integration_key_revoked"] is True
    assert task["sandbox_grant_disabled"] is True
    assert task["runtime_connector_grant_disabled"] is True

    audit_events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    issuance_audits = [
        event
        for event in audit_events
        if event.get("event_type")
        == "integration_activation_permission_key_issued"
    ]
    assert len(issuance_audits) == 1

    store_text = store_path.read_text(encoding="utf-8")
    audit_text = audit_path.read_text(encoding="utf-8")
    assert result.key_prefix in store_text
    assert f"{result.key_prefix}." not in store_text
    assert f"{result.key_prefix}." not in audit_text


def test_training_module_has_no_network_or_secret_sdk_imports() -> None:
    source_path = Path(
        "processual_api/integrations/training_activation_lifecycle.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    prohibited = {
        "boto3",
        "google",
        "http",
        "httpx",
        "requests",
        "socket",
        "ssl",
        "urllib",
        "azure",
        "hvac",
    }
    assert imported_roots.isdisjoint(prohibited)


def test_package_exports_16g_r3_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "TrainingActivationExercise",
        "TrainingActivationIsolation",
        "run_training_activation_lifecycle",
    }

    assert expected.issubset(set(package.__all__))
    for name in expected:
        assert getattr(package, name) is not None


def test_16g_r3_documentation_records_safety_boundary() -> None:
    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16G_R3.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    for marker in (
        "activation_permission_key_already_issued",
        "second_issuance_rejected",
        "raw key",
        "isolated store",
        "isolated audit",
        "suspend",
        "resume",
        "revoke",
        "external_http_enabled=false",
        "runtime_enabled=false",
        "production_allowed=false",
        "no secret resolution",
        "no external http",
        "no socket",
        "no sandbox launch",
    ):
        assert marker in lowered
