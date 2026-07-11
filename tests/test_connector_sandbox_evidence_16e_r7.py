"""Tests for immutable reference-only sandbox evidence R7."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import processual_api.integrations as integration_package
import processual_api.integrations.sandbox_evidence as evidence_module
from processual_api.integrations.sandbox_evidence import (
    CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS,
    SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS,
    ConnectorSandboxEvidenceAssessment,
    ConnectorSandboxEvidenceBundle,
    ConnectorSandboxEvidenceBundleStatus,
    ConnectorSandboxEvidenceContract,
    ConnectorSandboxEvidenceContractStatus,
    ConnectorSandboxEvidenceRequest,
    ConnectorSandboxEvidenceSourceKind,
    assess_connector_sandbox_evidence_contract,
    build_connector_sandbox_evidence_bundle,
    get_connector_sandbox_evidence_contract,
    list_connector_sandbox_evidence_contracts,
    normalize_connector_sandbox_evidence_contract_id,
    validate_connector_sandbox_evidence_contracts,
    validate_connector_sandbox_evidence_registry,
)
from processual_api.integrations.sandbox_read_faults import (
    ConnectorSandboxReadFaultResult,
    ConnectorSandboxReadFaultResultStatus,
)
from processual_api.integrations.sandbox_read_workflow import (
    ConnectorSandboxReadWorkflowResult,
    ConnectorSandboxReadWorkflowResultStatus,
)

CONTRACT_ID = (
    "telecom_ticketing_local_sandbox_evidence_contract"
)
WORKFLOW_ID = (
    "telecom_ticketing_deterministic_sandbox_read_workflow"
)
PLAN_ID = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)

REQUIRED_TRUE_CONTRACT_FIELDS = (
    "local_only",
    "sandbox_only",
    "reference_only",
    "deterministic",
    "immutable_bundle_required",
    "non_persistent_by_default",
    "export_safe_references_only",
    "source_validation_required",
    "unsafe_flag_projection_required",
)

UNSAFE_CONTRACT_FIELDS = (
    "source_execution_allowed",
    "payload_body_allowed",
    "raw_response_allowed",
    "secret_material_allowed",
    "credential_resolution_allowed",
    "dispatcher_invocation_allowed",
    "network_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "external_export_execution_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

UNSAFE_BUNDLE_FIELDS = (
    "source_executed",
    "payload_body_included",
    "raw_response_included",
    "secret_material_included",
    "credentials_resolved",
    "dispatcher_invoked",
    "network_accessed",
    "bundle_persisted",
    "background_task_created",
    "external_export_executed",
    "route_exposed",
    "runtime_used",
    "production_used",
)

WORKFLOW_UNSAFE_FIELDS = (
    "real_operation_executed",
    "payload_body_used",
    "secret_accessed",
    "credentials_resolved",
    "dispatcher_invoked",
    "base_transport_invoked",
    "external_http_used",
    "socket_used",
    "payload_persisted",
    "background_task_created",
    "route_exposed",
    "runtime_used",
    "production_used",
)

FAULT_UNSAFE_FIELDS = (
    "real_timeout_waited",
    "retry_executed",
    "automatic_retry_executed",
    "background_retry_created",
    "network_attempted",
    "secret_resolved",
    "dispatcher_invoked",
    "workflow_executed",
    "payload_body_used",
    "payload_persisted",
    "route_exposed",
    "runtime_used",
    "production_used",
)

FAULT_CASES = (
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_TIMEOUT,
        "telecom_ticketing_synthetic_timeout_fault_profile",
        "synthetic_timeout_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_TRANSPORT_UNAVAILABLE,
        (
            "telecom_ticketing_"
            "synthetic_transport_unavailable_fault_profile"
        ),
        "synthetic_transport_unavailable_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_AUTHORIZATION_DENIED,
        (
            "telecom_ticketing_"
            "synthetic_authorization_denied_fault_profile"
        ),
        "synthetic_authorization_denied_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE,
        (
            "telecom_ticketing_"
            "synthetic_secret_reference_unavailable_fault_profile"
        ),
        "synthetic_secret_reference_unavailable_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_PLAN_REJECTED,
        "telecom_ticketing_synthetic_plan_rejected_fault_profile",
        "synthetic_plan_rejected_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_OPERATOR_APPROVAL_MISSING,
        (
            "telecom_ticketing_"
            "synthetic_operator_approval_missing_fault_profile"
        ),
        "synthetic_operator_approval_missing_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_SECURITY_REVIEW_MISSING,
        (
            "telecom_ticketing_"
            "synthetic_security_review_missing_fault_profile"
        ),
        "synthetic_security_review_missing_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_MALFORMED_REFERENCE,
        (
            "telecom_ticketing_"
            "synthetic_malformed_reference_fault_profile"
        ),
        "synthetic_malformed_reference_fault_reference",
    ),
    (
        ConnectorSandboxReadFaultResultStatus.SAFE_REFUSAL,
        "telecom_ticketing_safe_refusal_fault_profile",
        "safe_refusal_fault_reference",
    ),
)


def _workflow_result() -> ConnectorSandboxReadWorkflowResult:
    return ConnectorSandboxReadWorkflowResult(
        request_id="workflow_request_reference",
        workflow_id=WORKFLOW_ID,
        fake_transport_id=(
            "telecom_ticketing_deterministic_fake_sandbox_transport"
        ),
        base_transport_id=(
            "telecom_ticketing_disabled_no_network_transport"
        ),
        plan_id=PLAN_ID,
        status=(
            ConnectorSandboxReadWorkflowResultStatus
            .SYNTHETIC_READ_COMPLETED
        ),
        reason_code="governed_synthetic_ticket_read_completed",
        reason="deterministic local result",
        contract_validated=True,
        request_validated=True,
        reference_graph_validated=True,
        fake_transport_validated=True,
        synthetic_result_completed=True,
        fake_result_status_reference="synthetic_read_result",
        synthetic_resource_reference=(
            "synthetic_ticket_reference"
        ),
        synthetic_resource_type_reference=(
            "synthetic_ticket_resource_type_reference"
        ),
        synthetic_source_reference=(
            "deterministic_local_fixture_v1_reference"
        ),
        synthetic_metadata_references=(
            "synthetic_ticket_state_open_reference",
            "synthetic_ticket_priority_normal_reference",
            "synthetic_ticket_channel_api_reference",
            "synthetic_ticket_owner_unassigned_reference",
            "synthetic_ticket_created_at_fixed_reference",
        ),
    )


def _fault_result(
    *,
    status: ConnectorSandboxReadFaultResultStatus = (
        ConnectorSandboxReadFaultResultStatus.SYNTHETIC_TIMEOUT
    ),
    fault_profile_id: str = (
        "telecom_ticketing_synthetic_timeout_fault_profile"
    ),
    synthetic_fault_reference: str = (
        "synthetic_timeout_fault_reference"
    ),
) -> ConnectorSandboxReadFaultResult:
    return ConnectorSandboxReadFaultResult(
        request_id="fault_request_reference",
        fault_profile_id=fault_profile_id,
        workflow_id=WORKFLOW_ID,
        status=status,
        reason_code=f"{status.value}_reason_code",
        reason_reference=f"{status.value}_reason_reference",
        synthetic_fault_reference=synthetic_fault_reference,
        contract_validated=True,
        request_validated=True,
        workflow_validated=True,
        fault_injected=True,
        deterministic=True,
        immediate_result=True,
        safe_refusal=True,
    )


def _request(
    source_result: (
        ConnectorSandboxReadWorkflowResult
        | ConnectorSandboxReadFaultResult
    ),
    *,
    evidence_contract_id: str = CONTRACT_ID,
) -> ConnectorSandboxEvidenceRequest:
    return ConnectorSandboxEvidenceRequest(
        evidence_id="sandbox_evidence_reference",
        evidence_contract_id=evidence_contract_id,
        source_result=source_result,
    )


def _forge(
    source: object,
    **changes: object,
) -> object:
    forged = object.__new__(type(source))

    for field in fields(source):
        value = changes.get(
            field.name,
            getattr(source, field.name),
        )
        object.__setattr__(
            forged,
            field.name,
            value,
        )

    return forged


def _workflow_bundle() -> ConnectorSandboxEvidenceBundle:
    return build_connector_sandbox_evidence_bundle(
        _request(_workflow_result())
    )


def _fault_bundle() -> ConnectorSandboxEvidenceBundle:
    return build_connector_sandbox_evidence_bundle(
        _request(_fault_result())
    )


def test_registry_is_immutable_and_valid() -> None:
    assert isinstance(
        CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS,
        MappingProxyType,
    )
    assert len(CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS) == 1
    assert (
        SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS
        == (CONTRACT_ID,)
    )
    assert validate_connector_sandbox_evidence_registry() == ()

    with pytest.raises(TypeError):
        CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS[
            "forged_contract"
        ] = get_connector_sandbox_evidence_contract(
            CONTRACT_ID
        )


def test_list_and_get_preserve_contract_identity() -> None:
    listed = list_connector_sandbox_evidence_contracts()

    assert len(listed) == 1
    assert listed[0] is get_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )


@pytest.mark.parametrize(
    "contract_type",
    (
        ConnectorSandboxEvidenceContract,
        ConnectorSandboxEvidenceAssessment,
        ConnectorSandboxEvidenceRequest,
        ConnectorSandboxEvidenceBundle,
    ),
)
def test_contracts_are_frozen_slotted_dataclasses(
    contract_type: type[object],
) -> None:
    assert is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True
    assert hasattr(contract_type, "__slots__")


def test_contract_instance_is_frozen() -> None:
    contract = get_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        contract.production_allowed = True


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " evidence_reference",
        "evidence_reference ",
        "https://external.invalid/evidence",
        "bearer raw_value",
        "password=raw_value",
        "token=raw_value",
        "secret=raw_value",
        "private_key=raw_value",
        "raw_payload=raw_value",
        "response_body=raw_value",
    ),
)
def test_normalizer_rejects_invalid_or_raw_reference(
    value: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_connector_sandbox_evidence_contract_id(
            value
        )


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_connector_sandbox_evidence_contract_id(
            object()
        )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_CONTRACT_FIELDS,
)
def test_contract_rejects_disabled_required_flag(
    field_name: str,
) -> None:
    contract = get_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )

    with pytest.raises(ValueError):
        replace(contract, **{field_name: False})


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_CONTRACT_FIELDS,
)
def test_contract_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    contract = get_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )

    with pytest.raises(ValueError):
        replace(contract, **{field_name: True})


def test_contract_validation_detects_duplicate() -> None:
    contract = get_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )
    issues = validate_connector_sandbox_evidence_contracts(
        (contract, contract)
    )

    assert any(
        "duplicate_contract_id" in issue
        for issue in issues
    )


def test_assessment_is_ready_and_default_deny() -> None:
    assessment = assess_connector_sandbox_evidence_contract(
        CONTRACT_ID
    )

    assert assessment.status is (
        ConnectorSandboxEvidenceContractStatus
        .LOCAL_EVIDENCE_READY
    )
    assert assessment.contract_valid is True
    assert assessment.source_types_valid is True
    assert assessment.local_evidence_available is True
    assert assessment.deterministic is True
    assert assessment.reference_only is True
    assert assessment.non_persistent_by_default is True
    assert assessment.export_safe_references_only is True

    for field_name in UNSAFE_CONTRACT_FIELDS:
        assert getattr(assessment, field_name) is False

def test_evidence_request_rejects_wrong_source_type() -> None:
    with pytest.raises(TypeError):
        ConnectorSandboxEvidenceRequest(
            evidence_id="evidence_reference",
            evidence_contract_id=CONTRACT_ID,
            source_result=object(),
        )


def test_builder_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError):
        build_connector_sandbox_evidence_bundle(
            object()
        )


def test_workflow_result_builds_deterministic_bundle() -> None:
    request = _request(_workflow_result())

    first = build_connector_sandbox_evidence_bundle(
        request
    )
    second = build_connector_sandbox_evidence_bundle(
        request
    )

    assert first == second
    assert first.status is (
        ConnectorSandboxEvidenceBundleStatus
        .EVIDENCE_CAPTURED
    )
    assert first.source_kind is (
        ConnectorSandboxEvidenceSourceKind.WORKFLOW_RESULT
    )
    assert first.evidence_captured is True
    assert first.plan_id_reference == PLAN_ID
    assert first.fault_profile_id_reference == (
        "fault_profile_not_applicable_reference"
    )
    assert first.result_reference == (
        "synthetic_ticket_reference"
    )
    assert len(first.metadata_references) == 5
    assert all(
        marker.endswith("_false_reference")
        for marker in first.unsafe_flag_projection
    )

    for field_name in UNSAFE_BUNDLE_FIELDS:
        assert getattr(first, field_name) is False


@pytest.mark.parametrize(
    (
        "status",
        "fault_profile_id",
        "fault_reference",
    ),
    FAULT_CASES,
)
def test_each_r6_fault_builds_safe_evidence(
    status: ConnectorSandboxReadFaultResultStatus,
    fault_profile_id: str,
    fault_reference: str,
) -> None:
    source = _fault_result(
        status=status,
        fault_profile_id=fault_profile_id,
        synthetic_fault_reference=fault_reference,
    )

    bundle = build_connector_sandbox_evidence_bundle(
        _request(source)
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .EVIDENCE_CAPTURED
    )
    assert bundle.source_kind is (
        ConnectorSandboxEvidenceSourceKind.FAULT_RESULT
    )
    assert bundle.evidence_captured is True
    assert (
        bundle.fault_profile_id_reference
        == fault_profile_id
    )
    assert bundle.result_reference == fault_reference
    assert bundle.metadata_references == ()
    assert all(
        marker.endswith("_false_reference")
        for marker in bundle.unsafe_flag_projection
    )

    for field_name in UNSAFE_BUNDLE_FIELDS:
        assert getattr(bundle, field_name) is False


def test_unknown_evidence_contract_is_blocked() -> None:
    bundle = build_connector_sandbox_evidence_bundle(
        _request(
            _workflow_result(),
            evidence_contract_id=(
                "unknown_evidence_contract_reference"
            ),
        )
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .CONTRACT_BLOCKED
    )
    assert bundle.evidence_captured is False
    assert bundle.result_reference == (
        "result_not_captured_reference"
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "contract_validated",
        "request_validated",
        "reference_graph_validated",
        "fake_transport_validated",
        "synthetic_result_completed",
    ),
)
def test_invalid_workflow_state_is_not_captured(
    field_name: str,
) -> None:
    forged = _forge(
        _workflow_result(),
        **{field_name: False},
    )

    bundle = build_connector_sandbox_evidence_bundle(
        _request(forged)
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .INVALID_SOURCE_RESULT
    )
    assert bundle.evidence_captured is False


@pytest.mark.parametrize(
    "field_name",
    (
        "contract_validated",
        "request_validated",
        "workflow_validated",
        "fault_injected",
        "deterministic",
        "immediate_result",
        "safe_refusal",
    ),
)
def test_invalid_fault_state_is_not_captured(
    field_name: str,
) -> None:
    forged = _forge(
        _fault_result(),
        **{field_name: False},
    )

    bundle = build_connector_sandbox_evidence_bundle(
        _request(forged)
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .INVALID_SOURCE_RESULT
    )
    assert bundle.evidence_captured is False


@pytest.mark.parametrize(
    "field_name",
    WORKFLOW_UNSAFE_FIELDS,
)
def test_forged_unsafe_workflow_source_is_rejected(
    field_name: str,
) -> None:
    forged = _forge(
        _workflow_result(),
        **{field_name: True},
    )

    bundle = build_connector_sandbox_evidence_bundle(
        _request(forged)
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .UNSAFE_SOURCE_REJECTED
    )
    assert bundle.evidence_captured is False
    assert (
        f"{field_name}_true_reference"
        in bundle.unsafe_flag_projection
    )
    assert bundle.result_reference == (
        "result_not_captured_reference"
    )


@pytest.mark.parametrize(
    "field_name",
    FAULT_UNSAFE_FIELDS,
)
def test_forged_unsafe_fault_source_is_rejected(
    field_name: str,
) -> None:
    forged = _forge(
        _fault_result(),
        **{field_name: True},
    )

    bundle = build_connector_sandbox_evidence_bundle(
        _request(forged)
    )

    assert bundle.status is (
        ConnectorSandboxEvidenceBundleStatus
        .UNSAFE_SOURCE_REJECTED
    )
    assert bundle.evidence_captured is False
    assert (
        f"{field_name}_true_reference"
        in bundle.unsafe_flag_projection
    )


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_BUNDLE_FIELDS,
)
def test_bundle_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    bundle = _workflow_bundle()

    with pytest.raises(ValueError):
        replace(bundle, **{field_name: True})


def test_bundle_rejects_raw_result_reference() -> None:
    bundle = _workflow_bundle()

    with pytest.raises(ValueError):
        replace(
            bundle,
            result_reference="https://external.invalid/result",
        )


def test_bundle_is_frozen_and_has_no_instance_dictionary() -> None:
    bundle = _fault_bundle()

    assert not hasattr(bundle, "__dict__")

    with pytest.raises((FrozenInstanceError, AttributeError)):
        bundle.production_used = True


def test_request_and_bundle_are_reference_only() -> None:
    request_fields = {
        field.name
        for field in fields(
            ConnectorSandboxEvidenceRequest
        )
    }
    bundle_fields = {
        field.name
        for field in fields(
            ConnectorSandboxEvidenceBundle
        )
    }

    prohibited = {
        "payload",
        "payload_body",
        "response_body",
        "headers",
        "authorization",
        "password",
        "token",
        "secret",
        "private_key",
        "certificate",
        "endpoint",
        "url",
        "personal_data",
    }

    assert request_fields.isdisjoint(prohibited)
    assert bundle_fields.isdisjoint(prohibited)


def test_module_does_not_import_or_call_execution_layers() -> None:
    source = inspect.getsource(evidence_module)
    tree = ast.parse(source)

    prohibited_symbols = (
        "execute_connector_sandbox_read_workflow",
        "execute_connector_sandbox_read_fault",
        "ConnectorDeterministicSandboxReadWorkflow",
        "ConnectorDeterministicSandboxReadFaultSimulator",
        "ConnectorDeterministicFakeSandboxTransport",
    )

    assert tuple(
        symbol
        for symbol in prohibited_symbols
        if symbol in source
    ) == ()

    forbidden_modules = {
        "requests",
        "httpx",
        "urllib",
        "socket",
        "aiohttp",
        "subprocess",
        "asyncio",
        "time",
        "random",
        "uuid",
    }

    module_hits = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]

                if root in forbidden_modules:
                    module_hits.append(
                        (node.lineno, alias.name)
                    )

        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]

            if root in forbidden_modules:
                module_hits.append(
                    (node.lineno, node.module or "")
                )

    assert module_hits == []


def test_public_export_list_covers_r7_surface() -> None:
    expected = {
        "CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS",
        "SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS",
        "ConnectorSandboxEvidenceAssessment",
        "ConnectorSandboxEvidenceBundle",
        "ConnectorSandboxEvidenceBundleStatus",
        "ConnectorSandboxEvidenceContract",
        "ConnectorSandboxEvidenceContractStatus",
        "ConnectorSandboxEvidenceRequest",
        "ConnectorSandboxEvidenceSourceKind",
        "assess_connector_sandbox_evidence_contract",
        "build_connector_sandbox_evidence_bundle",
        "get_connector_sandbox_evidence_contract",
        "list_connector_sandbox_evidence_contracts",
        "normalize_connector_sandbox_evidence_contract_id",
        "validate_connector_sandbox_evidence_contracts",
        "validate_connector_sandbox_evidence_registry",
    }

    assert set(evidence_module.__all__) == expected


def test_package_exports_r7_public_surface() -> None:
    expected = set(evidence_module.__all__)

    assert expected.issubset(
        set(integration_package.__all__)
    )

    for name in expected:
        assert hasattr(integration_package, name)


def test_r7_documentation_records_required_markers(
) -> None:
    documentation = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R7.md"
    ).read_text(encoding="utf-8")

    required_markers = (
        "EXTERNAL-CONNECTIVITY-16E-R7",
        "Immutable reference-only sandbox evidence bundle",
        "telecom_ticketing_local_sandbox_evidence_contract",
        "ConnectorSandboxReadWorkflowResult",
        "ConnectorSandboxReadFaultResult",
        "build_connector_sandbox_evidence_bundle",
        "evidence_captured",
        "invalid_source_result",
        "unsafe_source_rejected",
        "contract_blocked",
        "source_execution_allowed=False",
        "payload_body_allowed=False",
        "raw_response_allowed=False",
        "secret_material_allowed=False",
        "network_access_allowed=False",
        "persistence_allowed=False",
        "external_export_execution_allowed=False",
        "runtime_enabled=False",
        "production_allowed=False",
        "source_executed=False",
        "bundle_persisted=False",
        "external_export_executed=False",
        "execute_connector_sandbox_read_workflow",
        "execute_connector_sandbox_read_fault",
        "EXTERNAL-CONNECTIVITY-16F-R1",
    )

    missing = tuple(
        marker
        for marker in required_markers
        if marker not in documentation
    )

    assert missing == ()
