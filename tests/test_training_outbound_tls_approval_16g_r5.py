"""Outbound allowlist and TLS approval simulation tests for 16G-R5."""

from __future__ import annotations

import ast
import json
import os
from dataclasses import fields
from pathlib import Path

import pytest

from processual_api.integrations.training_activation_lifecycle import (
    TrainingActivationIsolation,
)
from processual_api.integrations.training_connection_request import (
    build_training_customer_input_package,
)
from processual_api.integrations.training_customer_input_review import (
    TrainingCustomerInputReviewStatus,
    TrainingCustomerInputSubmission,
    review_training_customer_input_submission,
)
from processual_api.integrations.training_outbound_tls_approval import (
    TrainingOutboundTlsApprovalSimulation,
    simulate_training_outbound_tls_approval,
)
from processual_api.services import integration_pilot_controls as pilot

REQUEST_ID = "telecom_ticketing_training_connection_request"
TLS_VERSIONS = ("tls_1_2", "tls_1_3")
UNSAFE_FIELDS = (
    "allowlist_applied",
    "dns_resolution_performed",
    "port_opened",
    "tls_context_created",
    "ca_bundle_loaded",
    "certificate_loaded",
    "certificate_pin_applied",
    "proxy_configured",
    "egress_authorized",
    "kill_switch_armed",
    "connection_attempted",
    "external_http_enabled",
    "socket_access_enabled",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)


def _values(tls_version="tls_1_2"):
    package = build_training_customer_input_package(REQUEST_ID)
    values = {
        item.item_id: f"training_{item.item_id.replace('.', '_')}_ref"
        for item in package.items
    }
    values["provider.selected_secret_provider"] = "gcp_secret_manager"
    values["outbound.tls_minimum_version_selection"] = tls_version
    return values


def _submission(
    tls_version="tls_1_2",
    *,
    submission_id="r5_training_submission",
    values=None,
):
    return TrainingCustomerInputSubmission(
        submission_id=submission_id,
        request_id=REQUEST_ID,
        values=values if values is not None else _values(tls_version),
    )


def _review(submission):
    return review_training_customer_input_submission(submission)


def _isolation(tmp_path, name="r5"):
    return TrainingActivationIsolation(
        store_path=tmp_path / f"{name}_tasks.json",
        audit_path=tmp_path / f"{name}_audit.jsonl",
    )


def test_result_is_frozen_slotted_and_has_no_raw_fields() -> None:
    assert TrainingOutboundTlsApprovalSimulation.__slots__
    assert (
        TrainingOutboundTlsApprovalSimulation
        .__dataclass_params__.frozen
        is True
    )

    names = {
        field.name
        for field in fields(TrainingOutboundTlsApprovalSimulation)
    }
    prohibited = {
        "raw_key",
        "raw_secret",
        "secret",
        "password",
        "token",
        "key_hash",
        "certificate",
        "private_key",
        "endpoint",
        "url",
        "payload",
    }
    assert names.isdisjoint(prohibited)


@pytest.mark.parametrize("tls_version", TLS_VERSIONS)
def test_supported_tls_versions_produce_disabled_review_simulation(
    tmp_path,
    monkeypatch,
    tls_version,
):
    original_store = tmp_path / f"{tls_version}_original_store.json"
    original_audit = tmp_path / f"{tls_version}_original_audit.jsonl"
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(original_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(original_audit),
    )

    submission = _submission(tls_version)
    isolation = _isolation(tmp_path, tls_version)

    result = simulate_training_outbound_tls_approval(
        _review(submission),
        submission,
        isolation,
        actor="r5-training-supervisor",
    )

    assert result.connector_id == "telecom_ticketing_reference"
    assert result.selected_tls_minimum_version == tls_version
    assert result.assessment_status == (
        "network_policy_references_received_for_review"
    )
    assert result.reference_count == 11
    assert result.required_reference_count == 11
    assert result.activation_permission_key_validated is True
    assert result.ready_for_network_policy_review is True
    assert result.approval_simulation_created is True
    assert result.final_status == "revoked"
    assert result.final_key_revoked is True

    for field_name in UNSAFE_FIELDS:
        assert getattr(result, field_name) is False

    assert (
        os.environ["PMK_INTEGRATION_PILOT_TASKS_STORE"]
        == str(original_store)
    )
    assert (
        os.environ["PMK_ADMIN_AUDIT_EVENTS_PATH"]
        == str(original_audit)
    )
    assert not original_store.exists()
    assert not original_audit.exists()

    store_text = isolation.store_path.read_text(encoding="utf-8")
    audit_text = isolation.audit_path.read_text(encoding="utf-8")

    assert f"{result.activation_permission_key_id}." not in store_text
    assert f"{result.activation_permission_key_id}." not in audit_text

    for key, value in submission.values.items():
        if key.startswith("outbound."):
            assert value not in store_text
            assert value not in audit_text

    persisted = json.loads(store_text)
    task = persisted["tasks"][0]
    assert task["status"] == "revoked"
    assert task["integration_key_revoked"] is True

    issuance_events = [
        event
        for event in task["timeline"]
        if event["action"] == "activation_permission_key_issued"
    ]
    revoke_events = [
        event
        for event in task["timeline"]
        if event["action"] == "revoke"
    ]
    assert len(issuance_events) == 1
    assert len(revoke_events) == 1


def test_incomplete_review_is_rejected_before_store_creation(
    tmp_path,
):
    values = _values()
    values.pop("outbound.kill_switch_reference")
    submission = _submission(values=values)
    review = _review(submission)

    assert review.status is (
        TrainingCustomerInputReviewStatus.NEEDS_CLARIFICATION
    )

    isolation = _isolation(tmp_path)

    with pytest.raises(
        ValueError,
        match="accepted R2 supervisor-ready review is required",
    ):
        simulate_training_outbound_tls_approval(
            review,
            submission,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_review_submission_mismatch_is_rejected_before_writes(
    tmp_path,
):
    canonical = _submission(submission_id="canonical_submission")
    mismatched = _submission(submission_id="mismatched_submission")
    isolation = _isolation(tmp_path)

    with pytest.raises(
        ValueError,
        match="review and submission identifiers differ",
    ):
        simulate_training_outbound_tls_approval(
            _review(canonical),
            mismatched,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_forged_noncanonical_review_is_rejected(tmp_path) -> None:
    submission = _submission()
    review = _review(submission)

    forged = object.__new__(type(review))
    for field in fields(type(review)):
        object.__setattr__(
            forged,
            field.name,
            getattr(review, field.name),
        )
    object.__setattr__(forged, "received_input_count", 26)

    isolation = _isolation(tmp_path)

    with pytest.raises(
        ValueError,
        match="canonical R2 submission review",
    ):
        simulate_training_outbound_tls_approval(
            forged,
            submission,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_validation_failure_revokes_and_restores_environment(
    tmp_path,
    monkeypatch,
):
    original_store = tmp_path / "original_store.json"
    original_audit = tmp_path / "original_audit.jsonl"
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(original_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(original_audit),
    )

    submission = _submission()
    isolation = _isolation(tmp_path)

    def reject_validation(task_id, raw_key):
        assert task_id.startswith("itask_")
        assert raw_key.startswith("iapk_")
        return {
            "ok": False,
            "activation_permission_key_valid": False,
        }

    monkeypatch.setattr(
        pilot,
        "validate_activation_permission_key",
        reject_validation,
    )

    with pytest.raises(
        RuntimeError,
        match="activation permission validation failed",
    ):
        simulate_training_outbound_tls_approval(
            _review(submission),
            submission,
            isolation,
        )

    assert (
        os.environ["PMK_INTEGRATION_PILOT_TASKS_STORE"]
        == str(original_store)
    )
    assert (
        os.environ["PMK_ADMIN_AUDIT_EVENTS_PATH"]
        == str(original_audit)
    )

    persisted = json.loads(
        isolation.store_path.read_text(encoding="utf-8")
    )
    task = persisted["tasks"][0]
    assert task["status"] == "revoked"
    assert task["integration_key_revoked"] is True

    audit_text = isolation.audit_path.read_text(encoding="utf-8")
    assert "R5 simulation aborted and revoked." in audit_text


def test_existing_isolated_path_is_rejected(tmp_path) -> None:
    submission = _submission()
    isolation = _isolation(tmp_path)
    isolation.audit_path.write_text("", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="isolated training audit must not already exist",
    ):
        simulate_training_outbound_tls_approval(
            _review(submission),
            submission,
            isolation,
        )


def test_module_has_no_network_tls_or_provider_sdk_imports() -> None:
    source_path = Path(
        "processual_api/integrations/training_outbound_tls_approval.py"
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
        "azure",
        "boto3",
        "google",
        "http",
        "httpx",
        "hvac",
        "requests",
        "socket",
        "ssl",
        "urllib",
    }
    assert imported_roots.isdisjoint(prohibited)


def test_package_exports_16g_r5_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "TrainingOutboundTlsApprovalSimulation",
        "simulate_training_outbound_tls_approval",
    }

    assert expected.issubset(set(package.__all__))
    for name in expected:
        assert getattr(package, name) is not None


def test_16g_r5_documentation_records_default_deny_boundary() -> None:
    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16G_R5.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    for marker in (
        "network_policy_references_received_for_review",
        "allowlist_applied=false",
        "dns_resolution_performed=false",
        "port_opened=false",
        "tls_context_created=false",
        "ca_bundle_loaded=false",
        "certificate_loaded=false",
        "certificate_pin_applied=false",
        "proxy_configured=false",
        "egress_authorized=false",
        "kill_switch_armed=false",
        "connection_attempted=false",
        "external_http_enabled=false",
        "socket_access_enabled=false",
        "runtime_enabled=false",
        "production_allowed=false",
        "no dns resolution",
        "no socket",
        "no tls context",
        "revoked",
    ):
        assert marker in lowered
