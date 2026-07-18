from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.connector_bindings import (
    CONNECTOR_ENVIRONMENT_BINDINGS,
    CONNECTOR_SECRET_REFERENCES,
    CONNECTOR_TARGET_REFERENCES,
)
from processual_api.integrations.connector_registry import (
    RUNTIME_CONNECTOR_CONTRACTS,
)
from processual_api.integrations.operation_plans import (
    CONNECTOR_OPERATION_PLANS,
)
from processual_api.integrations.sandbox_pilot import (
    CONNECTOR_SANDBOX_PILOT_CONTRACTS,
    SUPPORTED_CONNECTOR_SANDBOX_PILOT_CONTRACTS,
    ConnectorSandboxPilotAssessment,
    ConnectorSandboxPilotContract,
    ConnectorSandboxPilotStatus,
    assess_connector_sandbox_pilot,
    get_connector_sandbox_pilot_contract,
    list_connector_sandbox_pilot_contracts,
    normalize_connector_sandbox_pilot_id,
    validate_connector_sandbox_pilot_contracts,
    validate_connector_sandbox_pilot_registry,
)

SOURCE_PATH = Path(
    "processual_api/integrations/sandbox_pilot.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R1.md"
)

PILOT_ID = "telecom_ticketing_read_only_sandbox_pilot"

SELECTED_PLAN_ID = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)

CANDIDATE_PLAN_IDS = (
    "telecom_ticketing_reference_sandbox_helpdesk_read_operation_plan",
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan",
)

REQUIRED_INPUT_IDS = (
    "approved_sandbox_endpoint_reference",
    "operator_or_customer_approval_reference",
    "external_api_name_reference",
    "external_api_version_reference",
    "authentication_method_reference",
    "secret_manager_reference",
    "test_tenant_reference",
    "data_classification_reference",
    "allowed_scope_reference",
    "rate_limit_reference",
    "timeout_policy_reference",
    "retention_policy_reference",
    "audit_owner_reference",
    "incident_contact_reference",
    "acceptance_criteria_reference",
)

EXECUTION_FLAGS = (
    "action_execution_allowed",
    "runtime_enabled",
    "external_http_enabled",
    "production_allowed",
    "automatic_activation_allowed",
    "credentials_resolved",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _pilot() -> ConnectorSandboxPilotContract:
    return get_connector_sandbox_pilot_contract(
        PILOT_ID
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


def test_registry_contains_exactly_one_governed_pilot() -> None:
    assert len(CONNECTOR_SANDBOX_PILOT_CONTRACTS) == 1
    assert tuple(CONNECTOR_SANDBOX_PILOT_CONTRACTS) == (
        PILOT_ID,
    )
    assert SUPPORTED_CONNECTOR_SANDBOX_PILOT_CONTRACTS == (
        PILOT_ID,
    )
    assert (
        type(CONNECTOR_SANDBOX_PILOT_CONTRACTS).__name__
        == "mappingproxy"
    )


def test_registry_validation_has_no_issues() -> None:
    assert validate_connector_sandbox_pilot_registry() == ()


def test_list_and_get_return_the_same_contract() -> None:
    contracts = list_connector_sandbox_pilot_contracts()

    assert contracts == (_pilot(),)


def test_pilot_id_normalization_is_safe() -> None:
    assert normalize_connector_sandbox_pilot_id(
        f"  {PILOT_ID.upper()}  "
    ) == PILOT_ID


def test_unknown_pilot_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_connector_sandbox_pilot_contract(
            "unknown_sandbox_pilot"
        )


def test_contract_is_frozen_and_slotted() -> None:
    contract = _pilot()

    assert contract.__dataclass_params__.frozen is True
    assert not hasattr(contract, "__dict__")

    with pytest.raises(FrozenInstanceError):
        contract.environment = "production"


def test_assessment_is_frozen_and_slotted() -> None:
    assessment = assess_connector_sandbox_pilot(
        PILOT_ID
    )

    assert assessment.__dataclass_params__.frozen is True
    assert not hasattr(assessment, "__dict__")

    with pytest.raises(FrozenInstanceError):
        assessment.dispatch_allowed = True


def test_contract_selects_ticket_read_plan() -> None:
    contract = _pilot()

    assert contract.selected_plan_id == SELECTED_PLAN_ID
    assert contract.candidate_plan_ids == CANDIDATE_PLAN_IDS
    assert len(contract.candidate_plan_ids) == 2


def test_contract_is_read_only_sandbox_only() -> None:
    contract = _pilot()

    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"
    assert contract.sandbox_only is True
    assert contract.read_only is True
    assert contract.operator_approval_required is True
    assert contract.customer_approval_required is True
    assert contract.status is (
        ConnectorSandboxPilotStatus.PENDING_OPERATOR_INPUT
    )


def test_contract_references_existing_binding_graph() -> None:
    contract = _pilot()

    assert contract.connector_id == (
        "telecom_ticketing_reference"
    )
    assert contract.binding_id == (
        "telecom_ticketing_reference_sandbox_binding"
    )
    assert contract.target_reference_id == (
        "telecom_ticketing_reference_sandbox_target_reference"
    )
    assert contract.secret_reference_ids == (
        "telecom_operations_api_reference_secret_reference",
    )
    assert contract.credential_profile_ids == (
        "telecom_operations_api_reference",
    )


def test_required_input_catalog_is_exact_and_unique() -> None:
    contract = _pilot()

    assert contract.required_input_ids == REQUIRED_INPUT_IDS
    assert len(contract.required_input_ids) == 15
    assert len(set(contract.required_input_ids)) == 15


def test_contract_contains_no_endpoint_or_secret_value_field() -> None:
    field_names = {
        definition.name
        for definition in fields(ConnectorSandboxPilotContract)
    }

    prohibited_fields = {
        "endpoint",
        "endpoint_url",
        "url",
        "secret",
        "secret_value",
        "token",
        "password",
        "credential",
        "credentials",
        "payload",
        "raw_payload",
        "headers",
    }

    assert field_names.isdisjoint(prohibited_fields)


def test_selected_runtime_connector_remains_disabled() -> None:
    connector = RUNTIME_CONNECTOR_CONTRACTS[
        "telecom_ticketing_reference"
    ]

    assert connector.external_api_version == (
        "pending_operator_input"
    )
    assert connector.read_allowed is False
    assert connector.write_allowed is False
    assert connector.runtime_enabled is False
    assert connector.external_http_enabled is False
    assert connector.production_allowed is False
    assert connector.automatic_activation_allowed is False
    assert connector.credentials_storage_allowed is False
    assert connector.raw_secret_visible is False


def test_candidate_plans_are_safe_read_only_sandbox_plans() -> None:
    contract = _pilot()

    for plan_id in contract.candidate_plan_ids:
        plan = CONNECTOR_OPERATION_PLANS[plan_id]

        assert plan.connector_id == contract.connector_id
        assert plan.binding_id == contract.binding_id
        assert _enum_value(plan.environment) == "sandbox"
        assert _enum_value(plan.access_mode) == "read"
        assert _enum_value(plan.status) == "planning_only"
        assert plan.steps
        assert (
            _enum_value(plan.steps[-1].step_kind)
            == "block_dispatch"
        )

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


def test_selected_plan_uses_ticket_read_scope() -> None:
    plan = CONNECTOR_OPERATION_PLANS[SELECTED_PLAN_ID]

    assert plan.capability_id == "ticket.read"
    assert plan.scope_id == "ticket:read"
    assert _enum_value(plan.access_mode) == "read"


def test_sandbox_binding_remains_pending_and_disabled() -> None:
    binding = CONNECTOR_ENVIRONMENT_BINDINGS[
        "telecom_ticketing_reference_sandbox_binding"
    ]

    assert _enum_value(binding.environment) == "sandbox"
    assert _enum_value(binding.approval_status) == (
        "pending_operator_input"
    )
    assert _enum_value(binding.validation_status) == (
        "unvalidated"
    )
    assert binding.configured is False
    assert binding.validated is False
    assert binding.approved is False
    assert binding.runtime_enabled is False
    assert binding.external_http_enabled is False
    assert binding.production_allowed is False
    assert binding.automatic_activation_allowed is False
    assert binding.credentials_resolved is False


def test_sandbox_target_remains_reference_only() -> None:
    target = CONNECTOR_TARGET_REFERENCES[
        "telecom_ticketing_reference_sandbox_target_reference"
    ]

    assert _enum_value(target.environment) == "sandbox"
    assert target.target_alias == (
        "telecom_ticketing_reference_sandbox_pending_target"
    )
    assert target.endpoint_reference_name == (
        "telecom_ticketing_reference_sandbox_endpoint_reference"
    )
    assert target.configured is False
    assert target.validated is False
    assert target.approved is False
    assert target.runtime_enabled is False
    assert target.external_http_enabled is False
    assert target.production_allowed is False


def test_secret_reference_contains_no_value() -> None:
    secret_reference = CONNECTOR_SECRET_REFERENCES[
        "telecom_operations_api_reference_secret_reference"
    ]

    assert secret_reference.credential_profile_id == (
        "telecom_operations_api_reference"
    )
    assert secret_reference.required is True
    assert secret_reference.customer_supplied is True
    assert secret_reference.value_stored is False
    assert secret_reference.raw_secret_visible is False
    assert secret_reference.credentials_resolved is False
    assert secret_reference.runtime_enabled is False
    assert secret_reference.production_allowed is False


def test_assessment_is_pending_operator_input() -> None:
    assessment = assess_connector_sandbox_pilot(
        PILOT_ID
    )

    assert assessment.status is (
        ConnectorSandboxPilotStatus.PENDING_OPERATOR_INPUT
    )
    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.operator_inputs_complete is False
    assert assessment.customer_approval_present is False
    assert assessment.operator_approval_present is False


def test_assessment_preserves_all_execution_blocks() -> None:
    assessment = assess_connector_sandbox_pilot(
        PILOT_ID
    )

    assert assessment.credentials_resolved is False
    assert assessment.runtime_enabled is False
    assert assessment.external_http_enabled is False
    assert assessment.dispatch_allowed is False
    assert assessment.production_allowed is False
    assert assessment.action_execution_allowed is False


def test_assessment_reports_expected_blockers() -> None:
    assessment = assess_connector_sandbox_pilot(
        PILOT_ID
    )

    expected_blockers = {
        "operator_inputs_pending",
        "customer_approval_pending",
        "operator_approval_pending",
        "external_api_version_pending",
        "runtime_disabled",
        "external_http_disabled",
        "sandbox_binding_unconfigured",
        "sandbox_binding_unvalidated",
        "sandbox_binding_unapproved",
        "sandbox_target_unconfigured",
        "sandbox_target_unvalidated",
        "sandbox_target_unapproved",
        "secret_reference_unresolved",
    }

    assert set(assessment.blocker_codes) == expected_blockers


def test_assessment_is_deterministic() -> None:
    first = assess_connector_sandbox_pilot(PILOT_ID)
    second = assess_connector_sandbox_pilot(PILOT_ID)

    assert first == second


@pytest.mark.parametrize(
    "unsafe_change",
    (
        {"environment": "production"},
        {"access_mode": "write"},
        {"sandbox_only": False},
        {"read_only": False},
        {"operator_approval_required": False},
        {"customer_approval_required": False},
    ),
)
def test_contract_rejects_unsafe_identity_changes(
    unsafe_change: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(
            _pilot(),
            **unsafe_change,
        )


@pytest.mark.parametrize("flag_name", EXECUTION_FLAGS)
def test_contract_rejects_every_execution_flag(
    flag_name: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _pilot(),
            **{flag_name: True},
        )


@pytest.mark.parametrize(
    "flag_name",
    (
        "configured",
        "validated",
        "approved",
    ),
)
def test_contract_rejects_premature_readiness_flags(
    flag_name: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _pilot(),
            **{flag_name: True},
        )


def test_contract_rejects_selected_plan_outside_candidates() -> None:
    with pytest.raises(ValueError):
        replace(
            _pilot(),
            selected_plan_id="unlisted_plan",
        )


def test_custom_contract_validator_rejects_duplicates() -> None:
    contract = _pilot()

    issues = validate_connector_sandbox_pilot_contracts(
        (
            contract,
            contract,
        )
    )

    assert (
        f"{PILOT_ID}:duplicate_pilot_id"
        in issues
    )


def test_assessment_contract_contains_no_raw_material_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorSandboxPilotAssessment
        )
    }

    assert "endpoint" not in field_names
    assert "url" not in field_names
    assert "secret_value" not in field_names
    assert "token" not in field_names
    assert "password" not in field_names
    assert "payload" not in field_names


def test_pilot_assessment_does_not_mutate_existing_registries() -> None:
    connector_before = tuple(
        RUNTIME_CONNECTOR_CONTRACTS.items()
    )
    binding_before = tuple(
        CONNECTOR_ENVIRONMENT_BINDINGS.items()
    )
    target_before = tuple(
        CONNECTOR_TARGET_REFERENCES.items()
    )
    secret_before = tuple(
        CONNECTOR_SECRET_REFERENCES.items()
    )
    plans_before = tuple(
        CONNECTOR_OPERATION_PLANS.items()
    )

    assess_connector_sandbox_pilot(PILOT_ID)

    assert tuple(RUNTIME_CONNECTOR_CONTRACTS.items()) == (
        connector_before
    )
    assert tuple(CONNECTOR_ENVIRONMENT_BINDINGS.items()) == (
        binding_before
    )
    assert tuple(CONNECTOR_TARGET_REFERENCES.items()) == (
        target_before
    )
    assert tuple(CONNECTOR_SECRET_REFERENCES.items()) == (
        secret_before
    )
    assert tuple(CONNECTOR_OPERATION_PLANS.items()) == (
        plans_before
    )


def test_source_contains_no_network_or_execution_primitive() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    banned_import_roots = {
        "aiohttp",
        "fastapi",
        "httpx",
        "multiprocessing",
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
        "concurrent.futures.ProcessPoolExecutor",
        "concurrent.futures.ThreadPoolExecutor",
        "json.dump",
        "open",
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


def test_package_exports_16e_r1_contracts() -> None:
    assert (
        integrations.CONNECTOR_SANDBOX_PILOT_CONTRACTS
        is CONNECTOR_SANDBOX_PILOT_CONTRACTS
    )
    assert (
        integrations.ConnectorSandboxPilotContract
        is ConnectorSandboxPilotContract
    )
    assert (
        integrations.ConnectorSandboxPilotAssessment
        is ConnectorSandboxPilotAssessment
    )
    assert (
        integrations.ConnectorSandboxPilotStatus
        is ConnectorSandboxPilotStatus
    )
    assert (
        integrations.assess_connector_sandbox_pilot
        is assess_connector_sandbox_pilot
    )


def test_document_declares_required_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "read-only",
        "sandbox-only",
        "pending_operator_input",
        "no network",
        "no endpoint value",
        "no credential value",
        "no secret resolution",
        "no persistence",
        "no route",
        "no worker",
        "no dispatch",
        "no production",
        "customer approval required",
        "operator approval required",
        "ticket:read",
    )

    for marker in required_markers:
        assert marker in document
