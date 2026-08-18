from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PLATFORM_SUPERVISOR_AUTHORITY = "platform_supervisor"


class AdministratorGovernanceAction(StrEnum):
    VIEW_ADMINISTRATORS = "governance.administrators.view"
    VIEW_ACTIVITY = "governance.activity.view"
    VIEW_SESSIONS = "governance.sessions.view"
    REVOKE_SESSION = "governance.session.revoke"
    FREEZE_ADMINISTRATOR = "governance.administrator.freeze"
    RESTORE_ADMINISTRATOR = "governance.administrator.restore"


SENSITIVE_GOVERNANCE_ACTIONS = frozenset(
    {
        AdministratorGovernanceAction.REVOKE_SESSION,
        AdministratorGovernanceAction.FREEZE_ADMINISTRATOR,
        AdministratorGovernanceAction.RESTORE_ADMINISTRATOR,
    }
)


@dataclass(frozen=True, slots=True)
class AdministratorGovernanceAuthorityContext:
    user_id: str
    session_id: str
    identity_active: bool
    platform_authorities: frozenset[str]
    active_permissions: frozenset[str]
    recent_mfa_step_up: bool


@dataclass(frozen=True, slots=True)
class AdministratorGovernanceAuthorityDecision:
    action: AdministratorGovernanceAction
    allowed: bool
    reason_code: str
    step_up_required: bool


def evaluate_administrator_governance_authority(
    *,
    context: AdministratorGovernanceAuthorityContext,
    action: AdministratorGovernanceAction,
) -> AdministratorGovernanceAuthorityDecision:
    sensitive = action in SENSITIVE_GOVERNANCE_ACTIONS
    if not context.identity_active:
        return AdministratorGovernanceAuthorityDecision(action, False, "active_identity_required", sensitive)
    if any("*" in value for value in context.platform_authorities | context.active_permissions):
        return AdministratorGovernanceAuthorityDecision(action, False, "wildcard_authority_denied", sensitive)
    if PLATFORM_SUPERVISOR_AUTHORITY not in context.platform_authorities:
        return AdministratorGovernanceAuthorityDecision(action, False, "active_platform_supervisor_required", sensitive)
    if action.value not in context.active_permissions:
        return AdministratorGovernanceAuthorityDecision(action, False, "exact_permission_required", sensitive)
    if sensitive and not context.recent_mfa_step_up:
        return AdministratorGovernanceAuthorityDecision(action, False, "recent_mfa_step_up_required", True)
    return AdministratorGovernanceAuthorityDecision(
        action,
        True,
        "delegated_governance_permission_authorized",
        sensitive,
    )


__all__ = [
    "AdministratorGovernanceAction",
    "AdministratorGovernanceAuthorityContext",
    "AdministratorGovernanceAuthorityDecision",
    "PLATFORM_SUPERVISOR_AUTHORITY",
    "SENSITIVE_GOVERNANCE_ACTIONS",
    "evaluate_administrator_governance_authority",
]
