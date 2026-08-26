from __future__ import annotations

import pytest

from processual_api.admin_governance.onboarding_activation_service import (
    OPERATIONS_SUPERVISOR_PERMISSIONS,
    PERMISSIONS_BY_SUPERVISION_LEVEL,
    REVIEW_SUPERVISOR_PERMISSIONS,
)
from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAction,
    AdministratorGovernanceAuthorityContext,
    SENSITIVE_GOVERNANCE_ACTIONS,
    evaluate_administrator_governance_authority,
)


EXPECTED_REVIEW = frozenset(
    {
        "governance.administrators.view",
        "governance.activity.view",
    }
)
EXPECTED_OPERATIONS = frozenset(
    {
        *EXPECTED_REVIEW,
        "governance.sessions.view",
        "governance.session.revoke",
        "governance.administrator.freeze",
        "governance.administrator.restore",
    }
)


def _context(*, permissions: frozenset[str], recent_mfa: bool = True):
    return AdministratorGovernanceAuthorityContext(
        user_id="benchmark-supervisor",
        session_id="benchmark-session",
        identity_active=True,
        platform_authorities=frozenset({"platform_supervisor"}),
        active_permissions=permissions,
        recent_mfa_step_up=recent_mfa,
    )


def test_supervision_level_permission_matrix_is_exact_and_wildcard_free() -> None:
    assert REVIEW_SUPERVISOR_PERMISSIONS == EXPECTED_REVIEW
    assert OPERATIONS_SUPERVISOR_PERMISSIONS == EXPECTED_OPERATIONS
    assert PERMISSIONS_BY_SUPERVISION_LEVEL == {
        "review_supervisor": EXPECTED_REVIEW,
        "operations_supervisor": EXPECTED_OPERATIONS,
    }
    assert not any("*" in permission for permission in EXPECTED_OPERATIONS)


@pytest.mark.parametrize("action", tuple(AdministratorGovernanceAction))
def test_review_supervisor_is_strictly_read_only(action: AdministratorGovernanceAction) -> None:
    decision = evaluate_administrator_governance_authority(
        context=_context(permissions=EXPECTED_REVIEW),
        action=action,
    )
    assert decision.allowed is (action.value in EXPECTED_REVIEW)


@pytest.mark.parametrize("action", tuple(AdministratorGovernanceAction))
def test_operations_supervisor_is_bounded_to_declared_actions(action: AdministratorGovernanceAction) -> None:
    decision = evaluate_administrator_governance_authority(
        context=_context(permissions=EXPECTED_OPERATIONS),
        action=action,
    )
    assert decision.allowed is True


@pytest.mark.parametrize("action", tuple(SENSITIVE_GOVERNANCE_ACTIONS))
def test_sensitive_supervisor_actions_require_recent_mfa(action: AdministratorGovernanceAction) -> None:
    denied = evaluate_administrator_governance_authority(
        context=_context(permissions=EXPECTED_OPERATIONS, recent_mfa=False),
        action=action,
    )
    assert denied.allowed is False
    assert denied.reason_code == "recent_mfa_step_up_required"
    assert denied.step_up_required is True
