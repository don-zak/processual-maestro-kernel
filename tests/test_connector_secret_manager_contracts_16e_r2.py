from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.connector_bindings import (
    get_connector_secret_reference,
)
from processual_api.integrations.credential_profiles import (
    get_credential_profile,
)
from processual_api.integrations.sandbox_pilot import (
    get_connector_sandbox_pilot_contract,
)
from processual_api.integrations.secret_manager_contracts import (
    CONNECTOR_SECRET_MANAGER_CONTRACTS,
    SUPPORTED_CONNECTOR_SECRET_MANAGER_CONTRACTS,
    ConnectorSecretManagerAssessment,
    ConnectorSecretManagerContract,
    ConnectorSecretManagerMode,
    ConnectorSecretManagerStatus,
    assess_connector_secret_manager_contract,
    get_connector_secret_manager_contract,
    list_connector_secret_manager_contracts,
    normalize_connector_secret_manager_contract_id,
    validate_connector_secret_manager_contracts,
    validate_connector_secret_manager_registry,
)

SOURCE_PATH = Path(
    "processual_api/integrations/secret_manager_contracts.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R2.md"
)

CONTRACT_ID = (
    "telecom_operations_customer_vault_secret_manager_contract"
)

PILOT_ID = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

SECRET_REFERENCE_ID = (
    "telecom_operations_api_reference_secret_reference"
)

CREDENTIAL_PROFILE_ID = (
    "telecom_operations_api_reference"
)

PROVIDER_REFERENCE_NAME = (
    "telecom_operations_api_reference_pending_vault_reference"
)

SUPPORTED_AUTH_METHODS = (
    "api_key_reference",
    "oauth_client_reference",
    "mtls_certificate_reference",
    "customer_vault_reference",
)

FORBIDDEN_SECRET_MATERIAL = (
    "raw API key values",
    "raw OAuth client secrets",
    "raw passwords",
    "raw access tokens",
    "raw refresh tokens",
    "private key material",
    "certificate private keys",
    "webhook signing secret values",
    "database connection strings",
)

REQUIRED_CUSTOMER_INPUTS = (
    "api_documentation",
    "sandbox_access",
    "test_credentials_policy",
    "scope_matrix",
    "technical_contact",
    "acceptance_criteria",
    "security_requirements",
    "credential_owner",
    "rotation_policy",
    "customer_endpoint_inventory",
)

REQUIRED_SECURITY_CONTROLS = (
    "enterprise_review",
    "security_review",
    "sandbox_before_production",
    "least_privilege_scopes",
    "supervisor_approval_for_production_credentials",
    "no_raw_secrets_in_support_notes",
    "customer_vault_or_reference_storage",
    "audit_logging_required",
)

UNSAFE_CONTRACT_FLAGS = (
    "reference_registered",
    "reference_validated",
    "customer_authorization_present",
    "operator_approval_present",
    "security_review_completed",
    "rotation_policy_confirmed",
    "resolution_allowed",
    "credentials_resolved",
    "value_stored",
    "raw_secret_visible",
    "runtime_enabled",
    "production_allowed",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _contract() -> ConnectorSecretManagerContract:
    return get_connector_secret_manager_contract(
        CONTRACT_ID
    )


def _dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    current: ast.AST | None = node

    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    return ".".join(reversed(parts))


def test_registry_contains_one_contract() -> None:
    assert len(CONNECTOR_SECRET_MANAGER_CONTRACTS) == 1
    assert tuple(CONNECTOR_SECRET_MANAGER_CONTRACTS) == (
        CONTRACT_ID,
    )
    assert SUPPORTED_CONNECTOR_SECRET_MANAGER_CONTRACTS == (
        CONTRACT_ID,
    )
    assert (
        type(CONNECTOR_SECRET_MANAGER_CONTRACTS).__name__
        == "mappingproxy"
    )


def test_registry_validation_has_no_issues() -> None:
    assert validate_connector_secret_manager_registry() == ()


def test_list_and_get_return_same_contract() -> None:
    assert list_connector_secret_manager_contracts() == (
        _contract(),
    )


def test_contract_id_normalization_is_safe() -> None:
    normalized = (
        normalize_connector_secret_manager_contract_id(
            f"  {CONTRACT_ID.upper()}  "
        )
    )

    assert normalized == CONTRACT_ID


def test_unknown_contract_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_connector_secret_manager_contract(
            "unknown_secret_manager_contract"
        )


def test_contract_is_frozen_and_slotted() -> None:
    contract = _contract()

    assert contract.__dataclass_params__.frozen is True
    assert not hasattr(contract, "__dict__")

    with pytest.raises(FrozenInstanceError):
        contract.runtime_enabled = True


def test_assessment_is_frozen_and_slotted() -> None:
    assessment = (
        assess_connector_secret_manager_contract(
            CONTRACT_ID
        )
    )

    assert assessment.__dataclass_params__.frozen is True
    assert not hasattr(assessment, "__dict__")

    with pytest.raises(FrozenInstanceError):
        assessment.credentials_resolved = True


def test_contract_identity_is_exact() -> None:
    contract = _contract()

    assert contract.contract_id == CONTRACT_ID
    assert contract.pilot_id == PILOT_ID
    assert contract.secret_reference_id == (
        SECRET_REFERENCE_ID
    )
    assert contract.credential_profile_id == (
        CREDENTIAL_PROFILE_ID
    )
    assert contract.provider_reference_name == (
        PROVIDER_REFERENCE_NAME
    )
    assert contract.reference_kind == (
        "customer_vault_reference"
    )


def test_contract_mode_and_status_are_pending() -> None:
    contract = _contract()

    assert contract.mode is (
        ConnectorSecretManagerMode
        .CUSTOMER_MANAGED_VAULT_REFERENCE
    )
    assert contract.status is (
        ConnectorSecretManagerStatus
        .PENDING_CUSTOMER_VAULT_REFERENCE
    )


def test_contract_requires_governance() -> None:
    contract = _contract()

    assert contract.customer_supplied is True
    assert contract.customer_authorization_required is True
    assert contract.operator_approval_required is True
    assert contract.security_review_required is True
    assert contract.rotation_policy_required is True
    assert contract.sandbox_only is True


def test_supported_auth_methods_are_exact() -> None:
    assert _contract().supported_auth_methods == (
        SUPPORTED_AUTH_METHODS
    )


def test_forbidden_secret_material_is_exact() -> None:
    assert _contract().forbidden_secret_material == (
        FORBIDDEN_SECRET_MATERIAL
    )


def test_required_customer_inputs_are_exact() -> None:
    assert _contract().required_customer_inputs == (
        REQUIRED_CUSTOMER_INPUTS
    )


def test_required_security_controls_are_exact() -> None:
    assert _contract().required_security_controls == (
        REQUIRED_SECURITY_CONTROLS
    )


def test_contract_contains_no_secret_value_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorSecretManagerContract
        )
    }

    prohibited_fields = {
        "secret",
        "secret_value",
        "raw_secret",
        "password",
        "password_value",
        "token",
        "token_value",
        "api_key",
        "api_key_value",
        "private_key",
        "credential_value",
        "payload",
        "headers",
        "endpoint_url",
    }

    assert field_names.isdisjoint(
        prohibited_fields
    )


def test_existing_secret_reference_matches_contract() -> None:
    contract = _contract()

    secret_reference = get_connector_secret_reference(
        SECRET_REFERENCE_ID
    )

    assert secret_reference.credential_profile_id == (
        contract.credential_profile_id
    )
    assert secret_reference.provider_reference_name == (
        contract.provider_reference_name
    )
    assert _enum_value(
        secret_reference.reference_kind
    ) == contract.reference_kind
    assert secret_reference.required is True
    assert secret_reference.customer_supplied is True


def test_existing_secret_reference_remains_unresolved() -> None:
    secret_reference = get_connector_secret_reference(
        SECRET_REFERENCE_ID
    )

    assert secret_reference.value_stored is False
    assert secret_reference.raw_secret_visible is False
    assert secret_reference.credentials_resolved is False
    assert secret_reference.runtime_enabled is False
    assert secret_reference.production_allowed is False


def test_existing_credential_profile_matches_contract() -> None:
    contract = _contract()

    profile = get_credential_profile(
        CREDENTIAL_PROFILE_ID
    )

    supported_auth_methods = tuple(
        _enum_value(value)
        for value in profile.supported_auth_methods
    )

    assert supported_auth_methods == (
        contract.supported_auth_methods
    )
    assert profile.forbidden_secret_material == (
        contract.forbidden_secret_material
    )
    assert profile.required_customer_inputs == (
        contract.required_customer_inputs
    )
    assert profile.required_security_controls == (
        contract.required_security_controls
    )


def test_existing_credential_profile_remains_blocked() -> None:
    profile = get_credential_profile(
        CREDENTIAL_PROFILE_ID
    )

    assert profile.rotation_policy_required is True
    assert profile.sandbox_required is True
    assert (
        profile.production_credential_approval_required
        is True
    )
    assert profile.technical_contact_required is True
    assert profile.security_review_required is True
    assert profile.customer_endpoint_inventory_required is True
    assert profile.approved_for_runtime is False


def test_sandbox_pilot_references_secret_contract_graph() -> None:
    pilot = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    assert SECRET_REFERENCE_ID in (
        pilot.secret_reference_ids
    )
    assert CREDENTIAL_PROFILE_ID in (
        pilot.credential_profile_ids
    )
    assert pilot.environment == "sandbox"
    assert pilot.access_mode == "read"
    assert pilot.sandbox_only is True
    assert pilot.read_only is True


def test_sandbox_pilot_remains_default_deny() -> None:
    pilot = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    assert pilot.configured is False
    assert pilot.validated is False
    assert pilot.approved is False
    assert pilot.action_execution_allowed is False
    assert pilot.runtime_enabled is False
    assert pilot.external_http_enabled is False
    assert pilot.production_allowed is False
    assert pilot.automatic_activation_allowed is False
    assert pilot.credentials_resolved is False


def test_contract_preserves_every_unsafe_flag_as_false() -> None:
    contract = _contract()

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(contract, field_name) is False


def test_assessment_is_pending_customer_reference() -> None:
    assessment = (
        assess_connector_secret_manager_contract(
            CONTRACT_ID
        )
    )

    assert assessment.status is (
        ConnectorSecretManagerStatus
        .PENDING_CUSTOMER_VAULT_REFERENCE
    )
    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.provider_reference_pending is True


def test_assessment_preserves_every_unsafe_flag() -> None:
    assessment = (
        assess_connector_secret_manager_contract(
            CONTRACT_ID
        )
    )

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(assessment, field_name) is False


def test_assessment_reports_expected_blockers() -> None:
    assessment = (
        assess_connector_secret_manager_contract(
            CONTRACT_ID
        )
    )

    expected_blockers = {
        "customer_vault_reference_pending",
        "reference_registration_pending",
        "reference_validation_pending",
        "customer_authorization_pending",
        "operator_approval_pending",
        "security_review_pending",
        "rotation_policy_pending",
        "secret_resolution_disabled",
        "runtime_disabled",
        "production_disabled",
    }

    assert set(assessment.blocker_codes) == (
        expected_blockers
    )


def test_assessment_is_deterministic() -> None:
    first = assess_connector_secret_manager_contract(
        CONTRACT_ID
    )

    second = assess_connector_secret_manager_contract(
        CONTRACT_ID
    )

    assert first == second


@pytest.mark.parametrize(
    "unsafe_change",
    (
        {"reference_kind": "api_key_value"},
        {"customer_supplied": False},
        {"customer_authorization_required": False},
        {"operator_approval_required": False},
        {"security_review_required": False},
        {"rotation_policy_required": False},
        {"sandbox_only": False},
    ),
)
def test_contract_rejects_unsafe_identity_changes(
    unsafe_change: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            **unsafe_change,
        )


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_CONTRACT_FLAGS,
)
def test_contract_rejects_enabled_unsafe_flags(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            **{field_name: True},
        )


def test_contract_rejects_non_pending_status() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            status=ConnectorSecretManagerStatus.BLOCKED,
        )


def test_contract_rejects_non_pending_provider_reference() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            provider_reference_name=(
                "telecom_operations_registered_reference"
            ),
        )


def test_contract_rejects_duplicate_reference_catalog() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            supported_auth_methods=(
                "customer_vault_reference",
                "customer_vault_reference",
            ),
        )


def test_custom_validator_rejects_duplicate_contracts() -> None:
    contract = _contract()

    issues = validate_connector_secret_manager_contracts(
        (
            contract,
            contract,
        )
    )

    assert (
        f"{CONTRACT_ID}:duplicate_contract_id"
        in issues
    )


def test_assessment_contract_has_no_value_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorSecretManagerAssessment
        )
    }

    prohibited_fields = {
        "secret",
        "secret_value",
        "password",
        "token",
        "api_key",
        "private_key",
        "credential_value",
        "payload",
    }

    assert field_names.isdisjoint(
        prohibited_fields
    )


def test_assessment_does_not_mutate_referenced_contracts() -> None:
    secret_before = get_connector_secret_reference(
        SECRET_REFERENCE_ID
    )

    profile_before = get_credential_profile(
        CREDENTIAL_PROFILE_ID
    )

    pilot_before = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    assess_connector_secret_manager_contract(
        CONTRACT_ID
    )

    assert get_connector_secret_reference(
        SECRET_REFERENCE_ID
    ) == secret_before

    assert get_credential_profile(
        CREDENTIAL_PROFILE_ID
    ) == profile_before

    assert get_connector_sandbox_pilot_contract(
        PILOT_ID
    ) == pilot_before


def test_source_contains_no_secret_resolution_primitive() -> None:
    source = SOURCE_PATH.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    banned_import_roots = {
        "aiohttp",
        "azure",
        "boto3",
        "cryptography",
        "fastapi",
        "google",
        "hvac",
        "httpx",
        "keyring",
        "multiprocessing",
        "os",
        "redis",
        "requests",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "starlette",
        "subprocess",
        "threading",
        "urllib3",
    }

    banned_modules = {
        "http.client",
        "urllib.request",
    }

    banned_calls = {
        "asyncio.create_task",
        "base64.b64decode",
        "concurrent.futures.ProcessPoolExecutor",
        "concurrent.futures.ThreadPoolExecutor",
        "json.dump",
        "open",
        "os.getenv",
        "pathlib.Path.read_bytes",
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
    }

    import_hits: list[str] = []
    call_hits: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]

                if (
                    root in banned_import_roots
                    or alias.name in banned_modules
                ):
                    import_hits.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]

            if (
                root in banned_import_roots
                or module in banned_modules
            ):
                import_hits.append(module)

        elif isinstance(node, ast.Call):
            call_name = _dotted_name(node.func)

            if call_name in banned_calls:
                call_hits.append(call_name)

    assert import_hits == []
    assert call_hits == []


def test_package_exports_16e_r2_contracts() -> None:
    assert (
        integrations.CONNECTOR_SECRET_MANAGER_CONTRACTS
        is CONNECTOR_SECRET_MANAGER_CONTRACTS
    )
    assert (
        integrations.ConnectorSecretManagerContract
        is ConnectorSecretManagerContract
    )
    assert (
        integrations.ConnectorSecretManagerAssessment
        is ConnectorSecretManagerAssessment
    )
    assert (
        integrations.ConnectorSecretManagerMode
        is ConnectorSecretManagerMode
    )
    assert (
        integrations.ConnectorSecretManagerStatus
        is ConnectorSecretManagerStatus
    )
    assert (
        integrations.assess_connector_secret_manager_contract
        is assess_connector_secret_manager_contract
    )


def test_document_declares_required_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "customer-managed vault reference",
        "pending_customer_vault_reference",
        "no secret value",
        "no secret resolution",
        "no environment-variable lookup",
        "no network",
        "no credential logging",
        "no persistence",
        "no route",
        "no worker",
        "no runtime",
        "no production",
        "customer authorization required",
        "operator approval required",
        "security review required",
        "rotation policy required",
    )

    for marker in required_markers:
        assert marker in document
