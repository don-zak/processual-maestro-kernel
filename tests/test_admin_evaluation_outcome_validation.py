from __future__ import annotations

import json

from processual_api.integrations.sandbox_operational_readiness import SandboxContentContract
from processual_api.services.evaluation_outcome_expectations import (
    EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY,
    build_outcome_expectation,
    upsert_outcome_expectation,
    validate_read_outcome,
)
from processual_api.services.evaluation_outcome_runtime import (
    evaluate_completed_task_outcome,
)


def _content() -> SandboxContentContract:
    return SandboxContentContract(
        binding_id="binding-crm-read",
        dataset_reference="dataset/crm-customer-fixture-v1",
        fixture_profile_reference="fixture/crm-customer-active-v1",
        required_record_types=("customer",),
        acceptance_criteria_references=("criteria/crm-active-customer-v1",),
    )


def _expectation() -> dict:
    content = _content()
    return build_outcome_expectation(
        binding_id=content.binding_id,
        task_id="crm.customer_context",
        expected_fields={
            "customer_id": "customer-1",
            "account_status": "active",
        },
        acceptance_criteria_references=content.acceptance_criteria_references,
        dataset_reference=content.dataset_reference,
        fixture_profile_reference=content.fixture_profile_reference,
        created_by="platform-owner",
    )


def test_outcome_expectation_persists_hashes_not_raw_expected_values() -> None:
    expectation = _expectation()
    serialized = json.dumps(expectation, sort_keys=True)

    assert expectation["required_fields"] == ["account_status", "customer_id"]
    assert expectation["raw_expected_values_persisted"] is False
    assert '"customer-1"' not in serialized
    assert '"active"' not in serialized
    assert len(expectation["expected_field_sha256"]["customer_id"]) == 64
    assert len(expectation["expectation_sha256"]) == 64


def test_read_outcome_validation_passes_only_for_expected_semantic_result() -> None:
    content = _content()
    expectation = _expectation()

    passed = validate_read_outcome(
        expectation=expectation,
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "active",
            "display_name": "Synthetic Customer",
        },
        acceptance_criteria_references=content.acceptance_criteria_references,
        dataset_reference=content.dataset_reference,
        fixture_profile_reference=content.fixture_profile_reference,
    )
    failed = validate_read_outcome(
        expectation=expectation,
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "suspended",
        },
        acceptance_criteria_references=content.acceptance_criteria_references,
        dataset_reference=content.dataset_reference,
        fixture_profile_reference=content.fixture_profile_reference,
    )

    assert passed["outcome_validation_status"] == "passed"
    assert passed["outcome_validation_passed"] is True
    assert passed["matched_field_count"] == 2
    assert failed["outcome_validation_status"] == "failed"
    assert failed["outcome_validation_passed"] is False
    assert failed["matched_field_count"] == 1


def test_changed_fixture_or_acceptance_contract_invalidates_old_expectation() -> None:
    content = _content()
    expectation = _expectation()

    result = validate_read_outcome(
        expectation=expectation,
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "active",
        },
        acceptance_criteria_references=("criteria/crm-active-customer-v2",),
        dataset_reference=content.dataset_reference,
        fixture_profile_reference=content.fixture_profile_reference,
    )

    assert result["references_match"] is False
    assert result["outcome_validation_passed"] is False


def test_runtime_outcome_requires_super_admin_prepared_expectation() -> None:
    content = _content()
    raw: dict = {}

    missing = evaluate_completed_task_outcome(
        raw=raw,
        binding_id=content.binding_id,
        task_id="crm.customer_context",
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "active",
        },
        content_contract=content,
        maestro_task_completed=True,
    )
    assert missing["outcome_validation_status"] == "missing_expectation"
    assert missing["outcome_validation_passed"] is False

    upsert_outcome_expectation(raw, _expectation())
    assert EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY in raw

    passed = evaluate_completed_task_outcome(
        raw=raw,
        binding_id=content.binding_id,
        task_id="crm.customer_context",
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "active",
        },
        content_contract=content,
        maestro_task_completed=True,
    )
    assert passed["outcome_validation_status"] == "passed"
    assert passed["outcome_validation_passed"] is True


def test_incomplete_task_cannot_receive_outcome_pass() -> None:
    content = _content()
    raw: dict = {}
    upsert_outcome_expectation(raw, _expectation())

    result = evaluate_completed_task_outcome(
        raw=raw,
        binding_id=content.binding_id,
        task_id="crm.customer_context",
        canonical_result={
            "customer_id": "customer-1",
            "account_status": "active",
        },
        content_contract=content,
        maestro_task_completed=False,
    )

    assert result["outcome_validation_status"] == "task_incomplete"
    assert result["outcome_validation_passed"] is False


def test_admin_expectation_route_is_platform_admin_only_and_nonproduction() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "processual_api"
        / "routers"
        / "settings_admin_evaluation_outcomes.py"
    ).read_text(encoding="utf-8")

    assert "await require_active_platform_admin(current_user)" in source
    assert "/admin/evaluation-grants/bindings/{binding_id}/outcome-expectation" in source
    assert '"raw_expected_values_persisted": False' in source
    assert '"provisioned_by_authority": "platform_admin"' in source
    assert '"production_allowed": False' in source
