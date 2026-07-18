"""Tests for governed operator sandbox reference intake 16F-R1."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import processual_api.integrations as integration_package
import processual_api.integrations.operator_sandbox_intake as intake_module
from processual_api.integrations.operator_sandbox_intake import (
    OPERATOR_SANDBOX_INTAKE_CONTRACTS,
    SUPPORTED_OPERATOR_SANDBOX_INTAKES,
    OperatorSandboxIntakeAssessment,
    OperatorSandboxIntakeContract,
    OperatorSandboxIntakeStatus,
    OperatorSandboxReferenceSubmission,
    assess_operator_sandbox_intake,
    get_operator_sandbox_intake_contract,
    list_operator_sandbox_intake_contracts,
    normalize_operator_sandbox_intake_id,
    validate_operator_sandbox_intake_contracts,
    validate_operator_sandbox_intake_registry,
)

INTAKE_ID = (
    "telecom_ticketing_operator_sandbox_reference_intake"
)

REQUIRED_INPUT_NAMES = (
    "endpoint_reference",
    "auth_method_reference",
    "secret_provider_reference",
    "tenant_reference",
    "scope_reference",
    "tls_policy_reference",
    "allowlist_reference",
    "security_review_reference",
    "operator_approval_reference",
    "kill_switch_reference",
)

REQUIRED_TRUE_FIELDS = (
    "sandbox_only",
    "read_only",
    "reference_only",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
    "tls_policy_required",
    "allowlist_required",
    "kill_switch_required",
)

UNSAFE_FIELDS = (
    "endpoint_registered",
    "target_binding_created",
    "secret_reference_registered",
    "credentials_resolved",
    "external_http_enabled",
    "socket_access_enabled",
    "request_execution_allowed",
    "dispatcher_invocation_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)


def _submission() -> OperatorSandboxReferenceSubmission:
    return OperatorSandboxReferenceSubmission(
        submission_id="operator_submission_reference",
        intake_id=INTAKE_ID,
        endpoint_reference=(
            "operator_endpoint_registry_reference"
        ),
        auth_method_reference=(
            "operator_oauth2_method_reference"
        ),
        secret_provider_reference=(
            "customer_vault_provider_reference"
        ),
        tenant_reference=(
            "operator_sandbox_tenant_reference"
        ),
        scope_reference="ticket_read_scope_reference",
        tls_policy_reference=(
            "operator_tls_policy_reference"
        ),
        allowlist_reference=(
            "operator_allowlist_policy_reference"
        ),
        security_review_reference=(
            "security_review_pending_reference"
        ),
        operator_approval_reference=(
            "operator_approval_pending_reference"
        ),
        kill_switch_reference=(
            "operator_kill_switch_reference"
        ),
    )


def _forge_submission(
    submission: OperatorSandboxReferenceSubmission,
    **changes: object,
) -> OperatorSandboxReferenceSubmission:
    forged = object.__new__(
        OperatorSandboxReferenceSubmission
    )

    for field in fields(submission):
        object.__setattr__(
            forged,
            field.name,
            changes.get(
                field.name,
                getattr(submission, field.name),
            ),
        )

    return forged


def test_registry_is_immutable_and_valid() -> None:
    assert isinstance(
        OPERATOR_SANDBOX_INTAKE_CONTRACTS,
        MappingProxyType,
    )
    assert len(OPERATOR_SANDBOX_INTAKE_CONTRACTS) == 1
    assert SUPPORTED_OPERATOR_SANDBOX_INTAKES == (
        INTAKE_ID,
    )
    assert validate_operator_sandbox_intake_registry() == ()

    with pytest.raises(TypeError):
        OPERATOR_SANDBOX_INTAKE_CONTRACTS[
            "forged_intake"
        ] = get_operator_sandbox_intake_contract(
            INTAKE_ID
        )


def test_list_and_get_preserve_contract_identity() -> None:
    listed = list_operator_sandbox_intake_contracts()

    assert len(listed) == 1
    assert listed[0] is get_operator_sandbox_intake_contract(
        INTAKE_ID
    )


def test_contract_declares_exact_pending_scope() -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    assert contract.connector_id == (
        "telecom_ticketing_reference"
    )
    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"
    assert contract.required_operator_inputs == (
        REQUIRED_INPUT_NAMES
    )
    assert contract.status is (
        OperatorSandboxIntakeStatus.PENDING_OPERATOR_INPUT
    )


@pytest.mark.parametrize(
    "contract_type",
    (
        OperatorSandboxIntakeContract,
        OperatorSandboxReferenceSubmission,
        OperatorSandboxIntakeAssessment,
    ),
)
def test_contracts_are_frozen_slotted_dataclasses(
    contract_type: type[object],
) -> None:
    assert is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True
    assert hasattr(contract_type, "__slots__")


def test_contract_instance_is_frozen() -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        contract.production_allowed = True


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " intake_reference",
        "intake_reference ",
        "https://operator.invalid/api",
        "http://operator.invalid/api",
        "bearer raw_value",
        "basic raw_value",
        "password=raw_value",
        "token=raw_value",
        "secret=raw_value",
        "private_key=raw_value",
        "certificate=raw_value",
        "client_secret=raw_value",
        "api_key=raw_value",
        "raw_payload=raw_value",
    ),
)
def test_normalizer_rejects_raw_or_invalid_reference(
    value: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_operator_sandbox_intake_id(value)


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_operator_sandbox_intake_id(
            object()
        )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_FIELDS,
)
def test_contract_rejects_disabled_required_flag(
    field_name: str,
) -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    with pytest.raises(ValueError):
        replace(contract, **{field_name: False})


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_FIELDS,
)
def test_contract_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    with pytest.raises(ValueError):
        replace(contract, **{field_name: True})


def test_contract_rejects_non_sandbox_environment() -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    with pytest.raises(ValueError):
        replace(contract, environment="production")


def test_contract_rejects_write_access() -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    with pytest.raises(ValueError):
        replace(contract, access_mode="write")


def test_contract_validation_detects_duplicate() -> None:
    contract = get_operator_sandbox_intake_contract(
        INTAKE_ID
    )

    issues = validate_operator_sandbox_intake_contracts(
        (contract, contract)
    )

    assert any(
        "duplicate_intake_id" in issue
        for issue in issues
    )

@pytest.mark.parametrize(
    "field_name",
    REQUIRED_INPUT_NAMES,
)
def test_submission_rejects_raw_input_reference(
    field_name: str,
) -> None:
    submission = _submission()

    with pytest.raises(ValueError):
        replace(
            submission,
            **{
                field_name: (
                    "https://operator.invalid/raw"
                )
            },
        )


def test_submission_rejects_wrong_intake() -> None:
    submission = _submission()

    with pytest.raises(ValueError):
        replace(
            submission,
            intake_id="unknown_intake_reference",
        )


def test_pending_assessment_records_all_missing_inputs() -> None:
    assessment = assess_operator_sandbox_intake(
        INTAKE_ID
    )

    assert assessment.status is (
        OperatorSandboxIntakeStatus.PENDING_OPERATOR_INPUT
    )
    assert assessment.contract_valid is True
    assert assessment.submission_present is False
    assert assessment.reference_count == 0
    assert assessment.required_reference_count == 10
    assert assessment.references_valid is False
    assert assessment.ready_for_reference_review is False

    for input_name in REQUIRED_INPUT_NAMES:
        assert (
            f"{input_name}_pending"
            in assessment.blocker_codes
        )

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_reference_submission_is_received_for_review_only() -> None:
    assessment = assess_operator_sandbox_intake(
        INTAKE_ID,
        _submission(),
    )

    assert assessment.status is (
        OperatorSandboxIntakeStatus
        .REFERENCES_RECEIVED_FOR_REVIEW
    )
    assert assessment.contract_valid is True
    assert assessment.submission_present is True
    assert assessment.reference_count == 10
    assert assessment.required_reference_count == 10
    assert assessment.references_valid is True
    assert assessment.ready_for_reference_review is True

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_assessment_is_deterministic() -> None:
    submission = _submission()

    assert assess_operator_sandbox_intake(
        INTAKE_ID,
        submission,
    ) == assess_operator_sandbox_intake(
        INTAKE_ID,
        submission,
    )


def test_assessment_rejects_wrong_submission_type() -> None:
    with pytest.raises(TypeError):
        assess_operator_sandbox_intake(
            INTAKE_ID,
            object(),
        )


def test_forged_mismatched_submission_is_blocked() -> None:
    forged = _forge_submission(
        _submission(),
        intake_id="unknown_intake_reference",
    )

    assessment = assess_operator_sandbox_intake(
        INTAKE_ID,
        forged,
    )

    assert assessment.status is (
        OperatorSandboxIntakeStatus.BLOCKED
    )
    assert assessment.submission_present is True
    assert assessment.references_valid is False
    assert assessment.ready_for_reference_review is False

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_unknown_intake_is_rejected() -> None:
    with pytest.raises(KeyError):
        assess_operator_sandbox_intake(
            "unknown_intake_reference"
        )


def test_submission_contains_references_not_raw_material() -> None:
    names = {
        field.name
        for field in fields(
            OperatorSandboxReferenceSubmission
        )
    }

    prohibited = {
        "endpoint",
        "url",
        "password",
        "token",
        "secret",
        "private_key",
        "certificate",
        "payload",
        "headers",
        "authorization",
    }

    assert names.isdisjoint(prohibited)
    assert all(
        name.endswith("_reference")
        or name in {"submission_id", "intake_id"}
        for name in names
    )


def test_module_has_no_environment_network_or_io_access() -> None:
    source = inspect.getsource(intake_module)
    tree = ast.parse(source)

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
        "os",
    }

    forbidden_calls = {
        "open",
        "sleep",
        "urlopen",
        "create_task",
        "getenv",
    }

    module_hits = []
    call_hits = []

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

        if isinstance(node, ast.Call):
            function = node.func

            if isinstance(function, ast.Name):
                name = function.id
            elif isinstance(function, ast.Attribute):
                name = function.attr
            else:
                name = ""

            if name in forbidden_calls:
                call_hits.append(
                    (node.lineno, name)
                )

    assert module_hits == []
    assert call_hits == []


def test_public_export_list_covers_intake_surface() -> None:
    expected = {
        "OPERATOR_SANDBOX_INTAKE_CONTRACTS",
        "SUPPORTED_OPERATOR_SANDBOX_INTAKES",
        "OperatorSandboxIntakeAssessment",
        "OperatorSandboxIntakeContract",
        "OperatorSandboxIntakeStatus",
        "OperatorSandboxReferenceSubmission",
        "assess_operator_sandbox_intake",
        "get_operator_sandbox_intake_contract",
        "list_operator_sandbox_intake_contracts",
        "normalize_operator_sandbox_intake_id",
        "validate_operator_sandbox_intake_contracts",
        "validate_operator_sandbox_intake_registry",
    }

    assert set(intake_module.__all__) == expected


def test_package_exports_16f_r1_public_surface() -> None:
    expected = set(intake_module.__all__)

    assert expected.issubset(
        set(integration_package.__all__)
    )

    for name in expected:
        assert hasattr(integration_package, name)


def test_16f_r1_documentation_records_safety_markers(
) -> None:
    documentation = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16F_R1.md"
    ).read_text(encoding="utf-8")

    required = (
        "EXTERNAL-CONNECTIVITY-16F-R1",
        "pending_operator_input",
        "references_received_for_review",
        "endpoint_reference",
        "auth_method_reference",
        "secret_provider_reference",
        "tls_policy_reference",
        "allowlist_reference",
        "kill_switch_reference",
        "endpoint_registered=False",
        "target_binding_created=False",
        "secret_reference_registered=False",
        "credentials_resolved=False",
        "external_http_enabled=False",
        "request_execution_allowed=False",
        "persistence_allowed=False",
        "runtime_enabled=False",
        "production_allowed=False",
        "automatic_activation_allowed=False",
        "EXTERNAL-CONNECTIVITY-16F-R2",
    )

    missing = tuple(
        marker
        for marker in required
        if marker not in documentation
    )

    assert missing == ()
