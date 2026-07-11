"""Tests for deterministic sandbox-read fault contracts R6."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import processual_api.integrations as integration_package
import processual_api.integrations.fake_sandbox_transport as fake_module
import processual_api.integrations.sandbox_read_faults as fault_module
import processual_api.integrations.sandbox_read_workflow as workflow_module
from processual_api.integrations.fake_sandbox_transport import (
    ConnectorFakeSandboxRequest,
)
from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
)
from processual_api.integrations.sandbox_read_faults import (
    CONNECTOR_SANDBOX_READ_FAULT_PROFILES,
    SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES,
    ConnectorDeterministicSandboxReadFaultSimulator,
    ConnectorSandboxReadFaultAssessment,
    ConnectorSandboxReadFaultKind,
    ConnectorSandboxReadFaultProfile,
    ConnectorSandboxReadFaultProfileStatus,
    ConnectorSandboxReadFaultRequest,
    ConnectorSandboxReadFaultResult,
    ConnectorSandboxReadFaultResultStatus,
    assess_connector_sandbox_read_fault_profile,
    execute_connector_sandbox_read_fault,
    get_connector_sandbox_read_fault_profile,
    list_connector_sandbox_read_fault_profiles,
    normalize_connector_sandbox_read_fault_profile_id,
    validate_connector_sandbox_read_fault_profiles,
    validate_connector_sandbox_read_fault_registry,
)
from processual_api.integrations.sandbox_read_workflow import (
    ConnectorSandboxReadWorkflowRequest,
)
from processual_api.integrations.transport_contracts import (
    ConnectorTransportRequest,
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
PLAN_ID = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)
TIMEOUT_PROFILE_ID = (
    "telecom_ticketing_synthetic_timeout_fault_profile"
)

EXPECTED_KINDS = (
    ConnectorSandboxReadFaultKind.SYNTHETIC_TIMEOUT,
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_TRANSPORT_UNAVAILABLE
    ),
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_AUTHORIZATION_DENIED
    ),
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE
    ),
    ConnectorSandboxReadFaultKind.SYNTHETIC_PLAN_REJECTED,
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_OPERATOR_APPROVAL_MISSING
    ),
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_SECURITY_REVIEW_MISSING
    ),
    (
        ConnectorSandboxReadFaultKind
        .SYNTHETIC_MALFORMED_REFERENCE
    ),
    ConnectorSandboxReadFaultKind.SAFE_REFUSAL,
)

REQUIRED_TRUE_PROFILE_FIELDS = (
    "local_only",
    "sandbox_only",
    "read_only",
    "deterministic",
    "immediate_result",
    "synthetic_reference_only",
    "safe_refusal_required",
)

UNSAFE_PROFILE_FIELDS = (
    "real_timeout_wait_allowed",
    "retry_execution_allowed",
    "automatic_retry_allowed",
    "background_retry_allowed",
    "network_attempt_allowed",
    "secret_resolution_allowed",
    "dispatcher_invocation_allowed",
    "workflow_execution_allowed",
    "payload_body_allowed",
    "persistence_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

UNSAFE_RESULT_FIELDS = (
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

EXPECTED_BLOCKERS = (
    "real_timeout_wait_disabled",
    "retry_execution_disabled",
    "automatic_retry_disabled",
    "background_retry_disabled",
    "network_attempt_disabled",
    "secret_resolution_disabled",
    "dispatcher_invocation_disabled",
    "workflow_execution_disabled",
    "payload_body_disabled",
    "persistence_disabled",
    "route_exposure_disabled",
    "runtime_disabled",
    "production_disabled",
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
        tenant_reference="sandbox_tenant_reference",
        payload_hash="sha256_payload_reference",
        idempotency_key="idempotency_reference",
        requested_at_reference="requested_at_reference",
        expires_at_reference="expires_at_reference",
        requester_reference="requester_reference",
        approval_reference="approval_reference",
        simulation_mode=simulation_mode,
    )


def _workflow_request(
    *,
    workflow_id: str = WORKFLOW_ID,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
    simulation_mode: bool = True,
) -> ConnectorSandboxReadWorkflowRequest:
    transport_request = ConnectorTransportRequest(
        request_id="transport_request_reference",
        transport_id=base_transport_id,
        dispatch_request=_dispatch_request(
            plan_id=plan_id,
            simulation_mode=simulation_mode,
        ),
    )

    fake_request = ConnectorFakeSandboxRequest(
        request_id="fake_sandbox_request_reference",
        fake_transport_id=fake_transport_id,
        transport_request=transport_request,
    )

    return ConnectorSandboxReadWorkflowRequest(
        request_id="sandbox_read_workflow_request_reference",
        workflow_id=workflow_id,
        fake_request=fake_request,
    )


def _fault_request(
    *,
    fault_profile_id: str = TIMEOUT_PROFILE_ID,
    workflow_id: str = WORKFLOW_ID,
    fake_transport_id: str = FAKE_TRANSPORT_ID,
    base_transport_id: str = BASE_TRANSPORT_ID,
    plan_id: str = PLAN_ID,
    simulation_mode: bool = True,
) -> ConnectorSandboxReadFaultRequest:
    return ConnectorSandboxReadFaultRequest(
        request_id="sandbox_read_fault_request_reference",
        fault_profile_id=fault_profile_id,
        workflow_request=_workflow_request(
            workflow_id=workflow_id,
            fake_transport_id=fake_transport_id,
            base_transport_id=base_transport_id,
            plan_id=plan_id,
            simulation_mode=simulation_mode,
        ),
    )


def _timeout_result() -> ConnectorSandboxReadFaultResult:
    return execute_connector_sandbox_read_fault(
        _fault_request()
    )


def test_registry_is_immutable_and_complete() -> None:
    assert isinstance(
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES,
        MappingProxyType,
    )
    assert len(CONNECTOR_SANDBOX_READ_FAULT_PROFILES) == 9
    assert tuple(
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES
    ) == SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES
    assert tuple(
        profile.kind
        for profile in (
            CONNECTOR_SANDBOX_READ_FAULT_PROFILES.values()
        )
    ) == EXPECTED_KINDS

    with pytest.raises(TypeError):
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES[
            "forged_fault_profile"
        ] = get_connector_sandbox_read_fault_profile(
            TIMEOUT_PROFILE_ID
        )


def test_registry_validation_has_no_issues() -> None:
    assert validate_connector_sandbox_read_fault_registry() == ()


def test_list_and_get_preserve_declared_identity() -> None:
    listed = list_connector_sandbox_read_fault_profiles()

    assert len(listed) == 9

    for profile in listed:
        assert (
            get_connector_sandbox_read_fault_profile(
                profile.fault_profile_id
            )
            is profile
        )


@pytest.mark.parametrize("kind", EXPECTED_KINDS)
def test_each_fault_kind_has_exactly_one_profile(
    kind: ConnectorSandboxReadFaultKind,
) -> None:
    matches = tuple(
        profile
        for profile in (
            CONNECTOR_SANDBOX_READ_FAULT_PROFILES.values()
        )
        if profile.kind is kind
    )

    assert len(matches) == 1
    assert matches[0].result_status.value == kind.value


@pytest.mark.parametrize(
    "contract_type",
    (
        ConnectorSandboxReadFaultProfile,
        ConnectorSandboxReadFaultAssessment,
        ConnectorSandboxReadFaultRequest,
        ConnectorSandboxReadFaultResult,
    ),
)
def test_r6_contracts_are_frozen_slotted_dataclasses(
    contract_type: type[object],
) -> None:
    assert is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True
    assert hasattr(contract_type, "__slots__")


def test_profile_instances_are_frozen_and_slotted() -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    assert not hasattr(profile, "__dict__")

    with pytest.raises((FrozenInstanceError, AttributeError)):
        profile.production_allowed = True


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " fault_profile_reference",
        "fault_profile_reference ",
        "https://external.invalid/fault",
        "bearer raw_value",
        "password=raw_value",
        "token=raw_value",
        "secret=raw_value",
        "private_key=raw_value",
        "raw_payload=raw_value",
    ),
)
def test_normalizer_rejects_unsafe_or_invalid_references(
    value: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_connector_sandbox_read_fault_profile_id(
            value
        )


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_connector_sandbox_read_fault_profile_id(
            object()
        )


def test_normalizer_preserves_safe_reference() -> None:
    assert (
        normalize_connector_sandbox_read_fault_profile_id(
            TIMEOUT_PROFILE_ID
        )
        == TIMEOUT_PROFILE_ID
    )


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_TRUE_PROFILE_FIELDS,
)
def test_profile_rejects_disabled_required_flag(
    field_name: str,
) -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    with pytest.raises(ValueError):
        replace(profile, **{field_name: False})


@pytest.mark.parametrize("field_name", UNSAFE_PROFILE_FIELDS)
def test_profile_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    with pytest.raises(ValueError):
        replace(profile, **{field_name: True})


def test_profile_rejects_wrong_workflow_reference() -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    with pytest.raises(ValueError):
        replace(
            profile,
            workflow_id="unknown_workflow_reference",
        )


def test_profile_rejects_kind_status_mismatch() -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    with pytest.raises(ValueError):
        replace(
            profile,
            result_status=(
                ConnectorSandboxReadFaultResultStatus
                .SAFE_REFUSAL
            ),
        )


def test_profile_collection_validation_rejects_duplicates() -> None:
    profile = get_connector_sandbox_read_fault_profile(
        TIMEOUT_PROFILE_ID
    )

    issues = validate_connector_sandbox_read_fault_profiles(
        (profile, profile)
    )

    assert any(
        "duplicate_profile_id" in issue
        for issue in issues
    )
    assert any(
        "duplicate_fault_kind" in issue
        for issue in issues
    )
    assert "fault_kind_coverage_incomplete" in issues

def test_fault_request_rejects_wrong_workflow_request_type() -> None:
    with pytest.raises(TypeError):
        ConnectorSandboxReadFaultRequest(
            request_id="fault_request_reference",
            fault_profile_id=TIMEOUT_PROFILE_ID,
            workflow_request=object(),
        )


@pytest.mark.parametrize(
    "profile_id",
    SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES,
)
def test_each_profile_assessment_is_ready_and_default_deny(
    profile_id: str,
) -> None:
    assessment = assess_connector_sandbox_read_fault_profile(
        profile_id
    )

    assert assessment.status is (
        ConnectorSandboxReadFaultProfileStatus
        .LOCAL_FAULT_READY
    )
    assert assessment.contract_valid is True
    assert assessment.workflow_valid is True
    assert assessment.fault_injection_available is True
    assert assessment.deterministic is True
    assert assessment.immediate_result is True
    assert assessment.synthetic_reference_only is True
    assert assessment.safe_refusal_required is True

    for field_name in UNSAFE_PROFILE_FIELDS:
        assert getattr(assessment, field_name) is False

    assert set(EXPECTED_BLOCKERS).issubset(
        assessment.blocker_codes
    )


@pytest.mark.parametrize(
    "profile_id",
    SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES,
)
def test_each_profile_returns_immediate_deterministic_safe_refusal(
    profile_id: str,
) -> None:
    profile = get_connector_sandbox_read_fault_profile(
        profile_id
    )
    request = _fault_request(
        fault_profile_id=profile_id
    )

    first = execute_connector_sandbox_read_fault(request)
    second = execute_connector_sandbox_read_fault(request)

    assert first == second
    assert first.status is profile.result_status
    assert first.reason_code == profile.reason_code
    assert (
        first.reason_reference
        == profile.reason_reference
    )
    assert (
        first.synthetic_fault_reference
        == profile.synthetic_fault_reference
    )
    assert first.contract_validated is True
    assert first.request_validated is True
    assert first.workflow_validated is True
    assert first.fault_injected is True
    assert first.deterministic is True
    assert first.immediate_result is True
    assert first.safe_refusal is True

    for field_name in UNSAFE_RESULT_FIELDS:
        assert getattr(first, field_name) is False


@pytest.mark.parametrize("field_name", UNSAFE_RESULT_FIELDS)
def test_result_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    result = _timeout_result()

    with pytest.raises(ValueError):
        replace(result, **{field_name: True})


def test_unknown_profile_returns_safe_non_executed_result() -> None:
    request = _fault_request(
        fault_profile_id="unknown_fault_profile_reference"
    )
    result = execute_connector_sandbox_read_fault(
        request
    )

    assert result.status is (
        ConnectorSandboxReadFaultResultStatus
        .UNKNOWN_FAULT_PROFILE
    )
    assert result.contract_validated is False
    assert result.request_validated is True
    assert result.workflow_validated is False
    assert result.fault_injected is False
    assert result.immediate_result is True
    assert result.safe_refusal is True

    for field_name in UNSAFE_RESULT_FIELDS:
        assert getattr(result, field_name) is False


@pytest.mark.parametrize(
    ("override_name", "override_value"),
    (
        (
            "workflow_id",
            "unknown_workflow_reference",
        ),
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
            "unknown_operation_plan_reference",
        ),
    ),
)
def test_invalid_nested_reference_is_safely_rejected(
    override_name: str,
    override_value: object,
) -> None:
    kwargs = {override_name: override_value}
    request = _fault_request(**kwargs)
    result = execute_connector_sandbox_read_fault(
        request
    )

    assert result.status is (
        ConnectorSandboxReadFaultResultStatus
        .INVALID_REQUEST
    )
    assert result.contract_validated is True
    assert result.request_validated is False
    assert result.workflow_validated is False
    assert result.fault_injected is False
    assert result.safe_refusal is True

    for field_name in UNSAFE_RESULT_FIELDS:
        assert getattr(result, field_name) is False


def test_lower_dispatch_contract_rejects_non_simulation_mode(
) -> None:
    with pytest.raises(
        ValueError,
        match="must remain in simulation mode",
    ):
        _fault_request(simulation_mode=False)


def test_simulator_rejects_wrong_request_type() -> None:
    simulator = (
        ConnectorDeterministicSandboxReadFaultSimulator()
    )

    with pytest.raises(TypeError):
        simulator.simulate(object())


def test_executor_matches_direct_simulator() -> None:
    request = _fault_request()

    assert execute_connector_sandbox_read_fault(
        request
    ) == (
        ConnectorDeterministicSandboxReadFaultSimulator()
        .simulate(request)
    )


def test_fault_simulator_never_executes_r5_or_fake_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def forbidden_call(*args: object, **kwargs: object) -> object:
        calls.append("forbidden")
        raise AssertionError(
            "a prohibited execution layer was invoked"
        )

    monkeypatch.setattr(
        workflow_module,
        "execute_connector_sandbox_read_workflow",
        forbidden_call,
    )
    monkeypatch.setattr(
        workflow_module.ConnectorDeterministicSandboxReadWorkflow,
        "run",
        forbidden_call,
    )
    monkeypatch.setattr(
        fake_module.ConnectorDeterministicFakeSandboxTransport,
        "simulate",
        forbidden_call,
    )

    result = execute_connector_sandbox_read_fault(
        _fault_request()
    )

    assert result.status is (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_TIMEOUT
    )
    assert calls == []


def test_module_has_no_forbidden_imports_or_runtime_calls() -> None:
    source = inspect.getsource(fault_module)
    tree = ast.parse(source)

    forbidden_modules = {
        "requests",
        "httpx",
        "urllib",
        "socket",
        "aiohttp",
        "subprocess",
        "threading",
        "multiprocessing",
        "asyncio",
        "time",
        "random",
        "uuid",
    }

    forbidden_calls = {
        "sleep",
        "time",
        "uuid4",
        "urlopen",
        "create_task",
        "run_in_executor",
    }

    module_hits: list[tuple[int, str]] = []
    call_hits: list[tuple[int, str]] = []

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
                call_name = function.id
            elif isinstance(function, ast.Attribute):
                call_name = function.attr
            else:
                call_name = ""

            if call_name in forbidden_calls:
                call_hits.append(
                    (node.lineno, call_name)
                )

    assert module_hits == []
    assert call_hits == []


def test_module_has_no_prohibited_execution_symbols() -> None:
    source = inspect.getsource(fault_module)

    prohibited = (
        "execute_connector_sandbox_read_workflow",
        "ConnectorDeterministicSandboxReadWorkflow",
        "ConnectorDeterministicFakeSandboxTransport",
        ".simulate(request.fake_request)",
    )

    assert tuple(
        symbol
        for symbol in prohibited
        if symbol in source
    ) == ()


def test_request_and_result_contracts_are_reference_only() -> None:
    request_fields = {
        field.name
        for field in fields(
            ConnectorSandboxReadFaultRequest
        )
    }
    result_fields = {
        field.name
        for field in fields(
            ConnectorSandboxReadFaultResult
        )
    }

    prohibited_fields = {
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
    }

    assert request_fields.isdisjoint(prohibited_fields)
    assert result_fields.isdisjoint(prohibited_fields)


def test_timeout_profile_returns_without_real_wait_state() -> None:
    result = _timeout_result()

    assert result.status is (
        ConnectorSandboxReadFaultResultStatus
        .SYNTHETIC_TIMEOUT
    )
    assert result.immediate_result is True
    assert result.real_timeout_waited is False
    assert result.retry_executed is False
    assert result.background_retry_created is False


def test_public_export_list_covers_declared_surface() -> None:
    expected = {
        "CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
        "SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
        "ConnectorDeterministicSandboxReadFaultSimulator",
        "ConnectorSandboxReadFaultAssessment",
        "ConnectorSandboxReadFaultKind",
        "ConnectorSandboxReadFaultProfile",
        "ConnectorSandboxReadFaultProfileStatus",
        "ConnectorSandboxReadFaultRequest",
        "ConnectorSandboxReadFaultResult",
        "ConnectorSandboxReadFaultResultStatus",
        "assess_connector_sandbox_read_fault_profile",
        "execute_connector_sandbox_read_fault",
        "get_connector_sandbox_read_fault_profile",
        "list_connector_sandbox_read_fault_profiles",
        "normalize_connector_sandbox_read_fault_profile_id",
        "validate_connector_sandbox_read_fault_profiles",
        "validate_connector_sandbox_read_fault_registry",
    }

    assert set(fault_module.__all__) == expected


def test_package_exports_r6_public_surface() -> None:
    expected = {
        "CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
        "SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
        "ConnectorDeterministicSandboxReadFaultSimulator",
        "ConnectorSandboxReadFaultAssessment",
        "ConnectorSandboxReadFaultKind",
        "ConnectorSandboxReadFaultProfile",
        "ConnectorSandboxReadFaultProfileStatus",
        "ConnectorSandboxReadFaultRequest",
        "ConnectorSandboxReadFaultResult",
        "ConnectorSandboxReadFaultResultStatus",
        "assess_connector_sandbox_read_fault_profile",
        "execute_connector_sandbox_read_fault",
        "get_connector_sandbox_read_fault_profile",
        "list_connector_sandbox_read_fault_profiles",
        "normalize_connector_sandbox_read_fault_profile_id",
        "validate_connector_sandbox_read_fault_profiles",
        "validate_connector_sandbox_read_fault_registry",
    }

    assert expected.issubset(
        set(integration_package.__all__)
    )

    for name in expected:
        assert hasattr(integration_package, name)


def test_r6_documentation_records_required_safety_markers(
) -> None:
    documentation = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16E_R6.md"
    ).read_text(encoding="utf-8")

    required_markers = (
        "EXTERNAL-CONNECTIVITY-16E-R6",
        "Deterministic timeout rule",
        "synthetic_timeout",
        "safe_refusal",
        "real_timeout_wait_allowed=False",
        "retry_execution_allowed=False",
        "automatic_retry_allowed=False",
        "background_retry_allowed=False",
        "network_attempt_allowed=False",
        "secret_resolution_allowed=False",
        "dispatcher_invocation_allowed=False",
        "workflow_execution_allowed=False",
        "payload_body_allowed=False",
        "persistence_allowed=False",
        "route_exposure_allowed=False",
        "runtime_enabled=False",
        "production_allowed=False",
        "execute_connector_sandbox_read_workflow",
        "ConnectorDeterministicFakeSandboxTransport.simulate",
        "Sandbox evidence bundle",
    )

    missing = tuple(
        marker
        for marker in required_markers
        if marker not in documentation
    )

    assert missing == ()
