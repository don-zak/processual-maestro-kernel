"""Client-safe Enterprise Integration console contract for Settings.

This route extension composes existing authoritative plan capability, API-key,
operational-profile, scope-catalog, declarative readiness, identifiers-only
qualification persistence, and supervised revision primitives into one Settings
surface. It does not issue credentials, call external services, approve security
controls or production connectors, or expose stored secrets.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user
from processual_api.billing.usage_pricing import enterprise_integration_capability
from processual_api.integrations.enterprise_qualification_drafts import (
    safe_qualification_draft,
    save_qualification_draft,
    submit_qualification_draft,
)
from processual_api.integrations.enterprise_qualification_review import (
    request_qualification_revision,
    safe_qualification_review,
)
from processual_api.integrations.enterprise_sandbox_qualification import (
    build_customer_sandbox_qualification,
    build_sandbox_qualification_catalog,
)
from processual_api.integrations.integration_readiness import (
    list_integration_readiness_checks,
    summarize_integration_readiness,
)
from processual_api.integrations.scope_catalog import list_integration_scopes
from processual_api.services.supervisor_session_write_guard import (
    SupervisorSessionWriteGuardError,
    require_validated_supervisor_write_session,
)
from processual_api.supervision_rbac import (
    QUALIFICATION_READ_SCOPE,
    QUALIFICATION_REVIEW_SCOPE,
    require_supervision_scope,
)

from . import settings as settings_module


class EnterpriseSandboxQualificationRequest(BaseModel):
    """Identifiers-only customer input for sandbox qualification evaluation."""

    credential_profile_id: str = Field(min_length=1)
    requested_scope_ids: list[str] = Field(min_length=1)
    provided_input_ids: list[str] = Field(default_factory=list)


class EnterpriseQualificationRevisionRequest(BaseModel):
    """Fixed reason identifier for a supervised revision request."""

    reason_code: str = Field(min_length=1, max_length=80)


def _identity(current_user: dict[str, Any]) -> tuple[str, str]:
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    client_id = str(current_user.get("client_id") or user_id)
    return user_id, client_id


def _client_enterprise_capability(
    *,
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    user_id, _ = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    plan_id = settings_module._resolve_client_api_key_integration_plan_id(
        user_id,
        raw,
        current_user,
    )
    return user_id, raw, enterprise_integration_capability(plan_id)


def _require_enterprise_entitlement(capability: dict[str, Any]) -> None:
    if not bool(capability["enabled"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise Integration entitlement is required.",
        )


def _require_supervision_permission(
    current_user: dict[str, Any],
    required_scope: str,
) -> None:
    try:
        require_supervision_scope(current_user, required_scope)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


def _require_supervisor_write_session(
    request: Request,
    required_scope: str,
) -> dict[str, object]:
    try:
        return require_validated_supervisor_write_session(
            request,
            {required_scope},
            guard_name="enterprise_settings_qualification_review",
        )
    except SupervisorSessionWriteGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.detail,
        ) from exc


def _safe_target_user_id(value: str) -> str:
    target = str(value or "").strip()
    if (
        not target
        or len(target) > 200
        or "/" in target
        or "\\" in target
        or target in {".", ".."}
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid qualification target user identifier.",
        )
    return target


def _supervisor_actor(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("email")
        or current_user.get("user_id")
        or current_user.get("sub")
        or current_user.get("role")
        or "supervisor"
    ).strip() or "supervisor"


def _safe_readiness_checks(checks: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "readiness_check_id": check.readiness_check_id,
            "contract_id": check.contract_id,
            "credential_profile_id": check.credential_profile_id,
            "status": check.status,
            "blocking_reasons": list(check.blocking_reasons),
            "next_action": check.next_action,
            "sandbox_ready": check.sandbox_ready,
            "production_allowed": False,
            "runtime_connector_approved": False,
        }
        for check in checks
    ]


def _scope_posture(*, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "source": "catalog",
            "total": 0,
            "read": 0,
            "write": 0,
            "restricted": 0,
            "read_only_pilot": 0,
            "supervisor_approval_required": 0,
            "production_allowed_without_approval": 0,
        }

    scopes = list_integration_scopes()
    by_access = Counter(scope.access_level for scope in scopes)
    return {
        "enabled": True,
        "source": "catalog",
        "total": len(scopes),
        "read": by_access.get("read", 0),
        "write": by_access.get("write", 0),
        "restricted": by_access.get("restricted", 0),
        "read_only_pilot": sum(
            1 for scope in scopes if scope.allowed_in_read_only_pilot
        ),
        "supervisor_approval_required": sum(
            1 for scope in scopes if scope.requires_supervisor_approval
        ),
        "production_allowed_without_approval": sum(
            1 for scope in scopes if scope.production_allowed_without_approval
        ),
    }


def _qualification_catalog(*, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "source": "catalog",
            "profiles": [],
            "scopes": [],
        }

    return {
        "enabled": True,
        **build_sandbox_qualification_catalog(),
    }


def _console_sections(
    *,
    enabled: bool,
    key_count: int,
    operational_profile_count: int,
    scope_posture: dict[str, Any],
    readiness: dict[str, int],
) -> list[dict[str, Any]]:
    if not enabled:
        return [
            {
                "id": "entitlement",
                "label": "Enterprise entitlement",
                "status": "locked",
                "next_action": (
                    "Upgrade to an eligible Enterprise Integration plan."
                ),
            }
        ]

    keys_status = "ready" if key_count > 0 else "action_required"
    profile_status = (
        "ready"
        if operational_profile_count > 0
        and int(scope_posture.get("total", 0)) > 0
        else "action_required"
    )
    sandbox_ready = int(readiness.get("sandbox_ready", 0))
    readiness_status = "ready" if sandbox_ready > 0 else "action_required"

    return [
        {
            "id": "entitlement",
            "label": "Enterprise entitlement",
            "status": "ready",
            "next_action": (
                "Review integration credentials and sandbox readiness."
            ),
        },
        {
            "id": "api_keys",
            "label": "API & service identity",
            "status": keys_status,
            "next_action": (
                "Review active integration keys."
                if key_count > 0
                else (
                    "Provision a sandbox integration key or request "
                    "supervised issuance."
                )
            ),
        },
        {
            "id": "integration_profile",
            "label": "Profiles & scope posture",
            "status": profile_status,
            "next_action": (
                "Review read, write, and restricted scope posture "
                "before sandbox use."
                if profile_status == "ready"
                else (
                    "Complete the integration profile and scope policy "
                    "before sandbox use."
                )
            ),
        },
        {
            "id": "readiness",
            "label": "Integration readiness",
            "status": readiness_status,
            "next_action": (
                "Proceed with supervised sandbox review."
                if sandbox_ready > 0
                else "Complete required customer inputs and security controls."
            ),
        },
        {
            "id": "production",
            "label": "Production approval",
            "status": "blocked",
            "next_action": (
                "Production remains blocked until supervised qualification "
                "is complete."
            ),
        },
    ]


def _next_action(
    *,
    enabled: bool,
    key_count: int,
    operational_profile_count: int,
    readiness: dict[str, int],
) -> str:
    if not enabled:
        return "Upgrade to an eligible Enterprise Integration plan."
    if key_count == 0:
        return (
            "Provision a sandbox integration key or request supervised issuance."
        )
    if operational_profile_count == 0:
        return (
            "Complete the integration profile and scope policy before sandbox use."
        )
    if int(readiness.get("sandbox_ready", 0)) == 0:
        return "Complete required integration inputs and security controls."
    return "Proceed to supervised sandbox review; production remains blocked."


def enterprise_integration_console_payload(
    *,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    _, client_id = _identity(current_user)
    _, raw, capability = _client_enterprise_capability(
        current_user=current_user
    )
    enabled = bool(capability["enabled"])
    keys = (
        settings_module._active_client_integration_keys(raw, client_id)
        if enabled
        else []
    )
    operational = settings_module._client_api_key_operational_profiles_payload(
        enabled=enabled
    )
    scope_posture = _scope_posture(enabled=enabled)
    readiness_source = list_integration_readiness_checks() if enabled else []
    readiness_checks = _safe_readiness_checks(readiness_source)
    readiness = (
        summarize_integration_readiness(readiness_source)
        if enabled
        else {
            "total": 0,
            "blocked": 0,
            "sandbox_ready": 0,
            "production_allowed": 0,
            "runtime_connector_approved": 0,
        }
    )
    key_count = len(keys)
    operational_profile_count = int(operational["operational_profile_count"])
    qualification_draft = safe_qualification_draft(raw) if enabled else None
    qualification_review = safe_qualification_review(raw) if enabled else None
    return {
        "enabled": enabled,
        "status": capability["status"],
        "plan_id": capability["plan_id"],
        "normalized_plan_id": capability["normalized_plan_id"],
        "canonical_plan_id": capability.get(
            "canonical_plan_id",
            capability["normalized_plan_id"],
        ),
        "legacy_compatibility": capability["legacy_compatibility"],
        "eligible_plans": capability["eligible_plans"],
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
        "key_count": key_count,
        "keys": keys,
        "operational_profiles_enabled": operational[
            "operational_profiles_enabled"
        ],
        "operational_profile_count": operational_profile_count,
        "operational_profiles": operational["operational_profiles"],
        "scope_posture": scope_posture,
        "qualification_catalog": _qualification_catalog(enabled=enabled),
        "qualification_draft": qualification_draft,
        "qualification_review": qualification_review,
        "readiness": readiness,
        "readiness_checks": readiness_checks,
        "sections": _console_sections(
            enabled=enabled,
            key_count=key_count,
            operational_profile_count=operational_profile_count,
            scope_posture=scope_posture,
            readiness=readiness,
        ),
        "next_action": _next_action(
            enabled=enabled,
            key_count=key_count,
            operational_profile_count=operational_profile_count,
            readiness=readiness,
        ),
    }


@settings_module.router.get("/enterprise-integration", response_model=dict)
async def get_enterprise_integration_console(
    current_user: dict = Depends(get_current_user),
):
    return enterprise_integration_console_payload(current_user=current_user)


@settings_module.router.post(
    "/enterprise-integration/sandbox-qualification",
    response_model=dict,
)
async def evaluate_enterprise_sandbox_qualification(
    body: EnterpriseSandboxQualificationRequest,
    current_user: dict = Depends(get_current_user),
):
    _, _, capability = _client_enterprise_capability(current_user=current_user)
    _require_enterprise_entitlement(capability)

    try:
        qualification = build_customer_sandbox_qualification(
            credential_profile_id=body.credential_profile_id,
            requested_scope_ids=body.requested_scope_ids,
            provided_input_ids=body.provided_input_ids,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        **qualification,
        "environment": "sandbox",
        "persisted": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.put(
    "/enterprise-integration/sandbox-qualification/draft",
    response_model=dict,
)
async def save_enterprise_sandbox_qualification_draft(
    body: EnterpriseSandboxQualificationRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id, raw, capability = _client_enterprise_capability(
        current_user=current_user
    )
    _require_enterprise_entitlement(capability)
    try:
        qualification = save_qualification_draft(
            raw,
            credential_profile_id=body.credential_profile_id,
            requested_scope_ids=body.requested_scope_ids,
            provided_input_ids=body.provided_input_ids,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    settings_module._save_raw(user_id, raw)
    return {
        **qualification,
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.post(
    "/enterprise-integration/sandbox-qualification/draft/submit",
    response_model=dict,
)
async def submit_enterprise_sandbox_qualification_draft(
    current_user: dict = Depends(get_current_user),
):
    user_id, raw, capability = _client_enterprise_capability(
        current_user=current_user
    )
    _require_enterprise_entitlement(capability)
    try:
        qualification = submit_qualification_draft(raw)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    settings_module._save_raw(user_id, raw)
    return {
        **qualification,
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.get(
    "/admin/enterprise-integration/qualification-drafts/{user_id}",
    response_model=dict,
)
async def get_admin_enterprise_qualification_draft(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_supervision_permission(current_user, QUALIFICATION_READ_SCOPE)
    target_user_id = _safe_target_user_id(user_id)
    raw = settings_module._load_raw(target_user_id)
    draft = safe_qualification_draft(raw)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enterprise qualification draft not found.",
        )
    return {
        "status": "ready",
        "user_id": target_user_id,
        "qualification_draft": draft,
        "qualification_review": safe_qualification_review(raw),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.post(
    "/admin/enterprise-integration/qualification-drafts/{user_id}/request-revision",
    response_model=dict,
)
async def request_admin_enterprise_qualification_revision(
    user_id: str,
    body: EnterpriseQualificationRevisionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    _require_supervision_permission(current_user, QUALIFICATION_REVIEW_SCOPE)
    session = _require_supervisor_write_session(
        request,
        QUALIFICATION_REVIEW_SCOPE,
    )
    target_user_id = _safe_target_user_id(user_id)
    raw = settings_module._load_raw(target_user_id)
    try:
        review = request_qualification_revision(
            raw,
            reason_code=body.reason_code,
            reviewer_id=_supervisor_actor(current_user),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    settings_module._save_raw(target_user_id, raw)
    return {
        "status": "revision_requested",
        "user_id": target_user_id,
        "qualification_draft": safe_qualification_draft(raw),
        "qualification_review": review,
        "supervisor_session_validated": bool(session["session_validated"]),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "EnterpriseQualificationRevisionRequest",
    "EnterpriseSandboxQualificationRequest",
    "enterprise_integration_console_payload",
    "evaluate_enterprise_sandbox_qualification",
    "get_admin_enterprise_qualification_draft",
    "get_enterprise_integration_console",
    "request_admin_enterprise_qualification_revision",
    "save_enterprise_sandbox_qualification_draft",
    "submit_enterprise_sandbox_qualification_draft",
]
