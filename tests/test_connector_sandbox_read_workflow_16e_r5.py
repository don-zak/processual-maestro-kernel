from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.fake_sandbox_transport import (
    ConnectorFakeSandboxRequest,
    ConnectorFakeSandboxResultStatus,
)
from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
)
from processual_api.integrations.sandbox_read_workflow import (
    CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS,
    SUPPORTED_CONNECTOR_SANDBOX_READ_WORKFLOWS,
    ConnectorDeterministicSandboxReadWorkflow,
    ConnectorSandboxReadWorkflowAssessment,
    ConnectorSandboxReadWorkflowContract,
    ConnectorSandboxReadWorkflowMode,
    ConnectorSandboxReadWorkflowRequest,
    ConnectorSandboxReadWorkflowResult,
    ConnectorSandboxReadWorkflowResultStatus,
    ConnectorSandboxReadWorkflowStatus,
    assess_connector_sandbox_read_workflow,
    execute_connector_sandbox_read_workflow,
    get_connector_sandbox_read_workflow_contract,
    list_connector_sandbox_read_workflow_contracts,
    normalize_connector_sandbox_read_workflow_id,
    validate_connector_sandbox_read_workflow_contracts,
    validate_connector_sandbox_read_workflow_registry,
)
from processual_api.integrations.transport_contracts import (
    ConnectorTransportRequest,
)

SOURCE_PATH = Path(
    "processual_api/integrations/sandbox_read_workflow.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R5.md"
)

WORKFLOW_ID = (
    "telecom_ticketing_deterministic_sandbox_read_workflow"
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

SECRET_MANAGER_ID = (
    "telecom_operations_customer_vault_secret_manager_contract"
)

PLAN_ID = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)

OTHER_PLAN_ID = "other_sandbox_read_plan_reference"

EXPECTED_METADATA = (
    "synthetic_ticket_state_open_reference",
    "synthetic_ticket_priority_normal_reference",
    "synthetic_ticket_channel_api_reference",
    "synthetic_ticket_owner_unassigned_reference",
    "synthetic_ticket_created_at_fixed_reference",
)

REQUIRED_TRUE_CONTRACT_FLAGS = (
    "local_only",
    "sandbox_only",
    "read_only",
    "deterministic_output_required",
    "synthetic_reference_only",
    "fake_transport_simulation_required",
    "base_transport_must_remain_disabled",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
)

UNSAFE_CONTRACT_FLAGS = (
    "real_operation_execution_allowed",
    "payload_body_allowed",
    "secret_access_allowed",
    "credentials_resolution_allowed",
    "dispatcher_invocation_allowed",
    "base_transport_invocation_allowed",
    "external_http_allowed",
    "socket_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

UNSAFE_RESULT_FLAGS = (
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


def _contract() -> ConnectorSandboxReadWorkflowContract:
    return get_connector_sandbox_read_workflow_contract(
        WORKFLOW_ID
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


def _workflow_request(
    *,
    workflow_id: str = WORKFLOW_ID,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorSandboxReadWorkflowRequest:
    return ConnectorSandboxReadWorkflowRequest(
        request_id="sandbox_read_workflow_request_reference",
        workflow_id=workflow_id,
        fake_request=_fake_request(
            fake_transport_id=fake_transport_id,
            base_transport_id=base_transport_id,
            plan_id=plan_id,
        ),
    )


def _run(
    *,
    workflow_id: str = WORKFLOW_ID,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
) -> ConnectorSandboxReadWorkflowResult:
    return ConnectorDeterministicSandboxReadWorkflow().run(
        _workflow_request(
            workflow_id=workflow_id,
            fake_transport_id=fake_transport_id,
            base_transport_id=base_transport_id,
            plan_id=plan_id,
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


def test_registry_contains_one_immutable_workflow() -> None:
    assert len(
        CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
    ) == 1

    assert tuple(
        CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
    ) == (WORKFLOW_ID,)

    assert SUPPORTED_CONNECTOR_SANDBOX_READ_WORKFLOWS == (
        WORKFLOW_ID,
    )

    assert (
        type(
            CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
        ).__name__
        == "mappingproxy"
    )


def test_registry_validation_has_no_issues() -> None:
    assert (
        validate_connector_sandbox_read_workflow_registry()
        == ()
    )


def test_list_and_get_return_the_declared_contract() -> None:
    assert (
        list_connector_sandbox_read_workflow_contracts()
        == (_contract(),)
    )


def test_workflow_id_normalization() -> None:
    assert (
        normalize_connector_sandbox_read_workflow_id(
            f"  {WORKFLOW_ID.upper()}  "
        )
        == WORKFLOW_ID
    )


def test_unknown_workflow_lookup_is_rejected() -> None:
    with pytest.raises(KeyError):
        get_connector_sandbox_read_workflow_contract(
            "unknown_workflow_reference"
        )


def test_contract_is_frozen_and_slotted() -> None:
    contract = _contract()

    assert contract.__dataclass_params__.frozen is True
    assert not hasattr(contract, "__dict__")

    with pytest.raises(FrozenInstanceError):
        contract.runtime_enabled = True


def test_assessment_is_frozen_and_slotted() -> None:
    assessment = assess_connector_sandbox_read_workflow(
        WORKFLOW_ID
    )

    assert assessment.__dataclass_params__.frozen is True
    assert not hasattr(assessment, "__dict__")

    with pytest.raises(FrozenInstanceError):
        assessment.production_allowed = True


def test_request_is_frozen_and_slotted() -> None:
    request = _workflow_request()

    assert request.__dataclass_params__.frozen is True
    assert not hasattr(request, "__dict__")

    with pytest.raises(FrozenInstanceError):
        request.workflow_id = "other_workflow_reference"


def test_result_is_frozen_and_slotted() -> None:
    result = _run()

    assert result.__dataclass_params__.frozen is True
    assert not hasattr(result, "__dict__")

    with pytest.raises(FrozenInstanceError):
        result.external_http_used = True


def test_contract_reference_graph_is_exact() -> None:
    contract = _contract()

    assert contract.workflow_id == WORKFLOW_ID
    assert contract.fake_transport_id == FAKE_TRANSPORT_ID
    assert contract.base_transport_id == BASE_TRANSPORT_ID
    assert contract.pilot_id == PILOT_ID
    assert contract.secret_manager_contract_id == (
        SECRET_MANAGER_ID
    )
    assert contract.plan_id == PLAN_ID
    assert contract.connector_id == (
        "telecom_ticketing_reference"
    )
    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"


def test_contract_mode_output_and_status_are_exact() -> None:
    contract = _contract()

    assert contract.mode is (
        ConnectorSandboxReadWorkflowMode
        .GOVERNED_DETERMINISTIC_LOCAL_READ
    )

    assert contract.status is (
        ConnectorSandboxReadWorkflowStatus
        .LOCAL_HAPPY_PATH_READY
    )

    assert contract.output_mode == (
        "synthetic_reference_metadata_only"
    )

    assert contract.request_type_reference == (
        "ConnectorFakeSandboxRequest"
    )

    assert contract.response_type_reference == (
        "ConnectorSandboxReadWorkflowResult"
    )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_CONTRACT_FLAGS,
)
def test_required_contract_flags_remain_true(
    field_name: str,
) -> None:
    assert getattr(_contract(), field_name) is True


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_CONTRACT_FLAGS,
)
def test_unsafe_contract_flags_remain_false(
    field_name: str,
) -> None:
    assert getattr(_contract(), field_name) is False


def test_assessment_reports_valid_local_reference_graph() -> None:
    assessment = assess_connector_sandbox_read_workflow(
        WORKFLOW_ID
    )

    assert assessment.status is (
        ConnectorSandboxReadWorkflowStatus
        .LOCAL_HAPPY_PATH_READY
    )

    assert assessment.contract_valid is True
    assert assessment.reference_graph_valid is True
    assert assessment.operation_plan_valid is True
    assert assessment.pilot_valid is True
    assert assessment.secret_manager_valid is True
    assert assessment.base_transport_valid is True
    assert assessment.fake_transport_valid is True
    assert assessment.local_happy_path_available is True
    assert assessment.deterministic is True
    assert assessment.synthetic_reference_only is True
    assert assessment.no_network is True


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_CONTRACT_FLAGS,
)
def test_assessment_preserves_unsafe_flags(
    field_name: str,
) -> None:
    assessment = assess_connector_sandbox_read_workflow(
        WORKFLOW_ID
    )

    assert getattr(assessment, field_name) is False


def test_request_wraps_reference_only_r4_request() -> None:
    request = _workflow_request()

    assert isinstance(
        request.fake_request,
        ConnectorFakeSandboxRequest,
    )

    assert request.fake_request.fake_transport_id == (
        FAKE_TRANSPORT_ID
    )

    assert (
        request.fake_request.transport_request.transport_id
        == BASE_TRANSPORT_ID
    )

    assert (
        request.fake_request
        .transport_request
        .dispatch_request
        .plan_id
        == PLAN_ID
    )

    assert (
        request.fake_request
        .transport_request
        .dispatch_request
        .simulation_mode
        is True
    )


def test_request_rejects_wrong_fake_request_type() -> None:
    with pytest.raises(TypeError):
        ConnectorSandboxReadWorkflowRequest(
            request_id="workflow_request_reference",
            workflow_id=WORKFLOW_ID,
            fake_request=object(),
        )


def test_happy_path_returns_completed_result() -> None:
    result = _run()

    assert result.status is (
        ConnectorSandboxReadWorkflowResultStatus
        .SYNTHETIC_READ_COMPLETED
    )

    assert result.reason_code == (
        "governed_synthetic_ticket_read_completed"
    )

    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.reference_graph_validated is True
    assert result.fake_transport_validated is True
    assert result.synthetic_result_completed is True

    assert result.fake_result_status_reference == (
        ConnectorFakeSandboxResultStatus
        .SYNTHETIC_READ_RESULT
        .value
    )


def test_happy_path_projects_exact_synthetic_references() -> None:
    result = _run()

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
        EXPECTED_METADATA
    )


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_RESULT_FLAGS,
)
def test_happy_path_preserves_unsafe_result_flags(
    field_name: str,
) -> None:
    assert getattr(_run(), field_name) is False


def test_happy_path_is_deterministic() -> None:
    workflow = ConnectorDeterministicSandboxReadWorkflow()
    request = _workflow_request()

    assert workflow.run(request) == workflow.run(request)


def test_public_execute_function_matches_workflow_class() -> None:
    request = _workflow_request()

    assert execute_connector_sandbox_read_workflow(
        request
    ) == ConnectorDeterministicSandboxReadWorkflow().run(
        request
    )


def test_unknown_workflow_returns_safe_rejection() -> None:
    result = _run(
        workflow_id="unknown_workflow_reference"
    )

    assert result.status is (
        ConnectorSandboxReadWorkflowResultStatus
        .UNKNOWN_WORKFLOW
    )

    assert result.contract_validated is False
    assert result.synthetic_result_completed is False
    assert result.synthetic_metadata_references == ()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        (
            "fake_transport_id",
            "unknown_fake_transport_reference",
        ),
        (
            "base_transport_id",
            "unknown_base_transport_reference",
        ),
        (
            "plan_id",
            OTHER_PLAN_ID,
        ),
    ),
)
def test_reference_mismatches_return_invalid_request(
    field_name: str,
    field_value: str,
) -> None:
    arguments = {field_name: field_value}
    result = _run(**arguments)

    assert result.status is (
        ConnectorSandboxReadWorkflowResultStatus
        .INVALID_REQUEST
    )

    assert result.request_validated is False
    assert result.synthetic_result_completed is False
    assert result.synthetic_metadata_references == ()

    for unsafe_field in UNSAFE_RESULT_FLAGS:
        assert getattr(result, unsafe_field) is False


def test_workflow_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError):
        ConnectorDeterministicSandboxReadWorkflow().run(
            object()
        )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_CONTRACT_FLAGS,
)
def test_contract_rejects_disabled_required_flags(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            **{field_name: False},
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


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("environment", "production"),
        ("access_mode", "write"),
        ("output_mode", "raw_ticket_payload"),
        ("request_type_reference", "RawHttpRequest"),
        ("response_type_reference", "RawHttpResponse"),
    ),
)
def test_contract_rejects_unsafe_identity_changes(
    field_name: str,
    field_value: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            **{field_name: field_value},
        )


def test_contract_rejects_blocked_declaration_status() -> None:
    with pytest.raises(ValueError):
        replace(
            _contract(),
            status=ConnectorSandboxReadWorkflowStatus.BLOCKED,
        )


def test_custom_validator_rejects_duplicate_workflows() -> None:
    contract = _contract()

    issues = (
        validate_connector_sandbox_read_workflow_contracts(
            (contract, contract)
        )
    )

    assert (
        f"{WORKFLOW_ID}:duplicate_workflow_id"
        in issues
    )


@pytest.mark.parametrize(
    "field_name",
    UNSAFE_RESULT_FLAGS,
)
def test_result_rejects_enabled_unsafe_flags(
    field_name: str,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _run(),
            **{field_name: True},
        )


def test_success_result_requires_synthetic_metadata() -> None:
    with pytest.raises(ValueError):
        replace(
            _run(),
            synthetic_metadata_references=(),
        )


def test_rejected_result_must_not_expose_metadata() -> None:
    result = _run(
        workflow_id="unknown_workflow_reference"
    )

    with pytest.raises(ValueError):
        replace(
            result,
            synthetic_metadata_references=(
                "unexpected_metadata_reference",
            ),
        )


@pytest.mark.parametrize(
    "data_type",
    (
        ConnectorSandboxReadWorkflowContract,
        ConnectorSandboxReadWorkflowRequest,
        ConnectorSandboxReadWorkflowResult,
    ),
)
def test_public_contracts_contain_no_raw_material_fields(
    data_type: type[object],
) -> None:
    field_names = {
        definition.name
        for definition in fields(data_type)
    }

    prohibited = {
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

    assert field_names.isdisjoint(prohibited)


def test_source_contains_no_network_secret_or_persistence_primitive(
) -> None:
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

    banned_calls = {
        "asyncio.create_task",
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "httpx.AsyncClient",
        "httpx.Client",
        "json.dump",
        "open",
        "os.getenv",
        "os.urandom",
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
        "random.random",
        "requests.get",
        "requests.post",
        "secrets.token_hex",
        "socket.create_connection",
        "socket.socket",
        "subprocess.Popen",
        "subprocess.run",
        "time.time",
        "urllib.request.urlopen",
        "uuid.uuid4",
    }

    import_hits: list[str] = []
    call_hits: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]

                if root in banned_import_roots:
                    import_hits.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]

            if root in banned_import_roots:
                import_hits.append(module)

        elif isinstance(node, ast.Call):
            call_name = _dotted_name(node.func)

            if call_name in banned_calls:
                call_hits.append(call_name)

    assert import_hits == []
    assert call_hits == []


def test_source_invokes_only_r4_fake_simulation_boundary() -> None:
    source = SOURCE_PATH.read_text(
        encoding="utf-8"
    )

    assert "ConnectorMockDispatcher" not in source
    assert "ConnectorNoNetworkTransport" not in source
    assert ".dispatch(" not in source
    assert ".transmit(" not in source
    assert ".simulate(" in source


def test_package_exports_r5_public_contracts() -> None:
    assert (
        integrations
        .CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
        is CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
    )

    assert (
        integrations.ConnectorSandboxReadWorkflowContract
        is ConnectorSandboxReadWorkflowContract
    )

    assert (
        integrations.ConnectorSandboxReadWorkflowAssessment
        is ConnectorSandboxReadWorkflowAssessment
    )

    assert (
        integrations.ConnectorSandboxReadWorkflowRequest
        is ConnectorSandboxReadWorkflowRequest
    )

    assert (
        integrations.ConnectorSandboxReadWorkflowResult
        is ConnectorSandboxReadWorkflowResult
    )

    assert (
        integrations
        .ConnectorDeterministicSandboxReadWorkflow
        is ConnectorDeterministicSandboxReadWorkflow
    )


def test_document_declares_required_r5_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "governed_deterministic_local_read_happy_path",
        "synthetic_reference_metadata_only",
        "synthetic_read_completed",
        "reference-only workflow request",
        "fake sandbox simulation only",
        "no payload body",
        "no secret access",
        "no credential resolution",
        "no dispatcher invocation",
        "no base transport invocation",
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
