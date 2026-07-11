from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import processual_api.integrations as integrations
from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
    ConnectorDispatchResult,
    ConnectorDispatchStatus,
    ConnectorMockDispatcher,
)
from processual_api.integrations.operation_plans import (
    CONNECTOR_OPERATION_PLANS,
    validate_connector_operation_registry,
)

SOURCE_PATH = Path(
    "processual_api/integrations/mock_dispatcher.py"
)

DOCUMENT_PATH = Path(
    "docs/integrations/EXTERNAL_CONNECTIVITY_16D.md"
)

EXECUTION_FLAGS = (
    "dispatch_attempted",
    "operation_executed",
    "external_http_used",
    "credentials_resolved",
    "payload_persisted",
    "audit_event_emitted",
    "background_task_created",
    "production_used",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _known_plan():
    return next(iter(CONNECTOR_OPERATION_PLANS.values()))


def _request_for(
    plan,
    **overrides,
) -> ConnectorDispatchRequest:
    values = {
        "request_id": "dispatch_request_16d",
        "plan_id": plan.plan_id,
        "operation_id": "operation_reference_16d",
        "tenant_reference": "tenant_reference_16d",
        "payload_hash": "sha256:reference-only-16d",
        "idempotency_key": "idempotency_reference_16d",
        "requested_at_reference": "requested_time_reference_16d",
        "expires_at_reference": "expiry_time_reference_16d",
        "requester_reference": "requester_reference_16d",
        "approval_reference": "approval_reference_16d",
        "simulation_mode": True,
    }
    values.update(overrides)
    return ConnectorDispatchRequest(**values)


def _assert_no_execution(
    result: ConnectorDispatchResult,
) -> None:
    for flag_name in EXECUTION_FLAGS:
        assert getattr(result, flag_name) is False


def _dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    current: ast.AST | None = node

    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    return ".".join(reversed(parts))


def test_operation_plan_registry_baseline_is_valid() -> None:
    assert len(CONNECTOR_OPERATION_PLANS) == 101
    assert validate_connector_operation_registry() == ()


def test_request_and_result_are_frozen_and_slotted() -> None:
    plan = _known_plan()
    request = _request_for(plan)
    result = ConnectorMockDispatcher().dispatch(request)

    assert request.__dataclass_params__.frozen is True
    assert result.__dataclass_params__.frozen is True
    assert not hasattr(request, "__dict__")
    assert not hasattr(result, "__dict__")

    with pytest.raises(FrozenInstanceError):
        request.plan_id = "changed"

    with pytest.raises(FrozenInstanceError):
        result.reason_code = "changed"


def test_request_contract_contains_references_only() -> None:
    field_names = {
        definition.name
        for definition in fields(ConnectorDispatchRequest)
    }

    expected_fields = {
        "request_id",
        "plan_id",
        "operation_id",
        "tenant_reference",
        "payload_hash",
        "idempotency_key",
        "requested_at_reference",
        "expires_at_reference",
        "requester_reference",
        "approval_reference",
        "simulation_mode",
    }

    prohibited_fields = {
        "body",
        "credential",
        "credentials",
        "endpoint",
        "headers",
        "password",
        "payload",
        "raw_payload",
        "secret",
        "secret_value",
        "token",
        "url",
    }

    assert field_names == expected_fields
    assert field_names.isdisjoint(prohibited_fields)


def test_dispatch_status_catalog_contains_only_safe_outcomes() -> None:
    assert {
        status.value
        for status in ConnectorDispatchStatus
    } == {
        "blocked",
        "invalid_request",
        "unknown_plan",
        "metadata_incomplete",
        "approval_reference_missing",
        "expired_reference",
    }


@pytest.mark.parametrize(
    "unsafe_value",
    (
        "https://customer.example/api",
        "http://customer.example/api",
        "Bearer example-value",
        "password=example-value",
        "token=example-value",
        "secret=example-value",
        "private_key_material",
        "raw_payload_material",
    ),
)
def test_request_rejects_raw_or_network_material(
    unsafe_value: str,
) -> None:
    plan = _known_plan()

    with pytest.raises(ValueError):
        _request_for(
            plan,
            requester_reference=unsafe_value,
        )


def test_request_requires_local_simulation_mode() -> None:
    plan = _known_plan()

    with pytest.raises(ValueError):
        _request_for(
            plan,
            simulation_mode=False,
        )


def test_every_registered_plan_remains_blocked() -> None:
    dispatcher = ConnectorMockDispatcher()

    for plan in CONNECTOR_OPERATION_PLANS.values():
        result = dispatcher.dispatch(_request_for(plan))

        assert (
            result.dispatch_status
            is ConnectorDispatchStatus.BLOCKED
        )
        assert result.reason_code == (
            "dispatch_disabled_by_contract"
        )
        assert result.validated_plan is True
        assert result.validated_metadata is True
        _assert_no_execution(result)


def test_every_plan_preserves_16c_default_deny_guardrails() -> None:
    plan_flags = (
        "action_execution_allowed",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_resolution_allowed",
    )

    for plan in CONNECTOR_OPERATION_PLANS.values():
        assert plan.steps
        assert _enum_value(plan.status) == "planning_only"
        assert (
            _enum_value(plan.steps[-1].step_kind)
            == "block_dispatch"
        )

        for flag_name in plan_flags:
            assert getattr(plan, flag_name) is False

        for step in plan.steps:
            assert step.execution_allowed is False
            assert step.external_http_allowed is False
            assert step.credentials_resolution_allowed is False


def test_unknown_plan_returns_safe_failure() -> None:
    plan = _known_plan()
    request = _request_for(
        plan,
        plan_id="unknown_operation_plan_16d",
    )

    result = ConnectorMockDispatcher().dispatch(request)

    assert (
        result.dispatch_status
        is ConnectorDispatchStatus.UNKNOWN_PLAN
    )
    assert result.validated_plan is False
    assert result.validated_metadata is True
    _assert_no_execution(result)


def test_missing_required_metadata_returns_safe_failure() -> None:
    plan = _known_plan()
    request = _request_for(
        plan,
        tenant_reference="",
    )

    result = ConnectorMockDispatcher().dispatch(request)

    assert result.dispatch_status is (
        ConnectorDispatchStatus.METADATA_INCOMPLETE
    )
    assert result.validated_plan is False
    assert result.validated_metadata is False
    _assert_no_execution(result)


def test_missing_approval_reference_returns_safe_failure() -> None:
    plan = _known_plan()
    request = _request_for(
        plan,
        approval_reference="",
    )

    result = ConnectorMockDispatcher().dispatch(request)

    assert result.dispatch_status is (
        ConnectorDispatchStatus.APPROVAL_REFERENCE_MISSING
    )
    assert result.validated_plan is True
    assert result.validated_metadata is False
    _assert_no_execution(result)


def test_expired_reference_returns_safe_failure() -> None:
    plan = _known_plan()
    request = _request_for(
        plan,
        expires_at_reference="expired:reference_16d",
    )

    result = ConnectorMockDispatcher().dispatch(request)

    assert result.dispatch_status is (
        ConnectorDispatchStatus.EXPIRED_REFERENCE
    )
    assert result.validated_plan is True
    assert result.validated_metadata is False
    _assert_no_execution(result)


def test_dispatch_is_deterministic_and_request_is_unchanged() -> None:
    plan = _known_plan()
    request = _request_for(plan)
    dispatcher = ConnectorMockDispatcher()

    first = dispatcher.dispatch(request)
    second = dispatcher.dispatch(request)

    assert first == second
    assert request == _request_for(plan)


def test_dispatcher_is_stateless() -> None:
    dispatcher = ConnectorMockDispatcher()

    assert not hasattr(dispatcher, "__dict__")


def test_dispatch_does_not_mutate_plan_registry() -> None:
    plan = _known_plan()
    request = _request_for(plan)

    before = tuple(CONNECTOR_OPERATION_PLANS.items())

    ConnectorMockDispatcher().dispatch(request)

    after = tuple(CONNECTOR_OPERATION_PLANS.items())

    assert after == before


def test_result_defaults_preserve_default_deny() -> None:
    result = ConnectorDispatchResult(
        request_id="request_16d",
        plan_id="plan_16d",
        dispatch_status=ConnectorDispatchStatus.BLOCKED,
        reason_code="blocked",
        reason="Dispatch remains blocked.",
        validated_plan=True,
        validated_metadata=True,
    )

    _assert_no_execution(result)


@pytest.mark.parametrize("flag_name", EXECUTION_FLAGS)
def test_result_rejects_every_execution_flag(
    flag_name: str,
) -> None:
    result = ConnectorDispatchResult(
        request_id="request_16d",
        plan_id="plan_16d",
        dispatch_status=ConnectorDispatchStatus.BLOCKED,
        reason_code="blocked",
        reason="Dispatch remains blocked.",
        validated_plan=True,
        validated_metadata=True,
    )

    with pytest.raises(ValueError):
        replace(
            result,
            **{flag_name: True},
        )


def test_dispatch_rejects_non_contract_request() -> None:
    with pytest.raises(TypeError):
        ConnectorMockDispatcher().dispatch(object())


def test_mock_source_contains_no_forbidden_primitive() -> None:
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


def test_package_exports_16d_contracts() -> None:
    assert (
        integrations.ConnectorDispatchRequest
        is ConnectorDispatchRequest
    )
    assert (
        integrations.ConnectorDispatchResult
        is ConnectorDispatchResult
    )
    assert (
        integrations.ConnectorDispatchStatus
        is ConnectorDispatchStatus
    )
    assert (
        integrations.ConnectorMockDispatcher
        is ConnectorMockDispatcher
    )


def test_document_declares_required_guardrails() -> None:
    document = DOCUMENT_PATH.read_text(
        encoding="utf-8"
    ).casefold()

    required_markers = (
        "mock-only",
        "local-only",
        "no network",
        "no customer endpoint",
        "no credentials",
        "no raw payload",
        "no persistence",
        "no route",
        "no worker",
        "no production",
        "no sandbox connectivity proof",
        "all dispatch results remain blocked",
    )

    for marker in required_markers:
        assert marker in document
