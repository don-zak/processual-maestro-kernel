"""Tests for disabled secret-provider binding readiness R2A."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import processual_api.integrations as integration_package
import processual_api.integrations.secret_provider_binding_readiness as readiness_module
from processual_api.integrations.secret_provider_binding_readiness import (
    SECRET_PROVIDER_BINDING_READINESS_CONTRACTS,
    SUPPORTED_SECRET_PROVIDER_BINDING_READINESS,
    SecretProviderBindingReadinessAssessment,
    SecretProviderBindingReadinessContract,
    SecretProviderBindingReadinessStatus,
    SecretProviderKind,
    SecretProviderReferenceSubmission,
    assess_secret_provider_binding_readiness,
    get_secret_provider_binding_readiness_contract,
    list_secret_provider_binding_readiness_contracts,
    normalize_secret_provider_binding_readiness_id,
    validate_secret_provider_binding_readiness_contracts,
    validate_secret_provider_binding_readiness_registry,
)

READINESS_ID = (
    "telecom_ticketing_secret_provider_binding_readiness"
)

CANDIDATE_PROVIDERS = (
    SecretProviderKind.GCP_SECRET_MANAGER,
    SecretProviderKind.HASHICORP_VAULT,
    SecretProviderKind.AWS_SECRETS_MANAGER,
    SecretProviderKind.AZURE_KEY_VAULT,
)

REQUIRED_REFERENCE_NAMES = (
    "provider_reference",
    "authentication_reference",
    "rotation_policy_reference",
    "customer_authorization_reference",
    "operator_approval_reference",
    "security_review_reference",
    "revocation_policy_reference",
)

REQUIRED_TRUE_FIELDS = (
    "sandbox_only",
    "reference_only",
    "customer_supplied",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
    "rotation_policy_required",
    "revocation_policy_required",
)

UNSAFE_FIELDS = (
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


def _submission(
    provider_kind: SecretProviderKind = (
        SecretProviderKind.GCP_SECRET_MANAGER
    ),
) -> SecretProviderReferenceSubmission:
    return SecretProviderReferenceSubmission(
        submission_id="provider_submission_reference",
        readiness_id=READINESS_ID,
        provider_kind=provider_kind,
        provider_reference="provider_registry_reference",
        authentication_reference="provider_auth_reference",
        rotation_policy_reference="rotation_policy_reference",
        customer_authorization_reference=(
            "customer_authorization_pending_reference"
        ),
        operator_approval_reference=(
            "operator_approval_pending_reference"
        ),
        security_review_reference=(
            "security_review_pending_reference"
        ),
        revocation_policy_reference=(
            "revocation_policy_reference"
        ),
    )


def _forge_submission(
    submission: SecretProviderReferenceSubmission,
    **changes: object,
) -> SecretProviderReferenceSubmission:
    forged = object.__new__(
        SecretProviderReferenceSubmission
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
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS,
        MappingProxyType,
    )
    assert len(
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS
    ) == 1
    assert SUPPORTED_SECRET_PROVIDER_BINDING_READINESS == (
        READINESS_ID,
    )
    assert (
        validate_secret_provider_binding_readiness_registry()
        == ()
    )

    with pytest.raises(TypeError):
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS[
            "forged_readiness"
        ] = get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )


def test_list_and_get_preserve_contract_identity() -> None:
    listed = list_secret_provider_binding_readiness_contracts()

    assert len(listed) == 1
    assert listed[0] is (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )


def test_contract_declares_pending_provider_selection() -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    assert contract.environment == "sandbox"
    assert contract.selected_provider is (
        SecretProviderKind.PENDING_SELECTION
    )
    assert contract.candidate_providers == CANDIDATE_PROVIDERS
    assert (
        contract.required_references
        == REQUIRED_REFERENCE_NAMES
    )
    assert contract.status is (
        SecretProviderBindingReadinessStatus
        .PENDING_PROVIDER_REFERENCE
    )


@pytest.mark.parametrize(
    "contract_type",
    (
        SecretProviderBindingReadinessContract,
        SecretProviderReferenceSubmission,
        SecretProviderBindingReadinessAssessment,
    ),
)
def test_contracts_are_frozen_slotted_dataclasses(
    contract_type: type[object],
) -> None:
    assert is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True
    assert hasattr(contract_type, "__slots__")


def test_contract_instance_is_frozen() -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        contract.production_allowed = True


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " readiness_reference",
        "readiness_reference ",
        "https://provider.invalid/path",
        "http://provider.invalid/path",
        "bearer raw_value",
        "basic raw_value",
        "password=raw_value",
        "token=raw_value",
        "secret=raw_value",
        "client_secret=raw_value",
        "private_key=raw_value",
        "certificate=raw_value",
        "service_account=raw_value",
        "api_key=raw_value",
        "raw_value=value",
        "raw_payload=value",
    ),
)
def test_normalizer_rejects_raw_or_invalid_reference(
    value: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_secret_provider_binding_readiness_id(
            value
        )


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_secret_provider_binding_readiness_id(
            object()
        )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_FIELDS,
)
def test_contract_rejects_disabled_required_flag(
    field_name: str,
) -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
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
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    with pytest.raises(ValueError):
        replace(contract, **{field_name: True})


def test_contract_rejects_real_provider_as_declared_state() -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    with pytest.raises(ValueError):
        replace(
            contract,
            selected_provider=(
                SecretProviderKind.GCP_SECRET_MANAGER
            ),
        )


def test_contract_rejects_production_environment() -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    with pytest.raises(ValueError):
        replace(contract, environment="production")


def test_contract_validation_detects_duplicate() -> None:
    contract = (
        get_secret_provider_binding_readiness_contract(
            READINESS_ID
        )
    )

    issues = (
        validate_secret_provider_binding_readiness_contracts(
            (contract, contract)
        )
    )

    assert any(
        "duplicate_readiness_id" in issue
        for issue in issues
    )

@pytest.mark.parametrize(
    "provider_kind",
    CANDIDATE_PROVIDERS,
)
def test_each_candidate_provider_is_received_for_review(
    provider_kind: SecretProviderKind,
) -> None:
    assessment = assess_secret_provider_binding_readiness(
        READINESS_ID,
        _submission(provider_kind),
    )

    assert assessment.status is (
        SecretProviderBindingReadinessStatus
        .REFERENCES_RECEIVED_FOR_REVIEW
    )
    assert assessment.provider_selected is True
    assert (
        assessment.selected_provider_reference
        == provider_kind.value
    )
    assert assessment.reference_count == 7
    assert assessment.required_reference_count == 7
    assert assessment.references_valid is True
    assert assessment.ready_for_provider_review is True

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_submission_rejects_pending_provider_kind() -> None:
    with pytest.raises(ValueError):
        _submission(
            SecretProviderKind.PENDING_SELECTION
        )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_REFERENCE_NAMES,
)
def test_submission_rejects_raw_reference(
    field_name: str,
) -> None:
    submission = _submission()

    with pytest.raises(ValueError):
        replace(
            submission,
            **{
                field_name: (
                    "https://provider.invalid/raw"
                )
            },
        )


def test_submission_rejects_wrong_readiness_id() -> None:
    submission = _submission()

    with pytest.raises(ValueError):
        replace(
            submission,
            readiness_id="unknown_readiness_reference",
        )


def test_pending_assessment_is_default_deny() -> None:
    assessment = assess_secret_provider_binding_readiness(
        READINESS_ID
    )

    assert assessment.status is (
        SecretProviderBindingReadinessStatus
        .PENDING_PROVIDER_REFERENCE
    )
    assert assessment.contract_valid is True
    assert assessment.intake_reference_valid is True
    assert assessment.submission_present is False
    assert assessment.provider_selected is False
    assert assessment.reference_count == 0
    assert assessment.required_reference_count == 7
    assert assessment.references_valid is False
    assert assessment.ready_for_provider_review is False

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_assessment_is_deterministic() -> None:
    submission = _submission()

    assert assess_secret_provider_binding_readiness(
        READINESS_ID,
        submission,
    ) == assess_secret_provider_binding_readiness(
        READINESS_ID,
        submission,
    )


def test_assessment_rejects_wrong_submission_type() -> None:
    with pytest.raises(TypeError):
        assess_secret_provider_binding_readiness(
            READINESS_ID,
            object(),
        )


def test_forged_mismatched_submission_is_blocked() -> None:
    forged = _forge_submission(
        _submission(),
        readiness_id="unknown_readiness_reference",
    )

    assessment = assess_secret_provider_binding_readiness(
        READINESS_ID,
        forged,
    )

    assert assessment.status is (
        SecretProviderBindingReadinessStatus.BLOCKED
    )
    assert assessment.provider_selected is False
    assert assessment.references_valid is False
    assert assessment.ready_for_provider_review is False

    for field_name in UNSAFE_FIELDS:
        assert getattr(assessment, field_name) is False


def test_unknown_readiness_is_rejected() -> None:
    with pytest.raises(KeyError):
        assess_secret_provider_binding_readiness(
            "unknown_readiness_reference"
        )


def test_submission_fields_are_reference_only() -> None:
    names = {
        field.name
        for field in fields(
            SecretProviderReferenceSubmission
        )
    }

    prohibited = {
        "secret",
        "secret_value",
        "password",
        "token",
        "client_secret",
        "private_key",
        "certificate",
        "service_account",
        "api_key",
        "endpoint",
        "url",
        "payload",
    }

    assert names.isdisjoint(prohibited)


def test_module_has_no_provider_client_or_environment_access() -> None:
    source = inspect.getsource(readiness_module)
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
        "boto3",
        "hvac",
        "google.cloud.secretmanager",
        "azure.keyvault",
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

                if (
                    alias.name in forbidden_modules
                    or root in forbidden_modules
                ):
                    module_hits.append(
                        (node.lineno, alias.name)
                    )

        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            root = module_name.split(".", 1)[0]

            if (
                module_name in forbidden_modules
                or root in forbidden_modules
            ):
                module_hits.append(
                    (node.lineno, module_name)
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


def test_public_export_list_covers_r2a_surface() -> None:
    expected = {
        "SECRET_PROVIDER_BINDING_READINESS_CONTRACTS",
        "SUPPORTED_SECRET_PROVIDER_BINDING_READINESS",
        "SecretProviderBindingReadinessAssessment",
        "SecretProviderBindingReadinessContract",
        "SecretProviderBindingReadinessStatus",
        "SecretProviderKind",
        "SecretProviderReferenceSubmission",
        "assess_secret_provider_binding_readiness",
        "get_secret_provider_binding_readiness_contract",
        "list_secret_provider_binding_readiness_contracts",
        "normalize_secret_provider_binding_readiness_id",
        "validate_secret_provider_binding_readiness_contracts",
        "validate_secret_provider_binding_readiness_registry",
    }

    assert set(readiness_module.__all__) == expected


def test_package_exports_r2a_public_surface() -> None:
    expected = set(readiness_module.__all__)

    assert expected.issubset(
        set(integration_package.__all__)
    )

    for name in expected:
        assert hasattr(integration_package, name)


def test_r2a_documentation_records_safety_markers(
) -> None:
    documentation = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16F_R2A.md"
    ).read_text(encoding="utf-8")

    required = (
        "EXTERNAL-CONNECTIVITY-16F-R2A",
        "pending_provider_reference",
        "provider_references_received_for_review",
        "gcp_secret_manager",
        "hashicorp_vault",
        "aws_secrets_manager",
        "azure_key_vault",
        "provider_binding_created=False",
        "provider_client_initialized=False",
        "secret_reference_registered=False",
        "secret_value_accessed=False",
        "raw_secret_visible=False",
        "credentials_resolved=False",
        "resolution_allowed=False",
        "external_http_enabled=False",
        "persistence_allowed=False",
        "runtime_enabled=False",
        "production_allowed=False",
        "EXTERNAL-CONNECTIVITY-16F-R2B",
    )

    missing = tuple(
        marker
        for marker in required
        if marker not in documentation
    )

    assert missing == ()
