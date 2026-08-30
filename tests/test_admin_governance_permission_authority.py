from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAction,
    AdministratorGovernanceAuthorityContext,
    evaluate_administrator_governance_authority,
)


def context(*, permissions: set[str], recent_mfa_step_up: bool = False, active: bool = True):
    return AdministratorGovernanceAuthorityContext(
        user_id="user-1",
        session_id="session-1",
        identity_active=active,
        platform_authorities=frozenset({"platform_supervisor"}),
        active_permissions=frozenset(permissions),
        recent_mfa_step_up=recent_mfa_step_up,
    )


def test_review_supervisor_can_only_use_exact_review_permissions():
    review = {
        "governance.administrators.view",
        "governance.activity.view",
    }
    assert evaluate_administrator_governance_authority(
        context=context(permissions=review),
        action=AdministratorGovernanceAction.VIEW_ADMINISTRATORS,
    ).allowed
    decision = evaluate_administrator_governance_authority(
        context=context(permissions=review),
        action=AdministratorGovernanceAction.VIEW_SESSIONS,
    )
    assert not decision.allowed
    assert decision.reason_code == "exact_permission_required"


def test_operations_sensitive_actions_require_recent_mfa_step_up():
    permissions = {
        "governance.sessions.view",
        "governance.session.revoke",
        "governance.administrator.freeze",
        "governance.administrator.restore",
    }
    denied = evaluate_administrator_governance_authority(
        context=context(permissions=permissions),
        action=AdministratorGovernanceAction.FREEZE_ADMINISTRATOR,
    )
    assert not denied.allowed
    assert denied.reason_code == "recent_mfa_step_up_required"

    allowed = evaluate_administrator_governance_authority(
        context=context(permissions=permissions, recent_mfa_step_up=True),
        action=AdministratorGovernanceAction.FREEZE_ADMINISTRATOR,
    )
    assert allowed.allowed


def test_wildcard_or_inactive_identity_fails_closed():
    wildcard = evaluate_administrator_governance_authority(
        context=context(permissions={"governance.*"}, recent_mfa_step_up=True),
        action=AdministratorGovernanceAction.VIEW_ACTIVITY,
    )
    assert not wildcard.allowed
    assert wildcard.reason_code == "wildcard_authority_denied"

    inactive = evaluate_administrator_governance_authority(
        context=context(permissions={"governance.activity.view"}, active=False),
        action=AdministratorGovernanceAction.VIEW_ACTIVITY,
    )
    assert not inactive.allowed
    assert inactive.reason_code == "active_identity_required"


def test_missing_platform_supervisor_fails_closed():
    ctx = AdministratorGovernanceAuthorityContext(
        user_id="user-1",
        session_id="session-1",
        identity_active=True,
        platform_authorities=frozenset(),
        active_permissions=frozenset({"governance.administrators.view"}),
        recent_mfa_step_up=False,
    )
    decision = evaluate_administrator_governance_authority(
        context=ctx,
        action=AdministratorGovernanceAction.VIEW_ADMINISTRATORS,
    )
    assert not decision.allowed
    assert decision.reason_code == "active_platform_supervisor_required"
