"""Controlled deterministic sandbox qualification for R10 bindings.

This service permits one existing local-only synthetic ticket-read workflow.
It does not receive a raw sandbox API key, resolve credentials, invoke a real
connector, access a network, persist payloads, or enable production/runtime.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from processual_api.integrations.fake_sandbox_transport import (
    ConnectorFakeSandboxRequest,
)
from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
)
from processual_api.integrations.sandbox_evidence import (
    ConnectorSandboxEvidenceRequest,
    build_connector_sandbox_evidence_bundle,
)
from processual_api.integrations.sandbox_read_workflow import (
    ConnectorSandboxReadWorkflowRequest,
    execute_connector_sandbox_read_workflow,
)
from processual_api.integrations.transport_contracts import (
    ConnectorTransportRequest,
)
from processual_api.services.enterprise_r10_binding_store_18 import (
    list_safe_enterprise_r10_bindings,
)


class EnterpriseR10ControlledSandboxError(ValueError):
    """Safe rejection from controlled local qualification."""


_WORKFLOW_ID = (
    "telecom_ticketing_deterministic_"
    "sandbox_read_workflow"
)

_FAKE_TRANSPORT_ID = (
    "telecom_ticketing_deterministic_"
    "fake_sandbox_transport"
)

_BASE_TRANSPORT_ID = (
    "telecom_ticketing_disabled_no_network_transport"
)

_PLAN_ID = (
    "telecom_ticketing_reference_"
    "sandbox_ticket_read_operation_plan"
)

_EVIDENCE_CONTRACT_ID = (
    "telecom_ticketing_local_sandbox_"
    "evidence_contract"
)

_CONNECTOR_ID = "telecom_ticketing_reference"
_SCOPE_ID = "ticket:read"


def _required_reference(
    field_name: str,
    value: Any,
) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise EnterpriseR10ControlledSandboxError(
            f"{field_name}_required"
        )

    return normalized


def _binding_by_id(
    binding_id: str,
    *,
    binding_store_path: Path | None,
) -> dict[str, Any]:
    matches = [
        item
        for item in list_safe_enterprise_r10_bindings(
            path=binding_store_path
        )
        if item.get("binding_id") == binding_id
    ]

    if not matches:
        raise EnterpriseR10ControlledSandboxError(
            "enterprise_r10_binding_not_found"
        )

    if len(matches) != 1:
        raise EnterpriseR10ControlledSandboxError(
            "duplicate_enterprise_r10_binding_id"
        )

    return matches[0]


def _safe_projection(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value):
        return _safe_projection(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): _safe_projection(item)
            for key, item in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [
            _safe_projection(item)
            for item in value
        ]

    return value


def _deterministic_reference(
    prefix: str,
    *,
    binding_id: str,
    revision: int,
) -> str:
    material = (
        f"{prefix}|{binding_id}|{revision}"
    ).encode()

    digest = hashlib.sha256(material).hexdigest()[:24]

    return f"{prefix}_{digest}"


def _assert_false_flags(
    projection: dict[str, Any],
    field_names: tuple[str, ...],
) -> None:
    enabled = [
        field_name
        for field_name in field_names
        if projection.get(field_name) is not False
    ]

    if enabled:
        raise EnterpriseR10ControlledSandboxError(
            "unsafe_local_result:"
            + ",".join(enabled)
        )


def qualify_enterprise_r10_controlled_sandbox(
    binding_id: str,
    *,
    client_id: str,
    institution_case_id: str,
    institution_task_id: str,
    binding_store_path: Path | None = None,
) -> dict[str, Any]:
    """Run the single approved local synthetic sandbox workflow."""
    binding_id = _required_reference(
        "binding_id",
        binding_id,
    )
    client_id = _required_reference(
        "client_id",
        client_id,
    )
    institution_case_id = _required_reference(
        "institution_case_id",
        institution_case_id,
    )
    institution_task_id = _required_reference(
        "institution_task_id",
        institution_task_id,
    )

    binding = _binding_by_id(
        binding_id,
        binding_store_path=binding_store_path,
    )

    if binding.get("client_id") != client_id:
        raise EnterpriseR10ControlledSandboxError(
            "binding_client_mismatch"
        )

    if (
        binding.get("institution_case_id")
        != institution_case_id
    ):
        raise EnterpriseR10ControlledSandboxError(
            "binding_institution_case_mismatch"
        )

    if (
        binding.get("institution_task_id")
        != institution_task_id
    ):
        raise EnterpriseR10ControlledSandboxError(
            "binding_institution_task_mismatch"
        )

    if binding.get("status") != "sandbox_api_key_issued":
        raise EnterpriseR10ControlledSandboxError(
            "binding_not_sandbox_api_key_issued"
        )

    if (
        not str(
            binding.get(
                "external_sandbox_api_key_id"
            )
            or ""
        ).strip()
    ):
        raise EnterpriseR10ControlledSandboxError(
            "sandbox_api_key_reference_missing"
        )

    if binding.get("target_environment") != "sandbox":
        raise EnterpriseR10ControlledSandboxError(
            "binding_environment_not_sandbox"
        )

    if binding.get("connector_id") != _CONNECTOR_ID:
        raise EnterpriseR10ControlledSandboxError(
            "connector_not_supported_by_local_workflow"
        )

    scope_ids = tuple(
        str(item).strip()
        for item in binding.get(
            "requested_scope_ids",
            (),
        )
        if str(item).strip()
    )

    if scope_ids != (_SCOPE_ID,):
        raise EnterpriseR10ControlledSandboxError(
            "binding_scope_not_exact_ticket_read"
        )

    guardrail_fields = (
        "production_allowed",
        "runtime_connector_approved",
        "external_http_allowed",
        "write_allowed",
        "restricted_allowed",
        "raw_secret_visible",
    )

    unsafe_binding_flags = [
        field_name
        for field_name in guardrail_fields
        if binding.get(field_name) is not False
    ]

    if unsafe_binding_flags:
        raise EnterpriseR10ControlledSandboxError(
            "binding_guardrail_violation:"
            + ",".join(unsafe_binding_flags)
        )

    revision = int(binding.get("revision") or 0)

    if revision < 1:
        raise EnterpriseR10ControlledSandboxError(
            "binding_revision_invalid"
        )

    request_id = _deterministic_reference(
        "q2br8_request",
        binding_id=binding_id,
        revision=revision,
    )

    operation_id = _deterministic_reference(
        "q2br8_operation",
        binding_id=binding_id,
        revision=revision,
    )

    idempotency_key = _deterministic_reference(
        "q2br8_idempotency",
        binding_id=binding_id,
        revision=revision,
    )

    payload_hash = hashlib.sha256(
        (
            f"{binding_id}|{client_id}|"
            f"{institution_case_id}|"
            f"{institution_task_id}|"
            f"{_PLAN_ID}|{_SCOPE_ID}|{revision}"
        ).encode()
    ).hexdigest()

    dispatch_request = ConnectorDispatchRequest(
        request_id=request_id,
        plan_id=_PLAN_ID,
        operation_id=operation_id,
        tenant_reference=(
            f"client_reference_{client_id}"
        ),
        payload_hash=payload_hash,
        idempotency_key=idempotency_key,
        requested_at_reference=(
            _required_reference(
                "binding_updated_at",
                binding.get("updated_at"),
            )
        ),
        expires_at_reference=(
            "active_sandbox_binding_reference"
        ),
        requester_reference=(
            f"client_reference_{client_id}"
        ),
        approval_reference=(
            _required_reference(
                "qualification_grant_id",
                binding.get(
                    "qualification_grant_id"
                ),
            )
        ),
        simulation_mode=True,
    )

    transport_request = ConnectorTransportRequest(
        request_id=request_id,
        transport_id=_BASE_TRANSPORT_ID,
        dispatch_request=dispatch_request,
    )

    fake_request = ConnectorFakeSandboxRequest(
        request_id=request_id,
        fake_transport_id=_FAKE_TRANSPORT_ID,
        transport_request=transport_request,
    )

    workflow_request = (
        ConnectorSandboxReadWorkflowRequest(
            request_id=request_id,
            workflow_id=_WORKFLOW_ID,
            fake_request=fake_request,
        )
    )

    workflow_result = (
        execute_connector_sandbox_read_workflow(
            workflow_request
        )
    )

    workflow_projection = _safe_projection(
        workflow_result
    )

    if (
        workflow_projection.get("status")
        != "synthetic_read_completed"
    ):
        raise EnterpriseR10ControlledSandboxError(
            "controlled_sandbox_workflow_rejected:"
            + str(
                workflow_projection.get(
                    "reason_code"
                )
                or "unknown"
            )
        )

    _assert_false_flags(
        workflow_projection,
        (
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
        ),
    )

    evidence_id = _deterministic_reference(
        "q2br8_evidence",
        binding_id=binding_id,
        revision=revision,
    )

    evidence_bundle = (
        build_connector_sandbox_evidence_bundle(
            ConnectorSandboxEvidenceRequest(
                evidence_id=evidence_id,
                evidence_contract_id=(
                    _EVIDENCE_CONTRACT_ID
                ),
                source_result=workflow_result,
            )
        )
    )

    evidence_projection = _safe_projection(
        evidence_bundle
    )

    if evidence_projection.get("evidence_captured") is not True:
        raise EnterpriseR10ControlledSandboxError(
            "controlled_sandbox_evidence_not_captured"
        )

    required_true = (
        "deterministic",
        "immutable",
        "reference_only",
        "local_only",
        "non_persistent",
        "export_safe",
    )

    missing_safe_properties = [
        field_name
        for field_name in required_true
        if evidence_projection.get(field_name) is not True
    ]

    if missing_safe_properties:
        raise EnterpriseR10ControlledSandboxError(
            "unsafe_evidence_properties:"
            + ",".join(missing_safe_properties)
        )

    _assert_false_flags(
        evidence_projection,
        (
            "source_executed",
            "payload_body_included",
            "raw_response_included",
            "secret_material_included",
            "credentials_resolved",
            "dispatcher_invoked",
            "network_accessed",
            "bundle_persisted",
            "background_task_created",
            "external_export_executed",
            "route_exposed",
            "runtime_used",
            "production_used",
        ),
    )

    return {
        "status": "synthetic_qualification_completed",
        "binding_id": binding_id,
        "binding_revision": revision,
        "connector_id": _CONNECTOR_ID,
        "scope_id": _SCOPE_ID,
        "plan_id": _PLAN_ID,
        "workflow": workflow_projection,
        "evidence": evidence_projection,
        "sandbox_api_key_reference_verified": True,
        "sandbox_api_key_value_received": False,
        "sandbox_api_key_value_returned": False,
        "credential_resolved": False,
        "dispatcher_invoked": False,
        "real_transport_attempted": False,
        "operation_executed": False,
        "external_http_used": False,
        "socket_used": False,
        "payload_persisted": False,
        "runtime_used": False,
        "production_used": False,
    }
