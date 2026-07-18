from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
)
from processual_api.integrations.operation_plans import (
    get_connector_operation_plan,
)
from processual_api.integrations.sandbox_pilot import (
    assess_connector_sandbox_pilot,
    get_connector_sandbox_pilot_contract,
)
from processual_api.integrations.secret_manager_contracts import (
    assess_connector_secret_manager_contract,
    get_connector_secret_manager_contract,
)
from processual_api.integrations.transport_contracts import (
    CONNECTOR_TRANSPORT_CONTRACTS,
    SUPPORTED_CONNECTOR_TRANSPORT_CONTRACTS,
    ConnectorNoNetworkTransport,
    ConnectorTransport,
    ConnectorTransportAssessment,
    ConnectorTransportContract,
    ConnectorTransportContractStatus,
    ConnectorTransportMode,
    ConnectorTransportRequest,
    ConnectorTransportResult,
    ConnectorTransportResultStatus,
    assess_connector_transport_contract,
    get_connector_transport_contract,
    list_connector_transport_contracts,
    normalize_connector_transport_id,
    validate_connector_transport_contracts,
    validate_connector_transport_registry,
)

SOURCE_PATH = Path(
    "processual_api/integrations/transport_contracts.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R3.md"
)

TRANSPORT_ID = (
    "telecom_ticketing_disabled_no_network_transport"
)

PILOT_ID = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

SECRET_MANAGER_CONTRACT_ID = (
    "telecom_operations_customer_vault_secret_manager_contract"
)

PLAN_ID = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)

HELPDESK_PLAN_ID = (
    "telecom_ticketing_reference_sandbox_helpdesk_read_operation_plan"
)

UNSAFE_CONTRACT_FLAGS = (
    "transport_registered",
    "transport_validated",
    "request_execution_allowed",
    "secret_access_allowed",
    "credentials_resolution_allowed",
    "dispatch_allowed",
    "external_http_allowed",
    "socket_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "runtime_enabled",
    "production_allowed",
)

UNSAFE_RESULT_FLAGS = (
    "transport_attempted",
    "dispatch_attempted",
    "operation_executed",
    "secret_accessed",
    "credentials_resolved",
    "external_http_used",
    "socket_used",
    "payload_persisted",
    "background_task_created",
    "production_used",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _contract() -> ConnectorTransportContract:
    return get_connector_transport_contract(
        TRANSPORT_ID
    )


def _dispatch_request(
    *,
    plan_id: str = PLAN_ID,
    simulation_mode: bool = True,
) -> ConnectorDispatchRequest:
    return ConnectorDispatchRequest(
        request_id="dispatch_request_reference",
        plan_id=plan_id,
        operation_id="sandbox_ticket_read_operation_reference",
        tenant_reference="tenant_reference",
        payload_hash="sha256_payload_reference",
        idempotency_key="idempotency_reference",
        requested_at_reference="requested_at_reference",
        expires_at_reference="expires_at_reference",
        requester_reference="requester_reference",
        approval_reference="approval_reference",
        simulation_mode=simulation_mode,
    )


def _transport_request(
    *,
    transport_id: str = TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorTransportRequest:
    return ConnectorTransportRequest(
        request_id="transport_request_reference",
        transport_id=transport_id,
        dispatch_request=_dispatch_request(
            plan_id=plan_id,
        ),
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


def test_registry_contains_exactly_one_transport() -> None:
    assert len(CONNECTOR_TRANSPORT_CONTRACTS) == 1
    assert tuple(CONNECTOR_TRANSPORT_CONTRACTS) == (
        TRANSPORT_ID,
    )
    assert SUPPORTED_CONNECTOR_TRANSPORT_CONTRACTS == (
        TRANSPORT_ID,
    )
    assert (
        type(CONNECTOR_TRANSPORT_CONTRACTS).__name__
        == "mappingproxy"
    )


def test_registry_validation_has_no_issues() -> None:
    assert validate_connector_transport_registry() == ()


def test_list_and_get_return_same_transport() -> None:
    assert list_connector_transport_contracts() == (
        _contract(),
    )


def test_transport_id_normalization_is_safe() -> None:
    assert normalize_connector_transport_id(
        f"  {TRANSPORT_ID.upper()}  "
    ) == TRANSPORT_ID


def test_unknown_transport_lookup_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_connector_transport_contract(
            "unknown_transport"
        )


def test_contract_is_frozen_and_slotted() -> None:
    contract = _contract()

    assert contract.__dataclass_params__.frozen is True
    assert not hasattr(contract, "__dict__")

    with pytest.raises(FrozenInstanceError):
        contract.runtime_enabled = True


def test_assessment_is_frozen_and_slotted() -> None:
    assessment = assess_connector_transport_contract(
        TRANSPORT_ID
    )

    assert assessment.__dataclass_params__.frozen is True
    assert not hasattr(assessment, "__dict__")

    with pytest.raises(FrozenInstanceError):
        assessment.external_http_allowed = True


def test_request_is_frozen_and_slotted() -> None:
    request = _transport_request()

    assert request.__dataclass_params__.frozen is True
    assert not hasattr(request, "__dict__")

    with pytest.raises(FrozenInstanceError):
        request.transport_id = "other_transport"


def test_result_is_frozen_and_slotted() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request()
    )

    assert result.__dataclass_params__.frozen is True
    assert not hasattr(result, "__dict__")

    with pytest.raises(FrozenInstanceError):
        result.transport_attempted = True


def test_no_network_transport_implements_protocol() -> None:
    transport = ConnectorNoNetworkTransport()

    assert isinstance(transport, ConnectorTransport)


def test_contract_identity_is_exact() -> None:
    contract = _contract()

    assert contract.transport_id == TRANSPORT_ID
    assert contract.pilot_id == PILOT_ID
    assert contract.secret_manager_contract_id == (
        SECRET_MANAGER_CONTRACT_ID
    )
    assert contract.plan_id == PLAN_ID
    assert contract.connector_id == (
        "telecom_ticketing_reference"
    )
    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"


def test_contract_type_references_are_exact() -> None:
    contract = _contract()

    assert contract.request_type_reference == (
        "ConnectorDispatchRequest"
    )
    assert contract.response_type_reference == (
        "ConnectorTransportResult"
    )


def test_contract_mode_and_status_are_disabled() -> None:
    contract = _contract()

    assert contract.mode is (
        ConnectorTransportMode
        .DISABLED_NO_NETWORK_INTERFACE
    )
    assert contract.status is (
        ConnectorTransportContractStatus.DISABLED
    )


def test_contract_requires_safe_governance() -> None:
    contract = _contract()

    assert contract.sandbox_only is True
    assert contract.read_only is True
    assert contract.reference_only_request_required is True
    assert contract.deterministic_blocking_required is True
    assert contract.customer_authorization_required is True
    assert contract.operator_approval_required is True
    assert contract.security_review_required is True


def test_contract_preserves_every_unsafe_flag() -> None:
    contract = _contract()

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(contract, field_name) is False


def test_contract_contains_no_endpoint_or_secret_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorTransportContract
        )
    }

    prohibited_fields = {
        "endpoint",
        "endpoint_url",
        "url",
        "headers",
        "secret",
        "secret_value",
        "password",
        "token",
        "api_key",
        "private_key",
        "credential_value",
        "payload",
        "payload_body",
    }

    assert field_names.isdisjoint(
        prohibited_fields
    )


def test_request_contains_reference_dispatch_only() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorTransportRequest
        )
    }

    assert field_names == {
        "request_id",
        "transport_id",
        "dispatch_request",
    }


def test_request_rejects_non_simulation_dispatch() -> None:
    with pytest.raises(ValueError):
        ConnectorTransportRequest(
            request_id="transport_request_reference",
            transport_id=TRANSPORT_ID,
            dispatch_request=_dispatch_request(
                simulation_mode=False,
            ),
        )


def test_request_rejects_wrong_dispatch_type() -> None:
    with pytest.raises(TypeError):
        ConnectorTransportRequest(
            request_id="transport_request_reference",
            transport_id=TRANSPORT_ID,
            dispatch_request=object(),
        )


def test_referenced_operation_plan_is_exact() -> None:
    plan = get_connector_operation_plan(
        PLAN_ID
    )

    assert plan.connector_id == (
        "telecom_ticketing_reference"
    )
    assert _enum_value(plan.environment) == "sandbox"
    assert _enum_value(plan.access_mode) == "read"
    assert _enum_value(plan.status) == "planning_only"
    assert plan.steps
    assert (
        _enum_value(plan.steps[-1].step_kind)
        == "block_dispatch"
    )


def test_referenced_operation_plan_is_default_deny() -> None:
    plan = get_connector_operation_plan(
        PLAN_ID
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


def test_referenced_pilot_matches_transport() -> None:
    pilot = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    assert pilot.selected_plan_id == PLAN_ID
    assert pilot.connector_id == (
        "telecom_ticketing_reference"
    )
    assert pilot.environment == "sandbox"
    assert pilot.access_mode == "read"


def test_referenced_pilot_assessment_is_default_deny() -> None:
    assessment = assess_connector_sandbox_pilot(
        PILOT_ID
    )

    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.credentials_resolved is False
    assert assessment.runtime_enabled is False
    assert assessment.external_http_enabled is False
    assert assessment.dispatch_allowed is False
    assert assessment.production_allowed is False
    assert assessment.action_execution_allowed is False


def test_secret_manager_matches_transport_pilot() -> None:
    contract = get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    )

    assert contract.pilot_id == PILOT_ID
    assert contract.sandbox_only is True


def test_secret_manager_assessment_is_default_deny() -> None:
    assessment = assess_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    )

    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.reference_registered is False
    assert assessment.reference_validated is False
    assert assessment.resolution_allowed is False
    assert assessment.credentials_resolved is False
    assert assessment.value_stored is False
    assert assessment.raw_secret_visible is False
    assert assessment.runtime_enabled is False
    assert assessment.production_allowed is False


def test_transport_assessment_is_disabled_and_valid() -> None:
    assessment = assess_connector_transport_contract(
        TRANSPORT_ID
    )

    assert assessment.status is (
        ConnectorTransportContractStatus.DISABLED
    )
    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.plan_valid is True
    assert assessment.pilot_valid is True
    assert assessment.secret_manager_valid is True
    assert assessment.interface_declared is True
    assert assessment.deterministic_blocking is True
    assert assessment.no_network is True


def test_transport_assessment_preserves_unsafe_flags() -> None:
    assessment = assess_connector_transport_contract(
        TRANSPORT_ID
    )

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(assessment, field_name) is False


def test_transport_assessment_reports_expected_blockers() -> None:
    assessment = assess_connector_transport_contract(
        TRANSPORT_ID
    )

    expected_blockers = {
        "transport_disabled",
        "transport_registration_pending",
        "transport_validation_pending",
        "request_execution_disabled",
        "secret_access_disabled",
        "credential_resolution_disabled",
        "dispatch_disabled",
        "external_http_disabled",
        "socket_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "runtime_disabled",
        "production_disabled",
        "sandbox_pilot_pending",
        "secret_manager_reference_pending",
    }

    assert set(assessment.blocker_codes) == (
        expected_blockers
    )


def test_valid_request_returns_deterministic_block() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request()
    )

    assert result.status is (
        ConnectorTransportResultStatus.BLOCKED
    )
    assert result.reason_code == (
        "transport_disabled_no_network"
    )
    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.plan_validated is True
    assert result.pilot_validated is True
    assert result.secret_manager_validated is True


def test_valid_result_preserves_every_unsafe_flag() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request()
    )

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_valid_result_is_deterministic() -> None:
    transport = ConnectorNoNetworkTransport()
    request = _transport_request()

    first = transport.transmit(request)
    second = transport.transmit(request)

    assert first == second


def test_unknown_transport_returns_safe_result() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request(
            transport_id="unknown_transport_reference",
        )
    )

    assert result.status is (
        ConnectorTransportResultStatus.UNKNOWN_TRANSPORT
    )
    assert result.contract_validated is False
    assert result.request_validated is True

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_plan_mismatch_returns_safe_result() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request(
            plan_id=HELPDESK_PLAN_ID,
        )
    )

    assert result.status is (
        ConnectorTransportResultStatus.PLAN_MISMATCH
    )
    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.plan_validated is False

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_transport_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError):
        ConnectorNoNetworkTransport().transmit(
            object()
        )


@pytest.mark.parametrize(
    "unsafe_change",
    (
        {"environment": "production"},
        {"access_mode": "write"},
        {"sandbox_only": False},
        {"read_only": False},
        {"reference_only_request_required": False},
        {"deterministic_blocking_required": False},
        {"customer_authorization_required": False},
        {"operator_approval_required": False},
        {"security_review_required": False},
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


def test_contract_rejects_non_disabled_status() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            status=ConnectorTransportContractStatus.BLOCKED,
        )


def test_contract_rejects_wrong_request_type_reference() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            request_type_reference="RawHttpRequest",
        )


def test_contract_rejects_wrong_response_type_reference() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            response_type_reference="RawHttpResponse",
        )


def test_custom_validator_rejects_duplicate_contracts() -> None:
    contract = _contract()

    issues = validate_connector_transport_contracts(
        (
            contract,
            contract,
        )
    )

    assert (
        f"{TRANSPORT_ID}:duplicate_transport_id"
        in issues
    )


def test_result_rejects_enabled_unsafe_flag() -> None:
    result = ConnectorNoNetworkTransport().transmit(
        _transport_request()
    )

    with pytest.raises(ValueError):
        replace(
            result,
            external_http_used=True,
        )


def test_transport_does_not_mutate_referenced_contracts() -> None:
    plan_before = get_connector_operation_plan(
        PLAN_ID
    )

    pilot_before = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    secret_before = get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    )

    ConnectorNoNetworkTransport().transmit(
        _transport_request()
    )

    assert get_connector_operation_plan(
        PLAN_ID
    ) == plan_before

    assert get_connector_sandbox_pilot_contract(
        PILOT_ID
    ) == pilot_before

    assert get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    ) == secret_before


def test_source_contains_no_network_or_execution_primitives() -> None:
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
        "httpx.AsyncClient",
        "httpx.Client",
        "json.dump",
        "open",
        "os.getenv",
        "pathlib.Path.read_bytes",
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
        "requests.get",
        "requests.post",
        "socket.create_connection",
        "socket.socket",
        "subprocess.Popen",
        "subprocess.run",
        "urllib.request.urlopen",
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


def test_source_does_not_invoke_dispatcher() -> None:
    source = SOURCE_PATH.read_text(
        encoding="utf-8"
    )

    assert "ConnectorMockDispatcher" not in source
    assert ".dispatch(" not in source


def test_package_exports_16e_r3_contracts() -> None:
    assert (
        integrations.CONNECTOR_TRANSPORT_CONTRACTS
        is CONNECTOR_TRANSPORT_CONTRACTS
    )
    assert (
        integrations.ConnectorTransportContract
        is ConnectorTransportContract
    )
    assert (
        integrations.ConnectorTransportAssessment
        is ConnectorTransportAssessment
    )
    assert (
        integrations.ConnectorTransportRequest
        is ConnectorTransportRequest
    )
    assert (
        integrations.ConnectorTransportResult
        is ConnectorTransportResult
    )
    assert (
        integrations.ConnectorNoNetworkTransport
        is ConnectorNoNetworkTransport
    )


def test_document_declares_required_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "disabled_no_network_interface",
        "reference-only request",
        "deterministic blocked result",
        "no network",
        "no http",
        "no socket",
        "no endpoint value",
        "no secret access",
        "no credential resolution",
        "no dispatcher invocation",
        "no payload persistence",
        "no route",
        "no worker",
        "no runtime",
        "no production",
        "sandbox-only",
        "read-only",
    )

    for marker in required_markers:
        assert marker in document
