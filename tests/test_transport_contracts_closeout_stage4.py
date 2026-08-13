from __future__ import annotations

from dataclasses import replace

import pytest

import processual_api.integrations.transport_contracts as transport_module
from processual_api.integrations.mock_dispatcher import ConnectorDispatchRequest
from processual_api.integrations.transport_contracts import (
    ConnectorNoNetworkTransport,
    ConnectorTransportContractStatus,
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


def dispatch_request(*, plan_id: str, approval_reference: str = "approval-ref"):
    return ConnectorDispatchRequest(
        request_id="request-1",
        plan_id=plan_id,
        operation_id="operation-1",
        tenant_reference="tenant-ref",
        payload_hash="sha256-ref",
        idempotency_key="idem-ref",
        requested_at_reference="requested-ref",
        expires_at_reference="expires-ref",
        requester_reference="requester-ref",
        approval_reference=approval_reference,
        simulation_mode=True,
    )


def test_registry_normalization_listing_and_assessment_are_default_deny() -> None:
    contracts = list_connector_transport_contracts()
    assert len(contracts) == 1
    contract = contracts[0]
    assert normalize_connector_transport_id(f"  {contract.transport_id.upper()}  ") == contract.transport_id
    assert get_connector_transport_contract(contract.transport_id) is contract
    assert validate_connector_transport_registry() == ()

    assessment = assess_connector_transport_contract(contract.transport_id)
    assert assessment.transport_id == contract.transport_id
    assert assessment.status is ConnectorTransportContractStatus.DISABLED
    assert assessment.contract_valid is True
    assert assessment.interface_declared is True
    assert assessment.deterministic_blocking is True
    assert assessment.no_network is True
    assert assessment.transport_registered is False
    assert assessment.request_execution_allowed is False
    assert "transport_disabled" in assessment.blocker_codes
    assert "production_disabled" in assessment.blocker_codes


def test_normalization_and_lookup_reject_invalid_transport_ids() -> None:
    with pytest.raises(TypeError):
        normalize_connector_transport_id(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        normalize_connector_transport_id("   ")
    with pytest.raises(KeyError, match="Unknown connector transport"):
        get_connector_transport_contract("missing-transport")


def test_contract_validation_reports_type_duplicate_and_reference_failures(monkeypatch) -> None:
    contract = list_connector_transport_contracts()[0]
    assert validate_connector_transport_contracts((object(),)) == (
        "connector_transport_contract_type_invalid",
    )

    monkeypatch.setattr(
        transport_module,
        "_contract_validation_issues",
        lambda value: (f"{value.transport_id}:broken_reference",),
    )
    issues = validate_connector_transport_contracts((contract, contract))
    assert issues.count(f"{contract.transport_id}:broken_reference") == 2
    assert f"{contract.transport_id}:duplicate_transport_id" in issues


def test_transport_contract_and_result_dataclasses_reject_unsafe_mutations() -> None:
    contract = list_connector_transport_contracts()[0]
    with pytest.raises(ValueError, match="environment"):
        replace(contract, environment="production")
    with pytest.raises(ValueError, match="read-only"):
        replace(contract, access_mode="write")
    with pytest.raises(ValueError, match="must remain True"):
        replace(contract, sandbox_only=False)
    with pytest.raises(ValueError, match="must remain False"):
        replace(contract, external_http_allowed=True)
    with pytest.raises(ValueError, match="status"):
        replace(contract, status="blocked")

    result = ConnectorTransportResult(
        request_id="request-1",
        transport_id=contract.transport_id,
        plan_id=contract.plan_id,
        status="blocked",
        reason_code="disabled",
        reason="disabled by policy",
        contract_validated=True,
        request_validated=True,
        plan_validated=True,
        pilot_validated=True,
        secret_manager_validated=True,
    )
    assert result.status is ConnectorTransportResultStatus.BLOCKED
    with pytest.raises(ValueError, match="must remain False"):
        replace(result, external_http_used=True)
    with pytest.raises(TypeError, match="boolean"):
        replace(result, request_validated=1)


def test_transport_request_requires_dispatch_request_and_simulation_contract() -> None:
    contract = list_connector_transport_contracts()[0]
    with pytest.raises(TypeError, match="dispatch_request"):
        ConnectorTransportRequest(
            request_id="request-1",
            transport_id=contract.transport_id,
            dispatch_request=object(),  # type: ignore[arg-type]
        )


def test_no_network_transport_unknown_plan_invalid_and_success_branches(monkeypatch) -> None:
    transport = ConnectorNoNetworkTransport()
    contract = list_connector_transport_contracts()[0]

    with pytest.raises(TypeError, match="ConnectorTransportRequest"):
        transport.transmit(object())  # type: ignore[arg-type]

    unknown = ConnectorTransportRequest(
        request_id="request-unknown",
        transport_id="unknown-transport",
        dispatch_request=dispatch_request(plan_id=contract.plan_id),
    )
    unknown_result = transport.transmit(unknown)
    assert unknown_result.status is ConnectorTransportResultStatus.UNKNOWN_TRANSPORT
    assert unknown_result.transport_attempted is False

    invalid = ConnectorTransportRequest(
        request_id="request-invalid",
        transport_id=contract.transport_id,
        dispatch_request=dispatch_request(
            plan_id=contract.plan_id,
            approval_reference="",
        ),
    )
    invalid_result = transport.transmit(invalid)
    assert invalid_result.status is ConnectorTransportResultStatus.INVALID_REQUEST
    assert invalid_result.request_validated is False

    mismatch = ConnectorTransportRequest(
        request_id="request-mismatch",
        transport_id=contract.transport_id,
        dispatch_request=dispatch_request(plan_id="different-plan"),
    )
    mismatch_result = transport.transmit(mismatch)
    assert mismatch_result.status is ConnectorTransportResultStatus.PLAN_MISMATCH
    assert mismatch_result.contract_validated is True

    valid = ConnectorTransportRequest(
        request_id="request-valid",
        transport_id=contract.transport_id,
        dispatch_request=dispatch_request(plan_id=contract.plan_id),
    )
    result = transport.transmit(valid)
    assert result.status is ConnectorTransportResultStatus.BLOCKED
    assert result.reason_code == "transport_disabled_no_network"
    assert result.contract_validated is True
    assert result.request_validated is True
    assert result.plan_validated is True
    assert result.pilot_validated is True
    assert result.secret_manager_validated is True
    assert result.transport_attempted is False
    assert result.external_http_used is False

    monkeypatch.setattr(
        transport_module,
        "_contract_validation_issues",
        lambda value: (f"{value.transport_id}:broken",),
    )
    broken_result = transport.transmit(valid)
    assert broken_result.status is ConnectorTransportResultStatus.BLOCKED
    assert broken_result.reason_code == "transport_contract_invalid"
    assert broken_result.contract_validated is False
