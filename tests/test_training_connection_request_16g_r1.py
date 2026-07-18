from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

from processual_api.integrations.training_connection_request import (
    SUPPORTED_TRAINING_CONNECTION_REQUESTS,
    TRAINING_CONNECTION_REQUEST_CONTRACTS,
    TrainingConnectionInputDomain,
    TrainingConnectionRequestAssessment,
    TrainingConnectionRequestContract,
    TrainingConnectionRequestStatus,
    TrainingCustomerInputItem,
    TrainingCustomerInputPackage,
    assess_training_connection_request,
    build_training_customer_input_package,
    get_training_connection_request_contract,
    list_training_connection_request_contracts,
    normalize_training_connection_request_id,
    render_training_customer_input_request,
    validate_training_connection_request_contracts,
    validate_training_connection_request_registry,
)

REQUEST_ID = "telecom_ticketing_training_connection_request"

PROVIDER_INPUT_IDS = (
    "provider.selected_secret_provider",
    "provider.environment_reference",
    "provider.tenant_project_or_vault_reference",
    "provider.authentication_method_reference",
    "provider.provider_reference",
    "provider.secret_reference",
    "provider.rotation_policy_reference",
    "provider.revocation_policy_reference",
    "provider.customer_authorization_reference",
    "provider.operator_approval_reference",
    "provider.security_review_reference",
    "provider.sdk_dependency_authorization_reference",
    "provider.network_access_authorization_reference",
    "provider.sandbox_credential_issuance_reference",
    "provider.credential_revocation_test_plan_reference",
)

OUTBOUND_INPUT_IDS = (
    "outbound.allowlist_reference",
    "outbound.host_reference",
    "outbound.dns_policy_reference",
    "outbound.port_policy_reference",
    "outbound.tls_minimum_version_selection",
    "outbound.ca_policy_reference",
    "outbound.certificate_pinning_policy_reference",
    "outbound.proxy_policy_reference",
    "outbound.egress_authorization_reference",
    "outbound.security_review_reference",
    "outbound.operator_approval_reference",
    "outbound.kill_switch_reference",
)

UNSAFE_FIELDS = (
    "customer_submission_received",
    "customer_submission_persisted",
    "integration_task_created",
    "activation_permission_key_issued",
    "provider_binding_created",
    "credentials_resolved",
    "allowlist_applied",
    "tls_context_created",
    "connection_attempted",
    "fake_transport_invoked",
    "sandbox_launched",
    "evidence_bundle_created",
    "external_http_enabled",
    "socket_access_enabled",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)

MODULE_PATH = Path(
    "processual_api/integrations/training_connection_request.py"
)


def test_registry_is_immutable_and_valid() -> None:
    assert isinstance(
        TRAINING_CONNECTION_REQUEST_CONTRACTS,
        MappingProxyType,
    )
    assert validate_training_connection_request_registry() == ()
    assert SUPPORTED_TRAINING_CONNECTION_REQUESTS == (REQUEST_ID,)


def test_list_and_get_preserve_contract_identity() -> None:
    contracts = list_training_connection_request_contracts()

    assert len(contracts) == 1
    assert contracts[0] is get_training_connection_request_contract(
        REQUEST_ID
    )


def test_contract_links_r1_r2a_and_r3a() -> None:
    contract = get_training_connection_request_contract(REQUEST_ID)

    assert contract.intake_id == (
        "telecom_ticketing_operator_sandbox_reference_intake"
    )
    assert contract.provider_readiness_id == (
        "telecom_ticketing_secret_provider_binding_readiness"
    )
    assert contract.outbound_readiness_id == (
        "telecom_ticketing_outbound_allowlist_tls_readiness"
    )
    assert contract.connector_id == "telecom_ticketing_reference"
    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"
    assert contract.status is TrainingConnectionRequestStatus.DRAFT_REQUEST
    assert contract.training_only is True
    assert contract.reference_only is True
    assert contract.required_input_ids == (
        *PROVIDER_INPUT_IDS,
        *OUTBOUND_INPUT_IDS,
    )

    for name in UNSAFE_FIELDS:
        assert getattr(contract, name) is False


@pytest.mark.parametrize(
    "model",
    (
        TrainingConnectionRequestContract,
        TrainingCustomerInputItem,
        TrainingCustomerInputPackage,
        TrainingConnectionRequestAssessment,
    ),
)
def test_models_are_frozen_slotted_dataclasses(
    model: type[object],
) -> None:
    assert is_dataclass(model)
    assert "__slots__" in model.__dict__


def test_contract_is_immutable() -> None:
    contract = get_training_connection_request_contract(REQUEST_ID)

    with pytest.raises((FrozenInstanceError, AttributeError)):
        contract.runtime_enabled = True


@pytest.mark.parametrize("field_name", UNSAFE_FIELDS)
def test_contract_rejects_unsafe_enablement(
    field_name: str,
) -> None:
    contract = get_training_connection_request_contract(REQUEST_ID)

    with pytest.raises(
        ValueError,
        match=rf"{field_name} must remain false",
    ):
        replace(contract, **{field_name: True})


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    (
        ("environment", "production", "remain sandbox"),
        ("access_mode", "write", "remain read"),
        ("intake_id", "forged_intake", "reference R1"),
        (
            "provider_readiness_id",
            "forged_provider_readiness",
            "reference R2A",
        ),
        (
            "outbound_readiness_id",
            "forged_outbound_readiness",
            "reference R3A",
        ),
        ("connector_id", "forged_connector", "remain governed"),
    ),
)
def test_contract_rejects_changed_governed_reference(
    field_name: str,
    value: str,
    message: str,
) -> None:
    contract = get_training_connection_request_contract(REQUEST_ID)

    with pytest.raises(ValueError, match=message):
        replace(contract, **{field_name: value})


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " leading",
        "trailing ",
        "https://operator.invalid",
        "bearer forged",
        "password=forged",
        "token=forged",
        "secret=forged",
        "private_key=forged",
        "api_key=forged",
        "raw_payload=forged",
    ),
)
def test_normalizer_rejects_invalid_or_raw_material(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        normalize_training_connection_request_id(value)


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_training_connection_request_id(7)  # type: ignore[arg-type]


def test_input_package_contains_exact_27_reference_items() -> None:
    package = build_training_customer_input_package(REQUEST_ID)

    assert package.status is (
        TrainingConnectionRequestStatus.PACKAGE_READY_FOR_CUSTOMER
    )
    assert package.input_count == 27
    assert len(package.items) == 27
    assert tuple(item.item_id for item in package.items) == (
        *PROVIDER_INPUT_IDS,
        *OUTBOUND_INPUT_IDS,
    )
    assert len({item.item_id for item in package.items}) == 27
    assert package.reference_only is True
    assert package.raw_values_prohibited is True
    assert package.ready_for_customer is True


def test_input_domains_and_item_invariants_are_exact() -> None:
    package = build_training_customer_input_package(REQUEST_ID)
    provider_items = package.items[: len(PROVIDER_INPUT_IDS)]
    outbound_items = package.items[len(PROVIDER_INPUT_IDS) :]

    assert all(
        item.domain is TrainingConnectionInputDomain.SECRET_PROVIDER
        for item in provider_items
    )
    assert all(
        item.domain is TrainingConnectionInputDomain.OUTBOUND_TLS
        for item in outbound_items
    )

    for item in package.items:
        assert item.required is True
        assert item.reference_only is True
        assert item.raw_value_prohibited is True
        assert "do not provide a raw value" in item.prompt


def test_package_declares_provider_and_tls_candidates() -> None:
    package = build_training_customer_input_package(REQUEST_ID)

    assert package.provider_candidates == (
        "gcp_secret_manager",
        "hashicorp_vault",
        "aws_secrets_manager",
        "azure_key_vault",
    )
    assert package.tls_candidates == ("tls_1_2", "tls_1_3")


def test_package_does_not_advance_later_training_steps() -> None:
    package = build_training_customer_input_package(REQUEST_ID)

    assert package.activation_permission_key_issued is False
    assert package.fake_transport_invoked is False
    assert package.sandbox_launched is False
    assert package.runtime_enabled is False
    assert package.production_allowed is False


def test_assessment_is_deterministic_and_default_deny() -> None:
    first = assess_training_connection_request(REQUEST_ID)
    second = assess_training_connection_request(REQUEST_ID)

    assert first == second
    assert hash(first) == hash(second)
    assert first.contract_valid is True
    assert first.dependencies_valid is True
    assert first.required_input_count == 27
    assert first.package_ready_for_customer is True
    assert first.customer_submission_received is False
    assert first.integration_task_created is False
    assert first.activation_permission_key_issued is False
    assert first.fake_transport_invoked is False
    assert first.sandbox_launched is False
    assert first.external_http_enabled is False
    assert first.socket_access_enabled is False
    assert first.runtime_enabled is False
    assert first.production_allowed is False


def test_rendered_customer_request_is_complete_and_safe() -> None:
    rendered = render_training_customer_input_request(REQUEST_ID)
    lowered = rendered.lower()

    assert rendered.endswith("\n")
    assert "required reference inputs:" in lowered
    assert "do not send passwords, tokens, keys" in lowered
    assert "does not issue an activation key" in lowered
    assert "does not launch a sandbox" in lowered
    assert "runtime_enabled: false" in lowered
    assert "production_allowed: false" in lowered

    for item_id in (*PROVIDER_INPUT_IDS, *OUTBOUND_INPUT_IDS):
        assert item_id in rendered


def test_contract_validation_detects_empty_duplicate_and_wrong_type() -> None:
    contract = get_training_connection_request_contract(REQUEST_ID)

    assert validate_training_connection_request_contracts(()) == (
        "no_training_connection_request_declared",
    )
    assert validate_training_connection_request_contracts(
        (contract, contract)
    ) == (f"{REQUEST_ID}:duplicate_request_id",)

    issues = validate_training_connection_request_contracts(
        ("forged",)  # type: ignore[arg-type]
    )
    assert issues == (
        "contract_0:invalid_training_connection_request_type",
        "no_training_connection_request_declared",
    )


def test_unknown_request_is_rejected() -> None:
    with pytest.raises(
        KeyError,
        match="unknown training connection request",
    ):
        get_training_connection_request_contract("unknown_request")


def test_module_has_no_later_phase_or_runtime_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    prohibited = (
        "integration_pilot_controls",
        "fake_sandbox_transport",
        "sandbox_evidence",
        "socket",
        "ssl",
        "httpx",
        "requests",
        "aiohttp",
        "subprocess",
    )

    assert not any(
        marker in module
        for module in modules
        for marker in prohibited
    )

    for marker in (
        "issue_activation_permission_key(",
        "create_integration_task(",
        ".simulate(",
        "build_connector_sandbox_evidence_bundle(",
        "os.environ",
        "getenv(",
    ):
        assert marker not in source


def test_public_export_list_covers_direct_r1_surface() -> None:
    import processual_api.integrations.training_connection_request as module

    expected = {
        "SUPPORTED_TRAINING_CONNECTION_REQUESTS",
        "TRAINING_CONNECTION_REQUEST_CONTRACTS",
        "TrainingConnectionInputDomain",
        "TrainingConnectionRequestAssessment",
        "TrainingConnectionRequestContract",
        "TrainingConnectionRequestStatus",
        "TrainingCustomerInputItem",
        "TrainingCustomerInputPackage",
        "assess_training_connection_request",
        "build_training_customer_input_package",
        "get_training_connection_request_contract",
        "list_training_connection_request_contracts",
        "normalize_training_connection_request_id",
        "render_training_customer_input_request",
        "validate_training_connection_request_contracts",
        "validate_training_connection_request_registry",
    }

    assert set(module.__all__) == expected

    for name in expected:
        assert getattr(module, name) is not None
def test_package_exports_16g_r1_public_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "SUPPORTED_TRAINING_CONNECTION_REQUESTS",
        "TRAINING_CONNECTION_REQUEST_CONTRACTS",
        "TrainingConnectionInputDomain",
        "TrainingConnectionRequestAssessment",
        "TrainingConnectionRequestContract",
        "TrainingConnectionRequestStatus",
        "TrainingCustomerInputItem",
        "TrainingCustomerInputPackage",
        "assess_training_connection_request",
        "build_training_customer_input_package",
        "get_training_connection_request_contract",
        "list_training_connection_request_contracts",
        "normalize_training_connection_request_id",
        "render_training_customer_input_request",
        "validate_training_connection_request_contracts",
        "validate_training_connection_request_registry",
    }

    assert expected.issubset(set(package.__all__))
    for name in expected:
        assert getattr(package, name) is not None


def test_16g_r1_documentation_records_training_boundary() -> None:
    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16G_R1.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    for marker in (
        "input_package_ready_for_customer",
        "27 governed inputs",
        "15 secret-provider",
        "12 outbound",
        "raw_value_prohibited=true",
        "does not",
        "activation_permission_key_issued",
        "fake_transport_invoked",
        "sandbox_launched",
        "external_http_enabled",
        "socket_access_enabled",
        "runtime_enabled",
        "production_allowed",
        "parallel key system",
        "parallel transport",
    ):
        assert marker in lowered
