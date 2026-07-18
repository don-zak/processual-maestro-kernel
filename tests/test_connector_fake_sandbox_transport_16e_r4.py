from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.fake_sandbox_transport import (
    CONNECTOR_FAKE_SANDBOX_CONTRACTS,
    SUPPORTED_CONNECTOR_FAKE_SANDBOX_CONTRACTS,
    ConnectorDeterministicFakeSandboxTransport,
    ConnectorFakeSandboxAssessment,
    ConnectorFakeSandboxContract,
    ConnectorFakeSandboxMode,
    ConnectorFakeSandboxRequest,
    ConnectorFakeSandboxResult,
    ConnectorFakeSandboxResultStatus,
    ConnectorFakeSandboxStatus,
    assess_connector_fake_sandbox_transport,
    get_connector_fake_sandbox_contract,
    list_connector_fake_sandbox_contracts,
    normalize_connector_fake_sandbox_transport_id,
    validate_connector_fake_sandbox_contracts,
    validate_connector_fake_sandbox_registry,
)
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
    ConnectorTransportContractStatus,
    ConnectorTransportMode,
    ConnectorTransportRequest,
    assess_connector_transport_contract,
    get_connector_transport_contract,
)

SOURCE_PATH = Path(
    "processual_api/integrations/fake_sandbox_transport.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R4.md"
)

FAKE_TRANSPORT_ID = (
    "telecom_ticketing_deterministic_fake_sandbox_transport"
)

BASE_TRANSPORT_ID = (
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

SYNTHETIC_METADATA_REFERENCES = (
    "synthetic_ticket_state_open_reference",
    "synthetic_ticket_priority_normal_reference",
    "synthetic_ticket_channel_api_reference",
    "synthetic_ticket_owner_unassigned_reference",
    "synthetic_ticket_created_at_fixed_reference",
)

UNSAFE_CONTRACT_FLAGS = (
    "real_transport_allowed",
    "request_execution_allowed",
    "payload_body_allowed",
    "secret_access_allowed",
    "credentials_resolution_allowed",
    "dispatcher_invocation_allowed",
    "external_http_allowed",
    "socket_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "runtime_enabled",
    "production_allowed",
)

UNSAFE_RESULT_FLAGS = (
    "real_transport_attempted",
    "dispatch_attempted",
    "operation_executed",
    "payload_body_used",
    "secret_accessed",
    "credentials_resolved",
    "external_http_used",
    "socket_used",
    "payload_persisted",
    "background_task_created",
    "runtime_used",
    "production_used",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _contract() -> ConnectorFakeSandboxContract:
    return get_connector_fake_sandbox_contract(
        FAKE_TRANSPORT_ID
    )


def _dispatch_request(
    *,
    plan_id: str = PLAN_ID,
) -> ConnectorDispatchRequest:
    return ConnectorDispatchRequest(
        request_id="dispatch_request_reference",
        plan_id=plan_id,
        operation_id="sandbox_ticket_read_operation_reference",
        tenant_reference="sandbox_tenant_reference",
        payload_hash="sha256_payload_reference",
        idempotency_key="idempotency_reference",
        requested_at_reference="requested_at_reference",
        expires_at_reference="expires_at_reference",
        requester_reference="requester_reference",
        approval_reference="approval_reference",
        simulation_mode=True,
    )


def _transport_request(
    *,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorTransportRequest:
    return ConnectorTransportRequest(
        request_id="transport_request_reference",
        transport_id=base_transport_id,
        dispatch_request=_dispatch_request(
            plan_id=plan_id,
        ),
    )


def _fake_request(
    *,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorFakeSandboxRequest:
    return ConnectorFakeSandboxRequest(
        request_id="fake_sandbox_request_reference",
        fake_transport_id=fake_transport_id,
        transport_request=_transport_request(
            base_transport_id=base_transport_id,
            plan_id=plan_id,
        ),
    )


def _simulate(
    *,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorFakeSandboxResult:
    return (
        ConnectorDeterministicFakeSandboxTransport()
        .simulate(
            _fake_request(
                fake_transport_id=fake_transport_id,
                base_transport_id=base_transport_id,
                plan_id=plan_id,
            )
        )
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


def test_registry_contains_exactly_one_contract() -> None:
    assert len(CONNECTOR_FAKE_SANDBOX_CONTRACTS) == 1

    assert tuple(CONNECTOR_FAKE_SANDBOX_CONTRACTS) == (
        FAKE_TRANSPORT_ID,
    )

    assert SUPPORTED_CONNECTOR_FAKE_SANDBOX_CONTRACTS == (
        FAKE_TRANSPORT_ID,
    )

    assert (
        type(CONNECTOR_FAKE_SANDBOX_CONTRACTS).__name__
        == "mappingproxy"
    )


def test_registry_validation_has_no_issues() -> None:
    assert validate_connector_fake_sandbox_registry() == ()


def test_list_and_get_return_same_contract() -> None:
    assert list_connector_fake_sandbox_contracts() == (
        _contract(),
    )


def test_fake_transport_id_normalization_is_safe() -> None:
    normalized = (
        normalize_connector_fake_sandbox_transport_id(
            f"  {FAKE_TRANSPORT_ID.upper()}  "
        )
    )

    assert normalized == FAKE_TRANSPORT_ID


def test_unknown_contract_lookup_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_connector_fake_sandbox_contract(
            "unknown_fake_transport"
        )


def test_contract_is_frozen_and_slotted() -> None:
    contract = _contract()

    assert contract.__dataclass_params__.frozen is True
    assert not hasattr(contract, "__dict__")

    with pytest.raises(FrozenInstanceError):
        contract.runtime_enabled = True


def test_assessment_is_frozen_and_slotted() -> None:
    assessment = assess_connector_fake_sandbox_transport(
        FAKE_TRANSPORT_ID
    )

    assert assessment.__dataclass_params__.frozen is True
    assert not hasattr(assessment, "__dict__")

    with pytest.raises(FrozenInstanceError):
        assessment.external_http_allowed = True


def test_request_is_frozen_and_slotted() -> None:
    request = _fake_request()

    assert request.__dataclass_params__.frozen is True
    assert not hasattr(request, "__dict__")

    with pytest.raises(FrozenInstanceError):
        request.fake_transport_id = "other_fake_transport"


def test_result_is_frozen_and_slotted() -> None:
    result = _simulate()

    assert result.__dataclass_params__.frozen is True
    assert not hasattr(result, "__dict__")

    with pytest.raises(FrozenInstanceError):
        result.external_http_used = True


def test_contract_identity_is_exact() -> None:
    contract = _contract()

    assert contract.fake_transport_id == FAKE_TRANSPORT_ID
    assert contract.base_transport_id == BASE_TRANSPORT_ID
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


def test_contract_mode_and_status_are_exact() -> None:
    contract = _contract()

    assert contract.mode is (
        ConnectorFakeSandboxMode
        .DETERMINISTIC_LOCAL_REFERENCE_ONLY
    )

    assert contract.status is (
        ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
    )

    assert contract.response_content_mode == (
        "synthetic_reference_metadata_only"
    )


def test_contract_type_references_are_exact() -> None:
    contract = _contract()

    assert contract.request_type_reference == (
        "ConnectorTransportRequest"
    )

    assert contract.response_type_reference == (
        "ConnectorFakeSandboxResult"
    )


def test_contract_requires_local_deterministic_guardrails() -> None:
    contract = _contract()

    assert contract.local_only is True
    assert contract.sandbox_only is True
    assert contract.read_only is True
    assert contract.deterministic_output_required is True
    assert contract.synthetic_reference_only is True
    assert contract.base_transport_must_remain_disabled is True
    assert contract.customer_authorization_required is True
    assert contract.operator_approval_required is True
    assert contract.security_review_required is True


def test_contract_preserves_every_unsafe_flag() -> None:
    contract = _contract()

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(contract, field_name) is False


def test_contract_contains_no_raw_transport_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorFakeSandboxContract
        )
    }

    prohibited_fields = {
        "body",
        "endpoint",
        "endpoint_url",
        "headers",
        "password",
        "payload",
        "payload_body",
        "private_key",
        "raw_secret",
        "secret",
        "secret_value",
        "token",
        "url",
    }

    assert field_names.isdisjoint(
        prohibited_fields
    )


def test_request_wraps_existing_reference_only_request() -> None:
    request = _fake_request()

    assert isinstance(
        request.transport_request,
        ConnectorTransportRequest,
    )

    assert request.transport_request.transport_id == (
        BASE_TRANSPORT_ID
    )

    assert (
        request.transport_request
        .dispatch_request
        .simulation_mode
        is True
    )


def test_request_rejects_wrong_transport_request_type() -> None:
    with pytest.raises(TypeError):
        ConnectorFakeSandboxRequest(
            request_id="fake_request_reference",
            fake_transport_id=FAKE_TRANSPORT_ID,
            transport_request=object(),
        )


def test_existing_plan_remains_default_deny() -> None:
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


def test_existing_pilot_matches_fake_contract() -> None:
    pilot = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    assert pilot.selected_plan_id == PLAN_ID
    assert pilot.connector_id == (
        "telecom_ticketing_reference"
    )
    assert pilot.environment == "sandbox"
    assert pilot.access_mode == "read"


def test_existing_pilot_assessment_remains_default_deny() -> None:
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


def test_secret_manager_matches_fake_contract() -> None:
    contract = get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    )

    assert contract.pilot_id == PILOT_ID
    assert contract.sandbox_only is True


def test_secret_manager_assessment_remains_default_deny() -> None:
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


def test_base_transport_remains_disabled() -> None:
    contract = get_connector_transport_contract(
        BASE_TRANSPORT_ID
    )

    assert contract.mode is (
        ConnectorTransportMode.DISABLED_NO_NETWORK_INTERFACE
    )

    assert contract.status is (
        ConnectorTransportContractStatus.DISABLED
    )

    assert contract.plan_id == PLAN_ID
    assert contract.pilot_id == PILOT_ID
    assert contract.secret_manager_contract_id == (
        SECRET_MANAGER_CONTRACT_ID
    )


def test_base_transport_assessment_remains_default_deny() -> None:
    assessment = assess_connector_transport_contract(
        BASE_TRANSPORT_ID
    )

    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.no_network is True
    assert assessment.transport_registered is False
    assert assessment.transport_validated is False
    assert assessment.request_execution_allowed is False
    assert assessment.secret_access_allowed is False
    assert assessment.credentials_resolution_allowed is False
    assert assessment.dispatch_allowed is False
    assert assessment.external_http_allowed is False
    assert assessment.socket_access_allowed is False
    assert assessment.persistence_allowed is False
    assert assessment.background_task_allowed is False
    assert assessment.runtime_enabled is False
    assert assessment.production_allowed is False


def test_assessment_is_ready_for_local_fake_only() -> None:
    assessment = assess_connector_fake_sandbox_transport(
        FAKE_TRANSPORT_ID
    )

    assert assessment.status is (
        ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
    )
    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.operation_plan_valid is True
    assert assessment.pilot_valid is True
    assert assessment.secret_manager_valid is True
    assert assessment.base_transport_valid is True
    assert assessment.fake_response_available is True
    assert assessment.deterministic is True
    assert assessment.local_only is True
    assert assessment.synthetic_reference_only is True
    assert assessment.no_network is True


def test_assessment_preserves_every_unsafe_flag() -> None:
    assessment = assess_connector_fake_sandbox_transport(
        FAKE_TRANSPORT_ID
    )

    for field_name in UNSAFE_CONTRACT_FLAGS:
        assert getattr(assessment, field_name) is False


def test_assessment_reports_real_execution_blocks() -> None:
    assessment = assess_connector_fake_sandbox_transport(
        FAKE_TRANSPORT_ID
    )

    expected_blockers = {
        "real_transport_disabled",
        "request_execution_disabled",
        "payload_body_disabled",
        "secret_access_disabled",
        "credential_resolution_disabled",
        "dispatcher_invocation_disabled",
        "external_http_disabled",
        "socket_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "runtime_disabled",
        "production_disabled",
    }

    assert set(assessment.blocker_codes) == (
        expected_blockers
    )


def test_valid_request_returns_synthetic_read_result() -> None:
    result = _simulate()

    assert result.status is (
        ConnectorFakeSandboxResultStatus
        .SYNTHETIC_READ_RESULT
    )

    assert result.reason_code == (
        "deterministic_synthetic_ticket_reference"
    )

    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.operation_plan_validated is True
    assert result.pilot_validated is True
    assert result.secret_manager_validated is True
    assert result.base_transport_validated is True
    assert result.synthetic_result_generated is True


def test_synthetic_result_contains_exact_reference_metadata() -> None:
    result = _simulate()

    assert result.synthetic_resource_reference == (
        "synthetic_ticket_reference"
    )

    assert result.synthetic_resource_type_reference == (
        "synthetic_ticket_resource_type_reference"
    )

    assert result.synthetic_source_reference == (
        "deterministic_local_fixture_v1_reference"
    )

    assert result.synthetic_metadata_references == (
        SYNTHETIC_METADATA_REFERENCES
    )


def test_synthetic_result_preserves_every_unsafe_flag() -> None:
    result = _simulate()

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_synthetic_result_is_deterministic() -> None:
    request = _fake_request()

    transport = (
        ConnectorDeterministicFakeSandboxTransport()
    )

    first = transport.simulate(request)
    second = transport.simulate(request)

    assert first == second


def test_unknown_fake_transport_returns_safe_result() -> None:
    result = _simulate(
        fake_transport_id="unknown_fake_transport_reference"
    )

    assert result.status is (
        ConnectorFakeSandboxResultStatus
        .UNKNOWN_FAKE_TRANSPORT
    )

    assert result.contract_validated is False
    assert result.synthetic_result_generated is False
    assert result.synthetic_metadata_references == ()

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_wrong_base_transport_returns_invalid_request() -> None:
    result = _simulate(
        base_transport_id="unknown_base_transport_reference"
    )

    assert result.status is (
        ConnectorFakeSandboxResultStatus.INVALID_REQUEST
    )

    assert result.contract_validated is True
    assert result.request_validated is False
    assert result.synthetic_result_generated is False
    assert result.synthetic_metadata_references == ()

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_plan_mismatch_returns_safe_result() -> None:
    result = _simulate(
        plan_id=HELPDESK_PLAN_ID
    )

    assert result.status is (
        ConnectorFakeSandboxResultStatus.PLAN_MISMATCH
    )

    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.operation_plan_validated is False
    assert result.synthetic_result_generated is False
    assert result.synthetic_metadata_references == ()

    for field_name in UNSAFE_RESULT_FLAGS:
        assert getattr(result, field_name) is False


def test_fake_transport_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError):
        (
            ConnectorDeterministicFakeSandboxTransport()
            .simulate(object())
        )


@pytest.mark.parametrize(
    "unsafe_change",
    (
        {"environment": "production"},
        {"access_mode": "write"},
        {"local_only": False},
        {"sandbox_only": False},
        {"read_only": False},
        {"deterministic_output_required": False},
        {"synthetic_reference_only": False},
        {"base_transport_must_remain_disabled": False},
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


def test_contract_rejects_non_ready_status() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            status=ConnectorFakeSandboxStatus.BLOCKED,
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


def test_contract_rejects_non_reference_output_mode() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            response_content_mode="raw_payload_body",
        )


def test_custom_validator_rejects_duplicate_contracts() -> None:
    contract = _contract()

    issues = validate_connector_fake_sandbox_contracts(
        (
            contract,
            contract,
        )
    )

    assert (
        f"{FAKE_TRANSPORT_ID}:"
        "duplicate_fake_transport_id"
        in issues
    )


def test_result_rejects_enabled_unsafe_flag() -> None:
    result = _simulate()

    with pytest.raises(ValueError):
        replace(
            result,
            external_http_used=True,
        )


def test_success_result_requires_metadata() -> None:
    result = _simulate()

    with pytest.raises(ValueError):
        replace(
            result,
            synthetic_metadata_references=(),
        )


def test_non_success_result_rejects_synthetic_metadata() -> None:
    result = _simulate(
        fake_transport_id="unknown_fake_transport_reference"
    )

    with pytest.raises(ValueError):
        replace(
            result,
            synthetic_metadata_references=(
                "unexpected_synthetic_reference",
            ),
        )


def test_result_contract_contains_no_raw_payload_fields() -> None:
    field_names = {
        definition.name
        for definition in fields(
            ConnectorFakeSandboxResult
        )
    }

    prohibited_fields = {
        "body",
        "credential_value",
        "endpoint",
        "endpoint_url",
        "headers",
        "password",
        "payload",
        "payload_body",
        "private_key",
        "raw_secret",
        "secret",
        "secret_value",
        "token",
        "url",
    }

    assert field_names.isdisjoint(
        prohibited_fields
    )


def test_fake_simulation_does_not_mutate_referenced_contracts() -> None:
    plan_before = get_connector_operation_plan(
        PLAN_ID
    )

    pilot_before = get_connector_sandbox_pilot_contract(
        PILOT_ID
    )

    secret_before = get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    )

    transport_before = get_connector_transport_contract(
        BASE_TRANSPORT_ID
    )

    _simulate()

    assert get_connector_operation_plan(
        PLAN_ID
    ) == plan_before

    assert get_connector_sandbox_pilot_contract(
        PILOT_ID
    ) == pilot_before

    assert get_connector_secret_manager_contract(
        SECRET_MANAGER_CONTRACT_ID
    ) == secret_before

    assert get_connector_transport_contract(
        BASE_TRANSPORT_ID
    ) == transport_before


def test_source_contains_no_network_execution_or_secret_primitive() -> None:
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
        "random",
        "redis",
        "requests",
        "secrets",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "starlette",
        "subprocess",
        "threading",
        "time",
        "urllib3",
        "uuid",
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
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "httpx.AsyncClient",
        "httpx.Client",
        "json.dump",
        "open",
        "os.getenv",
        "os.urandom",
        "pathlib.Path.read_bytes",
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
        "random.choice",
        "random.randint",
        "random.random",
        "requests.get",
        "requests.post",
        "secrets.token_bytes",
        "secrets.token_hex",
        "secrets.token_urlsafe",
        "socket.create_connection",
        "socket.socket",
        "subprocess.Popen",
        "subprocess.run",
        "time.monotonic",
        "time.time",
        "urllib.request.urlopen",
        "uuid.uuid1",
        "uuid.uuid4",
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


def test_source_does_not_invoke_dispatch_or_base_transport() -> None:
    source = SOURCE_PATH.read_text(
        encoding="utf-8"
    )

    assert "ConnectorMockDispatcher" not in source
    assert "ConnectorNoNetworkTransport" not in source
    assert ".dispatch(" not in source
    assert ".transmit(" not in source


def test_package_exports_16e_r4_contracts() -> None:
    assert (
        integrations.CONNECTOR_FAKE_SANDBOX_CONTRACTS
        is CONNECTOR_FAKE_SANDBOX_CONTRACTS
    )

    assert (
        integrations.ConnectorFakeSandboxContract
        is ConnectorFakeSandboxContract
    )

    assert (
        integrations.ConnectorFakeSandboxAssessment
        is ConnectorFakeSandboxAssessment
    )

    assert (
        integrations.ConnectorFakeSandboxRequest
        is ConnectorFakeSandboxRequest
    )

    assert (
        integrations.ConnectorFakeSandboxResult
        is ConnectorFakeSandboxResult
    )

    assert (
        integrations
        .ConnectorDeterministicFakeSandboxTransport
        is ConnectorDeterministicFakeSandboxTransport
    )


def test_document_declares_required_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "deterministic_local_reference_only_fake_transport",
        "synthetic_reference_metadata_only",
        "deterministic synthetic read result",
        "no payload body",
        "no secret access",
        "no credential resolution",
        "no dispatcher invocation",
        "no network",
        "no http",
        "no socket",
        "no persistence",
        "no route",
        "no worker",
        "no runtime",
        "no production",
        "local-only",
        "sandbox-only",
        "read-only",
    )

    for marker in required_markers:
        assert marker in document
