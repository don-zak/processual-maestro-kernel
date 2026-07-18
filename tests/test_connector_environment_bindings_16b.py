from dataclasses import FrozenInstanceError, replace

import pytest

from processual_api.integrations.connector_bindings import (
    CONNECTOR_ENVIRONMENT_BINDINGS,
    CONNECTOR_SECRET_REFERENCES,
    CONNECTOR_TARGET_REFERENCES,
    ConnectorEnvironmentBinding,
    ConnectorSecretReference,
    ConnectorTargetReference,
    get_connector_environment_binding,
    get_connector_secret_reference,
    get_connector_target_reference,
    list_connector_environment_bindings,
    list_connector_secret_references,
    list_connector_target_references,
    validate_connector_binding_contracts,
    validate_connector_binding_registry,
)
from processual_api.integrations.connector_registry import (
    list_runtime_connector_contracts,
)


def test_16b_registry_is_complete_and_valid() -> None:
    assert len(CONNECTOR_TARGET_REFERENCES) == 22
    assert len(CONNECTOR_SECRET_REFERENCES) == 7
    assert len(CONNECTOR_ENVIRONMENT_BINDINGS) == 22
    assert validate_connector_binding_registry() == ()


def test_every_connector_environment_has_one_target_and_binding() -> None:
    expected_pairs = {
        (connector.connector_id, environment)
        for connector in list_runtime_connector_contracts()
        for environment in connector.supported_environments
    }
    target_pairs = {
        (reference.connector_id, reference.environment)
        for reference in list_connector_target_references()
    }
    binding_pairs = {
        (binding.connector_id, binding.environment)
        for binding in list_connector_environment_bindings()
    }

    assert target_pairs == expected_pairs
    assert binding_pairs == expected_pairs


def test_target_references_are_unresolved_and_default_deny() -> None:
    for reference in list_connector_target_references():
        assert reference.target_alias.endswith("_pending_target")
        assert reference.endpoint_reference_name.endswith(
            "_endpoint_reference"
        )
        assert "://" not in reference.target_alias
        assert "://" not in reference.endpoint_reference_name
        assert reference.configured is False
        assert reference.validated is False
        assert reference.approved is False
        assert reference.runtime_enabled is False
        assert reference.external_http_enabled is False
        assert reference.production_allowed is False


def test_secret_references_never_store_or_resolve_secret_values() -> None:
    expected_profiles = {
        profile_id
        for connector in list_runtime_connector_contracts()
        for profile_id in connector.authentication_profile_ids
    }
    actual_profiles = {
        reference.credential_profile_id
        for reference in list_connector_secret_references()
    }

    assert actual_profiles == expected_profiles

    for reference in list_connector_secret_references():
        assert reference.reference_kind == "customer_vault_reference"
        assert reference.provider_reference_name.endswith(
            "_pending_vault_reference"
        )
        assert reference.required is True
        assert reference.customer_supplied is True
        assert reference.value_stored is False
        assert reference.raw_secret_visible is False
        assert reference.credentials_resolved is False
        assert reference.runtime_enabled is False
        assert reference.production_allowed is False


def test_environment_bindings_remain_unapproved_and_non_runtime() -> None:
    target_ids = set(CONNECTOR_TARGET_REFERENCES)
    secret_ids = set(CONNECTOR_SECRET_REFERENCES)

    for binding in list_connector_environment_bindings():
        assert binding.target_reference_id in target_ids
        assert set(binding.secret_reference_ids).issubset(secret_ids)
        assert binding.required_operator_inputs
        assert binding.approval_status == "pending_operator_input"
        assert binding.validation_status == "unvalidated"
        assert binding.configured is False
        assert binding.validated is False
        assert binding.approved is False
        assert binding.runtime_enabled is False
        assert binding.external_http_enabled is False
        assert binding.production_allowed is False
        assert binding.automatic_activation_allowed is False
        assert binding.credentials_resolved is False


def test_registry_objects_are_immutable() -> None:
    target = list_connector_target_references()[0]
    secret = list_connector_secret_references()[0]
    binding = list_connector_environment_bindings()[0]

    with pytest.raises(FrozenInstanceError):
        target.target_alias = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        secret.provider_reference_name = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        binding.approved = True  # type: ignore[misc]

    with pytest.raises(TypeError):
        CONNECTOR_TARGET_REFERENCES["new"] = target  # type: ignore[index]


def test_getters_normalize_ids_and_reject_unknown_values() -> None:
    target = list_connector_target_references()[0]
    secret = list_connector_secret_references()[0]
    binding = list_connector_environment_bindings()[0]

    assert (
        get_connector_target_reference(
            target.target_reference_id.upper().replace("_", "-")
        )
        is target
    )
    assert (
        get_connector_secret_reference(
            secret.secret_reference_id.upper().replace("_", "-")
        )
        is secret
    )
    assert (
        get_connector_environment_binding(
            binding.binding_id.upper().replace("_", "-")
        )
        is binding
    )

    with pytest.raises(KeyError):
        get_connector_target_reference("missing")

    with pytest.raises(KeyError):
        get_connector_secret_reference("missing")

    with pytest.raises(KeyError):
        get_connector_environment_binding("missing")


def test_target_reference_rejects_literal_endpoint() -> None:
    with pytest.raises(ValueError):
        ConnectorTargetReference(
            target_reference_id="invalid_target_reference",
            connector_id="telecom_crm_reference",
            environment="sandbox",
            target_alias="https://customer.example",
            endpoint_reference_name="pending_endpoint_reference",
        )


def test_target_reference_rejects_enabled_runtime_flags() -> None:
    with pytest.raises(ValueError, match="external_http_enabled=True"):
        ConnectorTargetReference(
            target_reference_id="invalid_target_reference",
            connector_id="telecom_crm_reference",
            environment="sandbox",
            target_alias="pending_target",
            endpoint_reference_name="pending_endpoint_reference",
            external_http_enabled=True,
        )


def test_secret_reference_rejects_raw_or_resolved_material() -> None:
    with pytest.raises(ValueError, match="raw_secret_visible=True"):
        ConnectorSecretReference(
            secret_reference_id="invalid_secret_reference",
            credential_profile_id="telecom_operations_api_reference",
            reference_kind="customer_vault_reference",
            provider_reference_name="pending_vault_reference",
            raw_secret_visible=True,
        )

    with pytest.raises(ValueError, match="credentials_resolved=True"):
        ConnectorSecretReference(
            secret_reference_id="invalid_secret_reference",
            credential_profile_id="telecom_operations_api_reference",
            reference_kind="customer_vault_reference",
            provider_reference_name="pending_vault_reference",
            credentials_resolved=True,
        )


def test_binding_rejects_approval_or_runtime_enablement() -> None:
    with pytest.raises(ValueError, match="approved=True"):
        ConnectorEnvironmentBinding(
            binding_id="invalid_binding",
            connector_id="telecom_crm_reference",
            environment="sandbox",
            target_reference_id=(
                "telecom_crm_reference_sandbox_target_reference"
            ),
            secret_reference_ids=(
                "telecom_operations_api_reference_secret_reference",
            ),
            required_operator_inputs=("approved_target_alias",),
            approved=True,
        )

    with pytest.raises(ValueError, match="production_allowed=True"):
        ConnectorEnvironmentBinding(
            binding_id="invalid_binding",
            connector_id="telecom_crm_reference",
            environment="production",
            target_reference_id=(
                "telecom_crm_reference_production_target_reference"
            ),
            secret_reference_ids=(
                "telecom_operations_api_reference_secret_reference",
            ),
            required_operator_inputs=("approved_target_alias",),
            production_allowed=True,
        )


def test_contract_validation_detects_duplicate_ids() -> None:
    targets = list_connector_target_references()
    secrets = list_connector_secret_references()
    bindings = list_connector_environment_bindings()

    issues = validate_connector_binding_contracts(
        targets + (targets[0],),
        secrets + (secrets[0],),
        bindings + (bindings[0],),
    )

    assert "Connector target reference ids must be unique." in issues
    assert "Connector secret reference ids must be unique." in issues
    assert "Connector environment binding ids must be unique." in issues


def test_contract_validation_detects_unknown_target_reference() -> None:
    bindings = list(list_connector_environment_bindings())
    bindings[0] = replace(
        bindings[0],
        target_reference_id="missing_target_reference",
    )

    issues = validate_connector_binding_contracts(
        list_connector_target_references(),
        list_connector_secret_references(),
        tuple(bindings),
    )

    assert any("references an unknown target" in issue for issue in issues)


def test_contract_validation_detects_secret_profile_mismatch() -> None:
    bindings = list(list_connector_environment_bindings())
    replacement_secret = next(
        reference
        for reference in list_connector_secret_references()
        if reference.credential_profile_id
        != "telecom_operations_api_reference"
    )
    telecom_binding_index = next(
        index
        for index, binding in enumerate(bindings)
        if binding.connector_id == "telecom_crm_reference"
    )
    bindings[telecom_binding_index] = replace(
        bindings[telecom_binding_index],
        secret_reference_ids=(replacement_secret.secret_reference_id,),
    )

    issues = validate_connector_binding_contracts(
        list_connector_target_references(),
        list_connector_secret_references(),
        tuple(bindings),
    )

    assert any(
        "secret references do not match" in issue for issue in issues
    )


def test_integration_package_exports_16b_contracts() -> None:
    import processual_api.integrations as integrations

    assert integrations.ConnectorTargetReference is ConnectorTargetReference
    assert integrations.ConnectorSecretReference is ConnectorSecretReference
    assert integrations.ConnectorEnvironmentBinding is ConnectorEnvironmentBinding
    assert (
        integrations.validate_connector_binding_registry
        is validate_connector_binding_registry
    )


def test_16b_document_preserves_control_plane_guardrails() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "integrations"
        / "EXTERNAL_CONNECTIVITY_16B.md"
    ).read_text(encoding="utf-8").lower()

    expected_markers = (
        "external-connectivity-16b",
        "22 target references",
        "7 secret references",
        "22 environment bindings",
        "no customer endpoint url",
        "no secret value",
        "external_http_enabled=false",
        "runtime_enabled=false",
        "production_allowed=false",
        "credentials_resolved=false",
        "raw_secret_visible=false",
        "pending_operator_input",
        "unvalidated",
        "control plane metadata only",
    )

    for marker in expected_markers:
        assert marker in text


def test_contracts_reject_unknown_connector_and_profile_references() -> None:
    with pytest.raises(KeyError):
        ConnectorTargetReference(
            target_reference_id="unknown_target_reference",
            connector_id="unknown_connector",
            environment="sandbox",
            target_alias="pending_target",
            endpoint_reference_name="pending_endpoint_reference",
        )

    with pytest.raises(KeyError):
        ConnectorSecretReference(
            secret_reference_id="unknown_secret_reference",
            credential_profile_id="unknown_profile",
            reference_kind="customer_vault_reference",
            provider_reference_name="pending_vault_reference",
        )
