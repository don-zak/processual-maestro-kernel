import pytest

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    authority_context,
    evaluate_admin_marketplace_authority,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
    AdminMarketplaceStepUpRequiredError,
)


def _context(*authorities: str, active: bool = True, step_up: bool = True):
    return authority_context(
        user_id="user_001",
        session_id="session_001",
        platform_authorities=authorities,
        active_platform_admin=active,
        recent_mfa_step_up=step_up,
    )


def test_active_platform_admin_can_read_marketplace_without_step_up() -> None:
    decision = require_admin_marketplace_authority(
        context=_context("platform_admin", step_up=False),
        action=AdminMarketplaceAction.VIEW_CATALOG,
    )
    assert decision.allowed is True
    assert decision.step_up_required is False


def test_sensitive_commercial_action_requires_recent_mfa_step_up() -> None:
    with pytest.raises(AdminMarketplaceStepUpRequiredError):
        require_admin_marketplace_authority(
            context=_context("platform_admin", step_up=False),
            action=AdminMarketplaceAction.PUBLISH_OFFER,
        )


def test_delegated_and_specialized_admins_are_explicitly_denied() -> None:
    for authority in ("platform_supervisor", "billing_admin", "viewer_admin", "owner_admin"):
        decision = evaluate_admin_marketplace_authority(
            context=_context(authority),
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        assert decision.allowed is False
        assert decision.reason_code == "non_super_administrator_denied"


def test_wildcard_and_missing_active_authority_fail_closed() -> None:
    for authorities in (("commercial:*",), ("*",), tuple()):
        with pytest.raises(AdminMarketplaceAuthorityDeniedError):
            require_admin_marketplace_authority(
                context=_context(*authorities),
                action=AdminMarketplaceAction.VIEW_AUDIT,
            )

    with pytest.raises(AdminMarketplaceAuthorityDeniedError):
        require_admin_marketplace_authority(
            context=_context("platform_admin", active=False),
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )


def test_unknown_action_fails_closed() -> None:
    decision = evaluate_admin_marketplace_authority(
        context=_context("platform_admin"),
        action="marketplace.unknown.execute",  # type: ignore[arg-type]
    )
    assert decision.allowed is False
    assert decision.reason_code == "unknown_marketplace_action_denied"
    assert decision.step_up_required is True
