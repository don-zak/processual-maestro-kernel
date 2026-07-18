"""Reference-only secret-provider binding simulation tests for 16G-R4."""

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
from processual_api.integrations.training_secret_provider_binding import (
    TrainingSecretProviderBindingSimulation,
    simulate_training_secret_provider_binding,
)
from processual_api.services import integration_pilot_controls as pilot

REQUEST_ID = "telecom_ticketing_training_connection_request"
PROVIDERS = (
    "gcp_secret_manager",
    "hashicorp_vault",
    "aws_secrets_manager",
    "azure_key_vault",
)
UNSAFE_RESULT_FIELDS = (
    "provider_binding_created",
    "provider_client_initialized",
    "secret_reference_registered",
    "secret_value_accessed",
    "secret_value_stored",
    "raw_secret_visible",
    "authentication_performed",
    "credentials_resolved",
    "resolution_allowed",
    "external_http_enabled",
    "socket_access_enabled",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)


def _values(
    provider: str = "gcp_secret_manager",
) -> dict[str, str]:
    package = build_training_customer_input_package(REQUEST_ID)
    values = {
        item.item_id: f"training_{item.item_id.replace('.', '_')}_ref"
        for item in package.items
    }
    values["provider.selected_secret_provider"] = provider
    values["outbound.tls_minimum_version_selection"] = "tls_1_2"
    return values


def _submission(
    provider: str = "gcp_secret_manager",
    *,
    submission_id: str = "r4_training_submission",
    values: dict[str, str] | None = None,
) -> TrainingCustomerInputSubmission:
    return TrainingCustomerInputSubmission(
        submission_id=submission_id,
        request_id=REQUEST_ID,
        values=values if values is not None else _values(provider),
    )


def _review(submission):
    return review_training_customer_input_submission(submission)


def _isolation(tmp_path, name="r4"):
    return TrainingActivationIsolation(
        store_path=tmp_path / f"{name}_tasks.json",
        audit_path=tmp_path / f"{name}_audit.jsonl",
    )


def test_simulation_result_is_frozen_slotted_and_has_no_raw_fields() -> None:
    assert TrainingSecretProviderBindingSimulation.__slots__
    assert (
        TrainingSecretProviderBindingSimulation
        .__dataclass_params__.frozen
        is True
    )

    names = {
        field.name
        for field in fields(TrainingSecretProviderBindingSimulation)
    }
    prohibited = {
        "raw_key",
        "raw_secret",
        "secret",
        "secret_value",
        "password",
        "token",
        "credential",
        "payload",
        "endpoint",
        "url",
        "key_hash",
    }
    assert names.isdisjoint(prohibited)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_each_provider_produces_disabled_reference_only_simulation(
    tmp_path,
    monkeypatch,
    provider,
):
    original_store = tmp_path / f"{provider}_original_store.json"
    original_audit = tmp_path / f"{provider}_original_audit.jsonl"
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(original_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(original_audit),
    )

    submission = _submission(provider)
    review = _review(submission)
    isolation = _isolation(tmp_path, provider)

    result = simulate_training_secret_provider_binding(
        review,
        submission,
        isolation,
        actor="r4-training-supervisor",
    )

    assert result.selected_provider == provider
    assert result.assessment_status == (
        "provider_references_received_for_review"
    )
    assert result.reference_count == 7
    assert result.required_reference_count == 7
    assert result.activation_permission_key_validated is True
    assert result.ready_for_provider_review is True
    assert result.binding_simulation_created is True
    assert result.final_status == "revoked"
    assert result.final_key_revoked is True

    for name in UNSAFE_RESULT_FIELDS:
        assert getattr(result, name) is False

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
        if key.startswith("provider."):
            assert value not in store_text
            assert value not in audit_text

    persisted = json.loads(store_text)
    task = persisted["tasks"][0]
    assert task["status"] == "revoked"
    assert task["integration_key_revoked"] is True
    assert task["sandbox_grant_disabled"] is True
    assert task["runtime_connector_grant_disabled"] is True

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


def test_incomplete_r2_review_is_rejected_before_store_creation(
    tmp_path,
):
    values = _values()
    values.pop("provider.security_review_reference")
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
        simulate_training_secret_provider_binding(
            review,
            submission,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_review_and_submission_mismatch_is_rejected_before_writes(
    tmp_path,
):
    canonical = _submission(submission_id="canonical_submission")
    mismatched = _submission(submission_id="mismatched_submission")
    review = _review(canonical)
    isolation = _isolation(tmp_path)

    with pytest.raises(
        ValueError,
        match="review and submission identifiers differ",
    ):
        simulate_training_secret_provider_binding(
            review,
            mismatched,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_forged_noncanonical_review_is_rejected_before_writes(
    tmp_path,
):
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
        simulate_training_secret_provider_binding(
            forged,
            submission,
            isolation,
        )

    assert not isolation.store_path.exists()
    assert not isolation.audit_path.exists()


def test_validation_failure_revokes_task_and_restores_environment(
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
            "error": "forced_validation_failure",
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
        simulate_training_secret_provider_binding(
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
    assert "R4 simulation aborted and revoked." in audit_text


def test_existing_isolated_store_is_rejected(tmp_path) -> None:
    submission = _submission()
    isolation = _isolation(tmp_path)
    isolation.store_path.write_text("{}", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="isolated training store must not already exist",
    ):
        simulate_training_secret_provider_binding(
            _review(submission),
            submission,
            isolation,
        )


def test_module_has_no_network_or_provider_sdk_imports() -> None:
    source_path = Path(
        "processual_api/integrations/training_secret_provider_binding.py"
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


def test_package_exports_16g_r4_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "TrainingSecretProviderBindingSimulation",
        "simulate_training_secret_provider_binding",
    }

    assert expected.issubset(set(package.__all__))
    for name in expected:
        assert getattr(package, name) is not None


def test_16g_r4_documentation_records_default_deny_boundary() -> None:
    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16G_R4.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    for marker in (
        "validate_activation_permission_key",
        "constant-time",
        "provider_binding_created=false",
        "credentials_resolved=false",
        "external_http_enabled=false",
        "socket_access_enabled=false",
        "runtime_enabled=false",
        "production_allowed=false",
        "reference-only",
        "no provider sdk",
        "no secret resolution",
        "no authentication",
        "no sandbox launch",
        "revoked",
    ):
        assert marker in lowered
