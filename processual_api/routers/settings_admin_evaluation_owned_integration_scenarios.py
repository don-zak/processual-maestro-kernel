"""Project-owned Integration billing preparation for External Evaluation."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SandboxContentContract,
    SandboxSecretReference,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from .settings_admin_evaluation_binding_catalog import evaluation_binding_catalog
from .settings_admin_evaluation_binding_provisioning import (
    EvaluationBindingProvisionRequest,
    execute_evaluation_sandbox_operational_proof,
    provision_evaluation_binding,
)

_PRESET_ID = "INT-BILLING-01"
_DEFAULT_BINDING_ID = "evaluation.integration.billing_account_context.owned"


class OwnedIntegrationBillingPresetRequest(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    binding_id: str = Field(default=_DEFAULT_BINDING_ID, min_length=1, max_length=120)
    ttl_minutes: int = Field(default=30, ge=5, le=120)


def _binding(body: OwnedIntegrationBillingPresetRequest) -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id=body.binding_id,
        display_name="Project-owned Integration Billing Account Context proof",
        adapter_contract_id="billing",
        task_id="billing.account_context",
        credential_profile_id="enterprise_core_api_reference",
        environment="sandbox",
        base_url=body.base_url,
        method="GET",
        path="/billing/accounts/1",
        required_scope_ids=["billing:read"],
        response_format="json",
        response_data_path="$",
        field_mapping={
            "account_id": "$.account_id",
            "balance": "$.balance",
            "currency": "$.currency",
            "invoice_status": "$.invoice_status",
            "payment_status": "$.payment_status",
        },
        success_codes=[200],
        timeout_seconds=15,
    )


def _content(binding_id: str) -> SandboxContentContract:
    return SandboxContentContract(
        binding_id=binding_id,
        dataset_reference="project-evaluation-sandbox-billing-v1",
        fixture_profile_reference="integration-billing-account-read-only-v1",
        required_record_types=("billing_account",),
        acceptance_criteria_references=(_PRESET_ID,),
        customer_owned=False,
        project_owned=True,
        synthetic_or_nonproduction=True,
        secrets_included=False,
        raw_payloads_included=False,
    )


def _reference(binding_id: str) -> SandboxSecretReference:
    return SandboxSecretReference(
        binding_id=binding_id,
        provider_id="anonymous",
        secret_reference="public",
        customer_scoped=False,
        project_scoped=True,
        value_included=False,
    )


async def _catalog_item(
    *,
    binding_id: str,
    request: Request,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    catalog = await evaluation_binding_catalog(request=request, current_user=current_user)
    item = next(
        (
            candidate
            for candidate in catalog.get("bindings") or []
            if isinstance(candidate, dict)
            and str(candidate.get("binding_id") or "") == binding_id
        ),
        None,
    )
    if item is None or item.get("selectable") is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Owned Integration Evaluation binding did not reach sandbox-ready selectable state.",
        )
    return item


@settings_module.router.post(
    "/admin/evaluation-grants/bindings/presets/integration-billing-owned",
    response_model=dict,
)
async def prepare_owned_integration_billing_preset(
    body: OwnedIntegrationBillingPresetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Provision and prove a project-owned Integration safe-read scenario."""

    await require_active_platform_admin(current_user, request)
    binding = _binding(body)
    provisioned = await provision_evaluation_binding(
        binding_id=binding.binding_id,
        body=EvaluationBindingProvisionRequest(
            binding=binding,
            request_mapping=None,
            content_contract=_content(binding.binding_id),
            secret_reference=_reference(binding.binding_id),
            ttl_minutes=body.ttl_minutes,
        ),
        request=request,
        current_user=current_user,
    )
    proof = await execute_evaluation_sandbox_operational_proof(
        binding_id=binding.binding_id,
        body=binding_runtime.EndpointSandboxExecuteRequest(
            task_input={"account_id": "sandbox-account-001"}
        ),
        request=request,
        current_user=current_user,
    )
    item = await _catalog_item(
        binding_id=binding.binding_id,
        request=request,
        current_user=current_user,
    )

    return {
        "status": "ready",
        "preset_id": _PRESET_ID,
        "binding_id": binding.binding_id,
        "task_id": binding.task_id,
        "binding_selectable": True,
        "sandbox_readiness": item.get("sandbox_readiness"),
        "sandbox_grant": item.get("active_sandbox_grant"),
        "content_owner": "project",
        "credential_reference_scope": "project",
        "anonymous_public_sandbox": True,
        "provisioning": {
            "persisted": provisioned.get("persisted") is True,
            "request_mapping_configured": False,
            "raw_secret_visible": False,
            "raw_payload_visible": False,
        },
        "proof": {
            "operational_proof": proof.get("operational_proof") is True,
            "peer_address_verified": proof.get("peer_address_verified") is True,
            "network_request_executed": proof.get("network_request_executed") is True,
            "mapping_valid": proof.get("mapping_valid") is True,
            "ready_for_task_consumption": proof.get("ready_for_task_consumption") is True,
            "evidence_sha256": proof.get("evidence_sha256"),
            "raw_secret_visible": False,
            "raw_payload_visible": False,
        },
        "next_grant": {
            "evaluation_type": "integration",
            "allowed_task_ids": [binding.task_id],
            "allowed_binding_ids": [binding.binding_id],
            "allowed_endpoints": [
                {"method": "POST", "path": "/evaluation/runtime/task-execute"}
            ],
            "quota": 200,
            "subscription_required": False,
            "production_allowed": False,
        },
        "operation_class": "read",
        "production_mutation_performed": False,
        "production_allowed": False,
        "raw_secret_visible": False,
        "raw_payload_visible": False,
    }


__all__ = [
    "OwnedIntegrationBillingPresetRequest",
    "prepare_owned_integration_billing_preset",
]
