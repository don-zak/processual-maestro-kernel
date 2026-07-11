from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from processual_api.integrations.connector_bindings import (
    get_connector_environment_binding,
)
from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
    list_runtime_connector_contracts,
)
from processual_api.integrations.operation_plans import (
    CONNECTOR_APPROVAL_REQUIREMENTS,
    CONNECTOR_AUDIT_PROJECTIONS,
    CONNECTOR_OPERATION_PLANS,
    SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS,
    ConnectorApprovalRequirement,
    ConnectorAuditProjection,
    ConnectorOperationPlan,
    get_connector_approval_requirement,
    get_connector_audit_projection,
    get_connector_operation_plan,
    list_connector_approval_requirements,
    list_connector_audit_projections,
    list_connector_operation_plans,
    validate_connector_operation_contracts,
    validate_connector_operation_registry,
)

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "integrations" / "EXTERNAL_CONNECTIVITY_16C.md"


def _sample_plan() -> ConnectorOperationPlan:
    return list_connector_operation_plans()[0]


def _sample_approval() -> ConnectorApprovalRequirement:
    return list_connector_approval_requirements()[0]


def _sample_audit() -> ConnectorAuditProjection:
    return list_connector_audit_projections()[0]


def test_operation_registry_counts_are_stable() -> None:
    assert len(list_connector_operation_plans()) == 101
    assert len(list_connector_approval_requirements()) == 101
    assert len(list_connector_audit_projections()) == 101
    assert sum(len(plan.steps) for plan in list_connector_operation_plans()) == 404


def test_operation_registry_validation_has_no_issues() -> None:
    assert validate_connector_operation_registry() == ()


def test_operation_registries_are_immutable() -> None:
    with pytest.raises(TypeError):
        CONNECTOR_OPERATION_PLANS["forged"] = _sample_plan()  # type: ignore[index]
    with pytest.raises(TypeError):
        CONNECTOR_APPROVAL_REQUIREMENTS["forged"] = (
            _sample_approval()
        )  # type: ignore[index]
    with pytest.raises(TypeError):
        CONNECTOR_AUDIT_PROJECTIONS["forged"] = _sample_audit()  # type: ignore[index]


def test_operation_contracts_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _sample_plan().status = "planning_only"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        _sample_plan().steps[0].order = 9  # type: ignore[misc]


def test_plans_cover_every_allowed_capability_environment() -> None:
    expected: set[tuple[str, str, str]] = set()
    for connector in list_runtime_connector_contracts():
        for capability in connector.capabilities:
            environments = (
                ("sandbox",)
                if capability.sandbox_only
                else connector.supported_environments
            )
            for environment in environments:
                expected.add(
                    (
                        connector.connector_id,
                        environment,
                        capability.capability_id,
                    )
                )
    actual = {
        (plan.connector_id, plan.environment, plan.capability_id)
        for plan in list_connector_operation_plans()
    }
    assert actual == expected


def test_non_read_plans_remain_sandbox_only() -> None:
    for plan in list_connector_operation_plans():
        if plan.access_mode != "read":
            assert plan.environment == "sandbox"


def test_read_plans_have_sandbox_and_production_references() -> None:
    grouped: dict[tuple[str, str], set[str]] = {}
    for plan in list_connector_operation_plans():
        if plan.access_mode == "read":
            grouped.setdefault(
                (plan.connector_id, plan.capability_id),
                set(),
            ).add(plan.environment)
    assert grouped
    assert all(
        environments == {"sandbox", "production"}
        for environments in grouped.values()
    )


def test_plan_binding_and_capability_references_match() -> None:
    for plan in list_connector_operation_plans():
        binding = get_connector_environment_binding(plan.binding_id)
        connector = get_runtime_connector_contract(plan.connector_id)
        capability = next(
            item
            for item in connector.capabilities
            if item.capability_id == plan.capability_id
        )
        assert binding.connector_id == plan.connector_id
        assert binding.environment == plan.environment
        assert capability.scope_id == plan.scope_id
        assert capability.access_mode == plan.access_mode


def test_operation_steps_preserve_safe_order() -> None:
    for plan in list_connector_operation_plans():
        assert tuple(step.order for step in plan.steps) == (1, 2, 3, 4)
        assert tuple(step.step_kind for step in plan.steps) == (
            SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS
        )
        assert plan.steps[-1].step_kind == "block_dispatch"


def test_all_operation_and_step_execution_flags_are_false() -> None:
    for plan in list_connector_operation_plans():
        assert plan.action_execution_allowed is False
        assert plan.runtime_enabled is False
        assert plan.external_http_enabled is False
        assert plan.production_allowed is False
        assert plan.automatic_activation_allowed is False
        assert plan.credentials_resolution_allowed is False
        for step in plan.steps:
            assert step.execution_allowed is False
            assert step.external_http_allowed is False
            assert step.credentials_resolution_allowed is False


def test_required_operation_metadata_cannot_be_disabled() -> None:
    plan = _sample_plan()
    for field_name in (
        "operation_id_required",
        "tenant_binding_required",
        "payload_hash_required",
        "idempotency_key_required",
        "expiry_required",
    ):
        with pytest.raises(ValueError):
            replace(plan, **{field_name: False})


def test_approval_posture_matches_capability() -> None:
    for plan in list_connector_operation_plans():
        connector = get_runtime_connector_contract(plan.connector_id)
        capability = next(
            item
            for item in connector.capabilities
            if item.capability_id == plan.capability_id
        )
        approval = get_connector_approval_requirement(
            plan.approval_requirement_id
        )
        assert approval.plan_id == plan.plan_id
        assert approval.approval_required is capability.approval_required
        assert (
            approval.requester_approver_separation_required
            is capability.approval_required
        )
        assert approval.supervisor_session_required is capability.approval_required
        assert approval.satisfied is False
        assert approval.execution_allowed is False
        assert approval.production_allowed is False


def test_approval_cannot_be_satisfied_in_16c() -> None:
    with pytest.raises(ValueError):
        replace(_sample_approval(), satisfied=True)


def test_audit_projections_are_schema_only() -> None:
    for plan in list_connector_operation_plans():
        audit = get_connector_audit_projection(plan.audit_projection_id)
        assert audit.plan_id == plan.plan_id
        assert audit.status == "projection_only"
        assert audit.persisted is False
        assert audit.emitted is False
        assert audit.external_sink_enabled is False
        assert "operation_id" in audit.required_fields
        assert "payload_hash" in audit.required_fields
        assert "idempotency_key" in audit.required_fields
        assert "requester_actor" in audit.required_fields
        assert "approver_actor" in audit.required_fields


def test_audit_projection_cannot_emit_or_persist() -> None:
    with pytest.raises(ValueError):
        replace(_sample_audit(), emitted=True)
    with pytest.raises(ValueError):
        replace(_sample_audit(), persisted=True)


def test_getters_accept_normalized_variants_and_reject_unknown_ids() -> None:
    plan = _sample_plan()
    assert get_connector_operation_plan(plan.plan_id.upper()) is plan
    approval = _sample_approval()
    assert (
        get_connector_approval_requirement(
            approval.approval_requirement_id.upper()
        )
        is approval
    )
    audit = _sample_audit()
    assert get_connector_audit_projection(audit.audit_projection_id.upper()) is audit
    with pytest.raises(KeyError):
        get_connector_operation_plan("unknown-operation-plan")


def test_production_plan_for_sandbox_only_capability_is_rejected() -> None:
    plan = next(
        item
        for item in list_connector_operation_plans()
        if item.access_mode != "read"
    )
    production_binding = plan.binding_id.replace(
        "_sandbox_binding",
        "_production_binding",
    )
    with pytest.raises(ValueError, match="Sandbox-only"):
        replace(
            plan,
            plan_id=f"{plan.plan_id}_production_probe",
            binding_id=production_binding,
            environment="production",
        )


def test_executable_step_and_plan_are_rejected() -> None:
    step = _sample_plan().steps[0]
    with pytest.raises(ValueError):
        replace(step, execution_allowed=True)
    with pytest.raises(ValueError):
        replace(_sample_plan(), action_execution_allowed=True)


def test_contract_validation_reports_missing_links() -> None:
    plans = list_connector_operation_plans()
    approvals = list_connector_approval_requirements()[1:]
    audits = list_connector_audit_projections()[1:]
    issues = validate_connector_operation_contracts(plans, approvals, audits)
    assert any("unknown approval requirement" in issue for issue in issues)
    assert any("unknown audit projection" in issue for issue in issues)


def test_documentation_preserves_16c_guardrails() -> None:
    text = DOCUMENT.read_text(encoding="utf-8").lower()
    markers = (
        "external-connectivity-16c",
        "101 operation plans",
        "404 planning steps",
        "action_execution_allowed = false",
        "runtime_enabled = false",
        "external_http_enabled = false",
        "production_allowed = false",
        "credentials_resolution_allowed = false",
        "requester and approver separation",
        "payload hash",
        "idempotency",
        "no customer endpoint",
        "no secret value",
        "no external http",
        "no runtime dispatch",
    )
    for marker in markers:
        assert marker in text
