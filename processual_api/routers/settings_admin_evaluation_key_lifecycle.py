"""Administrator lifecycle controls for issued External Evaluation API keys."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    list_evaluation_authority_keys,
    load_evaluation_authority_state,
    update_evaluation_authority_key_lifecycle,
)
from processual_api.services.evaluation_cgt_evidence_postgres import (
    latest_evaluation_cgt_governance,
)
from processual_api.services.evaluation_grants import find_evaluation_grant
from processual_api.services.evaluation_runtime_delivery_postgres import (
    EvaluationDeliveryError,
    list_evaluation_audit_receipts,
)

from . import settings as settings_module


class EvaluationKeyRevoke(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


def _actor(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "super_admin"
    )


async def _require_platform_admin(request: Request, current_user: dict[str, Any]) -> None:
    await require_active_platform_admin(current_user, request)


def _lifecycle_http_error(exc: EvaluationAuthorityError) -> HTTPException:
    code = str(exc)
    if code == "evaluation_authority_key_not_found":
        return HTTPException(status_code=404, detail="Evaluation API key not found.")
    if code == "evaluation_authority_key_delivery_required":
        return HTTPException(
            status_code=409,
            detail="Confirm API key delivery before acknowledging receipt.",
        )
    if code == "evaluation_authority_key_revoked":
        return HTTPException(status_code=409, detail="Evaluation API key is revoked.")
    if code in {
        "evaluation_authority_key_transition_invalid",
        "evaluation_authority_key_action_invalid",
    }:
        return HTTPException(
            status_code=409,
            detail="Invalid Evaluation API key lifecycle transition.",
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Shared Evaluation authority is unavailable.",
    )


def _grant_string_list(grant: dict[str, Any], field: str) -> list[str]:
    values = grant.get(field, [])
    if not isinstance(values, list):
        return []
    return sorted(
        {
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        }
    )


def _final_audit_summary(
    *,
    grant: dict[str, Any],
    keys: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    governance_proofs: list[dict[str, Any]],
) -> dict[str, Any]:
    succeeded = sum(1 for item in receipts if item.get("status") == "succeeded")
    failed = sum(1 for item in receipts if item.get("status") == "failed")
    executing = sum(1 for item in receipts if item.get("status") == "executing")
    evidence_persisted = sum(1 for item in receipts if item.get("evidence_persisted_at"))
    quota_used = sum(max(0, int(item.get("usage_count", 0) or 0)) for item in keys)
    quota_rejected = sum(max(0, int(item.get("quota_rejected_count", 0) or 0)) for item in keys)
    per_key_limit = max(0, int(grant.get("max_requests", 0) or 0))

    task_ids = _grant_string_list(grant, "allowed_task_ids")
    binding_ids = _grant_string_list(grant, "allowed_binding_ids")

    key_states: dict[str, int] = {}
    for key in keys:
        lifecycle = str(key.get("lifecycle_status") or key.get("status") or "unknown")
        key_states[lifecycle] = key_states.get(lifecycle, 0) + 1

    ledger_receipt_mismatch = quota_used > 0 and not receipts
    if ledger_receipt_mismatch:
        audit_outcome = "ledger_receipt_mismatch"
    elif failed > 0 or executing > 0:
        audit_outcome = "needs_review"
    elif succeeded > 0 and succeeded == evidence_persisted:
        audit_outcome = "complete"
    else:
        audit_outcome = "not_evaluated"

    latest_governance = governance_proofs[0] if governance_proofs else None
    return {
        "report_type": "external_evaluation_final_summary",
        "audit_outcome": audit_outcome,
        "qualification_decision": "operator_required",
        "grant_id": str(grant.get("grant_id") or ""),
        "grant_status": str(grant.get("status") or "unknown"),
        "issued_to": str(grant.get("issued_to") or ""),
        "client_id": str(grant.get("client_id") or ""),
        "ledger_receipt_mismatch": ledger_receipt_mismatch,
        "quota": {
            "per_key_limit": per_key_limit,
            "used_across_keys": quota_used,
            "rejected_across_keys": quota_rejected,
            "issued_key_count": len(keys),
            "semantics": "admitted_execution",
        },
        "executions": {
            "total": len(receipts),
            "succeeded": succeeded,
            "failed": failed,
            "executing": executing,
            "evidence_persisted": evidence_persisted,
        },
        "tasks": task_ids,
        "bindings": binding_ids,
        "key_lifecycle": key_states,
        "governance_proof_count": len(governance_proofs),
        "latest_governance": latest_governance.get("governance") if latest_governance else None,
        "fate_vector": (
            latest_governance.get("governance", {}).get("fate_vector")
            if latest_governance
            else None
        ),
        "fate_vector_basis": (
            latest_governance.get("governance", {}).get("fate_vector_basis")
            if latest_governance
            else None
        ),
        "maestro_task_completed": bool(
            latest_governance and latest_governance.get("maestro_task_completed") is True
        ),
        "maestro_consumption": (
            latest_governance.get("maestro_consumption") if latest_governance else None
        ),
        "maestro_governed_evidence_sha256": (
            latest_governance.get("maestro_governed_evidence_sha256")
            if latest_governance
            else None
        ),
        "production_allowed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }


async def _governance_proofs_for_keys(
    *,
    owner_id: str,
    grant_id: str,
    keys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    for key in keys:
        key_id = str(key.get("key_id") or key.get("api_key_id") or "").strip()
        if not key_id:
            continue
        proof = await latest_evaluation_cgt_governance(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=key_id,
        )
        if proof:
            proofs.append({"api_key_id": key_id, **proof})
    return proofs


@settings_module.router.get(
    "/admin/evaluation-grants/{grant_id}/keys",
    response_model=dict,
)
async def list_evaluation_keys(
    grant_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    try:
        keys = await list_evaluation_authority_keys(_owner_user_id(current_user), grant_id)
    except EvaluationAuthorityError as exc:
        raise _lifecycle_http_error(exc) from exc
    return {
        "status": "ready",
        "grant_id": grant_id,
        "key_count": len(keys),
        "keys": keys,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


@settings_module.router.get(
    "/admin/evaluation-grants/{grant_id}/audit-receipts",
    response_model=dict,
)
async def list_evaluation_audit_report_receipts(
    grant_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Return safe receipts plus a final aggregate audit summary."""

    await _require_platform_admin(request, current_user)
    owner_id = _owner_user_id(current_user)
    try:
        receipts = await list_evaluation_audit_receipts(owner_id, grant_id, limit=limit)
        keys = await list_evaluation_authority_keys(owner_id, grant_id)
        raw = await load_evaluation_authority_state(owner_id)
        grant = find_evaluation_grant(raw, grant_id)
        if grant is None:
            raise EvaluationAuthorityError("evaluation_grant_not_found")
        governance_proofs = await _governance_proofs_for_keys(
            owner_id=owner_id,
            grant_id=grant_id,
            keys=keys,
        )
    except (EvaluationDeliveryError, EvaluationAuthorityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation audit report is unavailable.",
        ) from exc
    return {
        "status": "ready",
        "grant_id": grant_id,
        "report_type": "external_evaluation_admin_audit",
        "summary": _final_audit_summary(
            grant=grant,
            keys=keys,
            receipts=receipts,
            governance_proofs=governance_proofs,
        ),
        "governance_proofs": governance_proofs,
        "receipt_count": len(receipts),
        "receipts": receipts,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/keys/{key_id}/confirm-delivery",
    response_model=dict,
)
async def confirm_evaluation_key_delivery(
    grant_id: str,
    key_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    try:
        key = await update_evaluation_authority_key_lifecycle(
            _owner_user_id(current_user),
            grant_id,
            key_id,
            action="confirm_delivery",
            actor=_actor(current_user),
        )
    except EvaluationAuthorityError as exc:
        raise _lifecycle_http_error(exc) from exc
    return {"status": "delivery_confirmed", "key": key}


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/keys/{key_id}/acknowledge",
    response_model=dict,
)
async def acknowledge_evaluation_key_receipt(
    grant_id: str,
    key_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    try:
        key = await update_evaluation_authority_key_lifecycle(
            _owner_user_id(current_user),
            grant_id,
            key_id,
            action="acknowledge",
            actor=_actor(current_user),
        )
    except EvaluationAuthorityError as exc:
        raise _lifecycle_http_error(exc) from exc
    return {"status": "acknowledged", "key": key}


@settings_module.router.delete(
    "/admin/evaluation-grants/{grant_id}/keys/{key_id}",
    response_model=dict,
)
async def revoke_evaluation_key(
    grant_id: str,
    key_id: str,
    request: Request,
    body: EvaluationKeyRevoke | None = None,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    try:
        key = await update_evaluation_authority_key_lifecycle(
            _owner_user_id(current_user),
            grant_id,
            key_id,
            action="revoke",
            actor=_actor(current_user),
            reason=body.reason if body else None,
        )
    except EvaluationAuthorityError as exc:
        raise _lifecycle_http_error(exc) from exc
    return {"status": "revoked", "key": key}


__all__ = [
    "EvaluationKeyRevoke",
    "acknowledge_evaluation_key_receipt",
    "confirm_evaluation_key_delivery",
    "list_evaluation_audit_report_receipts",
    "list_evaluation_keys",
    "revoke_evaluation_key",
]
