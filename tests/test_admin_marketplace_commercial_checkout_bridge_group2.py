from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.admin_marketplace.commercial_checkout_bridge import (
    AdminActivationAction,
    AdminCommercialAction,
    AdminCommercialActor,
    AdminMarketplaceCheckoutBridge,
    build_admin_marketplace_checkout_bridge_status,
)
from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialDecisionOutcome,
)

ORDER_ID = UUID("47a43c6d-84cb-4452-b78f-627e51a60101")
DECISION_ID = UUID("47a43c6d-84cb-4452-b78f-627e51a60102")
NOW = datetime(2026, 7, 30, 17, 10, tzinfo=UTC)


def actor(
    authority: str = "platform_admin",
    *,
    mfa: bool = True,
) -> AdminCommercialActor:
    return AdminCommercialActor(
        user_reference="platform-admin:user-1",
        authority_reference=authority,
        recent_mfa_step_up=mfa,
        session_reference="session:1",
        correlation_reference="correlation:1",
    )


def action(
    kind: AdminCommercialAction,
    *,
    authority: str = "platform_admin",
    mfa: bool = True,
) -> AdminActivationAction:
    return AdminActivationAction(
        action=kind,
        order_id=ORDER_ID,
        decision_id=DECISION_ID,
        actor=actor(authority, mfa=mfa),
        approval_reference="billing-cycle-approval:order-1",
        reason="commercial review completed",
        occurred_at=NOW,
        idempotency_key=f"admin-action:{kind.value}:1",
    )


@pytest.mark.parametrize(
    ("kind", "outcome"),
    (
        (
            AdminCommercialAction.APPROVE_ACTIVATION,
            CommercialDecisionOutcome.APPROVED,
        ),
        (
            AdminCommercialAction.REJECT_ACTIVATION,
            CommercialDecisionOutcome.DENIED,
        ),
        (
            AdminCommercialAction.REQUIRE_ACTIVATION_REVIEW,
            CommercialDecisionOutcome.REQUIRES_REVIEW,
        ),
    ),
)
def test_bridge_maps_admin_action_to_governed_decision(
    kind,
    outcome,
) -> None:
    command = AdminMarketplaceCheckoutBridge().build_activation_command(action(kind))

    assert command.decision.outcome is outcome
    assert command.decision.authority_reference == "platform_admin"
    assert command.recent_mfa_step_up is True


def test_delegated_supervisor_is_explicitly_denied() -> None:
    with pytest.raises(PermissionError, match="platform_admin"):
        AdminMarketplaceCheckoutBridge().build_activation_command(
            action(
                AdminCommercialAction.APPROVE_ACTIVATION,
                authority="delegated_supervisor",
            )
        )


def test_recent_mfa_is_required() -> None:
    with pytest.raises(PermissionError, match="recent MFA"):
        AdminMarketplaceCheckoutBridge().build_activation_command(
            action(
                AdminCommercialAction.APPROVE_ACTIVATION,
                mfa=False,
            )
        )


def test_bridge_status_remains_fail_closed() -> None:
    status = build_admin_marketplace_checkout_bridge_status()

    assert status["enabled"] is False
    assert status["command_runtime_enabled"] is False
    assert status["delegated_supervisor_allowed"] is False
    assert status["customer_registration_owned"] is False
    assert status["direct_grant_allowed"] is False
